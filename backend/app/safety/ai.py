from __future__ import annotations

import json
import os
import re
from typing import Any


SYSTEM_RULES = """You are HeatGuard's operations brief writer for Florida construction supervisors.

HARD RULES:
1. You ONLY explain facts already present in the provided JSON (risk levels, screening WBGT, actions, site rankings).
2. You MUST NOT invent temperatures, wet-bulb values, WBGT numbers, risk colors, thresholds, or site recommendations.
3. You MUST NOT recalculate safety. Risk math was already done using OSHA/NIOSH/ACGIH screening limits.
4. If the JSON lacks the answer, say you cannot tell from today's calculated results.
5. Keep language practical and short. No medical diagnosis. Screening guidance only — not a certified WBGT instrument.
6. If facts.data.mode is fixture, say the numbers are from the backup demo day — not a live FortyGuard pull. If mixed, say so.
"""


def render_brief_template(planner: dict[str, Any]) -> str:
    workload = planner.get("workload", "heavy")
    actions = planner.get("todays_actions") or []
    comparison = planner.get("comparison") or {}
    sites = planner.get("sites") or []

    lines = [
        f"Today's Heat Operations Brief — workload: {workload}",
        "",
    ]
    data = planner.get("data") or {}
    mode = data.get("mode")
    if mode == "fixture":
        lines.append("Data: backup demo fixtures — not a live FortyGuard pull.")
        lines.append("")
    elif mode == "mixed":
        lines.append("Data: MIXED live and fixture hours — do not treat as one source.")
        lines.append("")
    elif mode == "live":
        lines.append("Data: live FortyGuard pull.")
        lines.append("")
    if comparison.get("answer"):
        lines.append(f"Site ranking: {comparison['answer']}")
        lines.append("")

    lines.append("Site status:")
    for site in sites:
        n = len(site.get("hours") or [])
        lines.append(f"- {site.get('name') or site['id']}: {site.get('current_risk')} ({n} hours)")
    lines.append("")

    if actions:
        lines.append("Recommended actions:")
        for i, action in enumerate(actions[:6], 1):
            lines.append(f"{i}. {action.get('title')} — {action.get('detail')}")
    else:
        lines.append("No recommended actions yet — load forecast hours first.")

    lines.append("")
    lines.append(
        "Note: Colors use a screening WBGT estimate from FortyGuard wet-bulb + air temperature "
        "against OSHA/NIOSH published limits. Not an on-site WBGT meter reading."
    )
    return "\n".join(lines)


def answer_from_facts(question: str, planner: dict[str, Any]) -> str:
    """Deterministic Q&A over calculated results — no LLM required."""
    q = question.lower().strip()
    ctx = planner.get("ai_context") or planner
    sites = ctx.get("sites") or planner.get("sites") or []
    comparison = ctx.get("comparison") or planner.get("comparison") or {}
    at_10 = ctx.get("comparison_at_10am") or planner.get("comparison_at_10am")
    workload = planner.get("workload", "heavy")

    if "10" in q and ("best" in q or "prioritize" in q or "heavy" in q):
        if at_10 and at_10.get("answer"):
            return at_10["answer"]
        return comparison.get("answer") or "No 10 AM comparison available in today's calculated results."

    if "after 3" in q or "after 15" in q or "3 pm" in q or "15:" in q:
        afternoon = []
        for site in sites:
            for h in site.get("hours") or []:
                hour = str(h.get("hour_local") or "")
                if re.search(r"T(15|16|17|18|19):", hour) and h.get("level") != "unknown":
                    afternoon.append({**h, "site_id": site.get("id"), "name": site.get("name")})
        if not afternoon:
            return "No after-3 PM hours are present in today's calculated results."
        best = sorted(
            afternoon,
            key=lambda h: (
                {"green": 0, "amber": 1, "red": 2}.get(h.get("level"), 3),
                h.get("screening_wbgt_c") if h.get("screening_wbgt_c") is not None else 999,
            ),
        )[0]
        return (
            f"After 3 PM, best calculated conditions for {workload} work: "
            f"{best.get('name') or best.get('site_id')} at {best.get('hour_local')} "
            f"({best.get('level')}, screening WBGT {best.get('screening_wbgt_c')}°C)."
        )

    if "why" in q and "red" in q:
        for site in sites:
            name = (site.get("name") or site.get("id") or "").lower()
            sid = (site.get("id") or "").lower()
            if sid in q or name in q or any(tok in q for tok in sid.split("_")):
                reds = [h for h in (site.get("hours") or []) if h.get("level") == "red"]
                if not reds:
                    return f"{site.get('name') or site.get('id')} is not red in today's calculated results."
                h = reds[0]
                return (
                    f"{site.get('name') or site.get('id')} is red because screening WBGT "
                    f"{h.get('screening_wbgt_c')}°C met/exceeded the {workload} TLV "
                    f"in the calculated results (e.g. {h.get('hour_local')})."
                )
        red_sites = [s for s in sites if s.get("current_risk") == "red"]
        if not red_sites:
            return "No site is red in today's calculated results."
        s = red_sites[0]
        return f"{s.get('name') or s.get('id')} is marked red overall. Ask 'Why is {s.get('id')} red?' for the hour-level reason."

    if "prioritize" in q or "best" in q or "where" in q:
        return comparison.get("answer") or "No site comparison is available yet."

    if "midday" in q or "break" in q:
        actions = [a for a in (ctx.get("todays_actions") or planner.get("todays_actions") or []) if a.get("code") == "midday_break"]
        if not actions:
            return "No midday-break actions were generated from today's calculated risk rows."
        return " ".join(f"{a.get('title')}: {a.get('detail')}" for a in actions)

    # Fallback: brief summary
    return render_brief_template(planner)


def maybe_llm_explain(question: str | None, planner: dict[str, Any]) -> dict[str, Any]:
    """Optional OpenAI narration. Falls back to deterministic explainer."""
    facts = planner.get("ai_context") or {
        "sites": planner.get("sites"),
        "todays_actions": planner.get("todays_actions"),
        "comparison": planner.get("comparison"),
    }
    deterministic = answer_from_facts(question or "Summarize today's plan", planner)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not question:
        return {
            "mode": "deterministic",
            "answer": deterministic if question else render_brief_template(planner),
            "brief": render_brief_template(planner),
        }

    try:
        import httpx

        prompt = {
            "question": question,
            "facts": facts,
            "deterministic_answer_hint": deterministic,
        }
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": SYSTEM_RULES},
                    {
                        "role": "user",
                        "content": (
                            "Answer the supervisor question using ONLY these facts JSON. "
                            "If unsure, say you cannot tell from the calculated results.\n\n"
                            + json.dumps(prompt, default=str)
                        ),
                    },
                ],
            },
            timeout=45.0,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return {
            "mode": "llm",
            "answer": text,
            "brief": render_brief_template(planner),
            "deterministic_fallback": deterministic,
        }
    except Exception as exc:  # noqa: BLE001 — demo must not fail on AI
        return {
            "mode": "deterministic_fallback",
            "answer": deterministic,
            "brief": render_brief_template(planner),
            "error": str(exc),
        }
