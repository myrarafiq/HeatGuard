from __future__ import annotations

from datetime import datetime
from typing import Any

from .risk import assess_hour
from .thresholds import MIDDAY_BREAK_END, MIDDAY_BREAK_START, Workload


def _parse_hour(hour_local: str) -> datetime | None:
    try:
        return datetime.fromisoformat(hour_local)
    except ValueError:
        return None


def in_midday_break(hour_local: str) -> bool:
    dt = _parse_hour(hour_local)
    if dt is None:
        return False
    minutes = dt.hour * 60 + dt.minute
    start = MIDDAY_BREAK_START[0] * 60 + MIDDAY_BREAK_START[1]
    end = MIDDAY_BREAK_END[0] * 60 + MIDDAY_BREAK_END[1]
    return start <= minutes < end


def _score(level: str, wbgt: float | None) -> tuple[int, float]:
    rank = {"green": 0, "amber": 1, "red": 2, "unknown": 3}.get(level, 3)
    return rank, float(wbgt) if wbgt is not None else 999.0


def recommend_for_hour(assessment: dict[str, Any]) -> dict[str, Any]:
    level = assessment["level"]
    workload = assessment["workload"]
    midday = in_midday_break(str(assessment.get("hour_local") or ""))
    actions: list[str] = []
    codes: list[str] = []

    if level == "unknown":
        actions.append("Hold judgment for this hour — required environmental inputs are missing.")
        codes.append("missing_data")
    elif level == "green":
        actions.append(f"Conditions support planned {workload} outdoor work with normal hydration/rest.")
        codes.append("proceed")
    elif level == "amber":
        actions.append(
            f"Increase rest/water cycles; consider reducing continuous {workload} outdoor exposure."
        )
        codes.append("increase_controls")
    else:
        actions.append(
            f"Do not schedule continuous outdoor {workload} work — reduce intensity, add shade/rest, or reschedule."
        )
        codes.append("restrict_outdoor")

    if midday and level in {"amber", "red"}:
        actions.append(
            "Midday window (12:30–15:00): pause outdoor work or move crews to shaded/indoor tasks "
            "(operational heat-protection practice — not a Florida legal mandate)."
        )
        codes.append("midday_break")

    if level == "green" and workload == "heavy" and not midday:
        actions.append("Prefer this window for heavy outdoor tasks if the day heats up later.")
        codes.append("prefer_heavy_window")

    return {
        "action_codes": codes,
        "actions": actions,
        "midday_break_window": midday,
        "primary_action": actions[0] if actions else None,
        "explanation": assessment.get("reason"),
    }


def compare_sites_at_hour(
    assessments: list[dict[str, Any]],
    *,
    hour_local: str | None = None,
) -> dict[str, Any]:
    rows = assessments
    if hour_local:
        rows = [a for a in assessments if a.get("hour_local") == hour_local]
    usable = [a for a in rows if a.get("level") != "unknown"]
    if not usable:
        return {
            "best_site_id": None,
            "worst_site_id": None,
            "ranking": [],
            "answer": "No comparable site data for that hour.",
        }

    ranked = sorted(
        usable,
        key=lambda a: _score(a["level"], a.get("screening_wbgt_c")),
    )
    best = ranked[0]
    worst = ranked[-1]
    ranking = [
        {
            "site_id": a["site_id"],
            "level": a["level"],
            "screening_wbgt_c": a.get("screening_wbgt_c"),
            "temp_c_mean": a.get("temp_c_mean"),
            "reason": a.get("reason"),
        }
        for a in ranked
    ]
    hour_label = hour_local or best.get("hour_local")
    return {
        "hour_local": hour_label,
        "workload": best.get("workload"),
        "best_site_id": best["site_id"],
        "worst_site_id": worst["site_id"],
        "ranking": ranking,
        "answer": (
            f"Best site for {best.get('workload')} outdoor work at {hour_label}: "
            f"{best['site_id']} ({best['level']}, screening WBGT {best.get('screening_wbgt_c')}°C). "
            f"Worst: {worst['site_id']} ({worst['level']})."
        ),
    }


def best_windows_for_site(
    assessments: list[dict[str, Any]],
    site_id: str,
    *,
    prefer_level: str = "green",
) -> list[dict[str, Any]]:
    rows = [a for a in assessments if a.get("site_id") == site_id and a.get("level") != "unknown"]
    preferred = [a for a in rows if a.get("level") == prefer_level]
    pool = preferred or [a for a in rows if a.get("level") == "amber"] or rows
    pool = sorted(pool, key=lambda a: (a.get("screening_wbgt_c") is None, a.get("screening_wbgt_c") or 999))
    return [
        {
            "hour_local": a["hour_local"],
            "level": a["level"],
            "screening_wbgt_c": a.get("screening_wbgt_c"),
            "recommendation": recommend_for_hour(a),
        }
        for a in pool[:3]
    ]


def build_site_timeline(hours: list[dict[str, Any]], workload: Workload) -> list[dict[str, Any]]:
    timeline = []
    for hour in sorted(hours, key=lambda h: h.get("hour_local") or ""):
        assessment = assess_hour(hour, workload)
        recommendation = recommend_for_hour(assessment)
        timeline.append({**assessment, "recommendation": recommendation})
    return timeline


def todays_actions(
    timelines_by_site: dict[str, list[dict[str, Any]]],
    workload: Workload,
) -> list[dict[str, Any]]:
    """Manager-facing action list: explainable, ordered by urgency then time."""
    actions: list[dict[str, Any]] = []

    # Cross-site: best morning heavy window if any greens exist
    morning: list[dict[str, Any]] = []
    for site_id, timeline in timelines_by_site.items():
        for row in timeline:
            dt = _parse_hour(str(row.get("hour_local") or ""))
            if dt and dt.hour < 12 and row.get("level") in {"green", "amber"}:
                morning.append({**row, "site_id": site_id})
    if morning:
        best = sorted(morning, key=lambda a: _score(a["level"], a.get("screening_wbgt_c")))[0]
        actions.append(
            {
                "priority": 1,
                "code": "prioritize_coolest_morning",
                "title": f"Prioritize {workload} work at {best['site_id']} this morning",
                "detail": best["recommendation"]["primary_action"],
                "site_id": best["site_id"],
                "hour_local": best["hour_local"],
                "risk_level": best["level"],
                "explanation": best.get("reason"),
            }
        )

    # Midday break callouts
    for site_id, timeline in timelines_by_site.items():
        for row in timeline:
            if row["recommendation"].get("midday_break_window") and "midday_break" in row["recommendation"]["action_codes"]:
                actions.append(
                    {
                        "priority": 2,
                        "code": "midday_break",
                        "title": f"Midday outdoor pause at {site_id}",
                        "detail": row["recommendation"]["actions"][-1],
                        "site_id": site_id,
                        "hour_local": row["hour_local"],
                        "risk_level": row["level"],
                        "explanation": row.get("reason"),
                    }
                )
                break

    # Red restrictions
    for site_id, timeline in timelines_by_site.items():
        reds = [r for r in timeline if r.get("level") == "red"]
        if reds:
            first = reds[0]
            actions.append(
                {
                    "priority": 1,
                    "code": "restrict_red_hours",
                    "title": f"Restrict outdoor {workload} work at {site_id} during red hours",
                    "detail": first["recommendation"]["primary_action"],
                    "site_id": site_id,
                    "hour_local": first["hour_local"],
                    "risk_level": "red",
                    "explanation": first.get("reason"),
                    "red_hours": [r["hour_local"] for r in reds],
                }
            )

    # Coolest overall site today
    site_scores: list[tuple[str, float, str]] = []
    for site_id, timeline in timelines_by_site.items():
        usable = [r for r in timeline if r.get("screening_wbgt_c") is not None]
        if usable:
            avg = sum(float(r["screening_wbgt_c"]) for r in usable) / len(usable)
            worst = max(usable, key=lambda r: {"green": 0, "amber": 1, "red": 2}.get(r["level"], 0))
            site_scores.append((site_id, avg, worst["level"]))
    if site_scores:
        site_scores.sort(key=lambda t: t[1])
        coolest = site_scores[0]
        hottest = site_scores[-1]
        actions.append(
            {
                "priority": 3,
                "code": "site_comparison",
                "title": f"Coolest site today: {coolest[0]} · Hottest: {hottest[0]}",
                "detail": (
                    f"Mean screening WBGT — {coolest[0]}: {coolest[1]:.1f}°C; "
                    f"{hottest[0]}: {hottest[1]:.1f}°C."
                ),
                "site_id": coolest[0],
                "hour_local": None,
                "risk_level": coolest[2],
                "explanation": "Site ranking uses mean screening WBGT across available hours.",
            }
        )

    actions.sort(key=lambda a: (a["priority"], a.get("hour_local") or ""))
    # Deduplicate midday spam — keep first per site already handled
    return actions
