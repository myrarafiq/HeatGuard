from __future__ import annotations

from datetime import datetime
from typing import Any

from .risk import assess_hour, limits_for
from .thresholds import DEFAULT_ACCLIMATIZED, DEFAULT_CLOTHING, ClothingId, MIDDAY_BREAK_END, MIDDAY_BREAK_START, Workload


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
    work_rest = assessment.get("work_rest") or {}
    cycle = work_rest.get("code")
    actions: list[str] = []
    codes: list[str] = []

    if level == "unknown" or cycle == "unknown":
        actions.append("Hold judgment for this hour — required environmental inputs are missing.")
        codes.append("missing_data")
    elif cycle == "stop" or (not cycle and level == "red"):
        if cycle == "stop":
            actions.append(
                f"Stop continuous outdoor {workload} work this hour — ACGIH 0–25% work allocation "
                f"is the remaining published band (or is already exceeded)."
            )
        else:
            actions.append(
                f"Stop continuous outdoor {workload} work this hour (red — at/above TLV)."
            )
        codes.append("stop")
    elif cycle in {"45/15", "30/30", "15/45"}:
        work_min = work_rest.get("work_min")
        rest_min = work_rest.get("rest_min")
        allocation = work_rest.get("allocation") or "published allocation"
        actions.append(
            f"Work/rest {cycle} ({work_min} min work / {rest_min} min rest each hour) "
            f"for {workload} work — ACGIH {allocation}."
        )
        codes.append(f"work_rest_{cycle.replace('/', '_')}")
    elif not cycle and level == "amber":
        actions.append(
            f"Do not treat this as continuous {workload} work — amber is at/above the Action Limit. "
            "Use the ACGIH work/rest cycle attached to this hour when available."
        )
        codes.append("increase_controls")
    else:
        actions.append(f"Conditions support planned {workload} outdoor work with conventional breaks.")
        codes.append("proceed")

    if midday and level in {"amber", "red"}:
        actions.append(
            "Midday window (12:30–15:00): pause outdoor work or move crews to shaded/indoor tasks "
            "(operational heat-protection practice — not a Florida legal mandate)."
        )
        codes.append("midday_break")

    if level == "green" and workload == "heavy" and not midday and cycle not in {"stop", "unknown"}:
        actions.append("Prefer this window for heavy outdoor tasks if the day heats up later.")
        codes.append("prefer_heavy_window")

    return {
        "action_codes": codes,
        "actions": actions,
        "work_rest": work_rest,
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
        key=lambda a: _score(
            a["level"],
            a.get("effective_wbgt_c") if a.get("effective_wbgt_c") is not None else a.get("screening_wbgt_c"),
        ),
    )
    best = ranked[0]
    worst = ranked[-1]
    ranking = [
        {
            "site_id": a["site_id"],
            "level": a["level"],
            "screening_wbgt_c": a.get("screening_wbgt_c"),
            "effective_wbgt_c": a.get("effective_wbgt_c"),
            "temp_c_mean": a.get("temp_c_mean"),
            "screening_air_temp_c": a.get("screening_air_temp_c"),
            "work_rest": (a.get("work_rest") or {}).get("code"),
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


def build_site_timeline(
    hours: list[dict[str, Any]],
    workload: Workload,
    *,
    acclimatized: bool = DEFAULT_ACCLIMATIZED,
    clothing: ClothingId | str = DEFAULT_CLOTHING,
) -> list[dict[str, Any]]:
    timeline = []
    for hour in sorted(hours, key=lambda h: h.get("hour_local") or ""):
        assessment = assess_hour(hour, workload, acclimatized=acclimatized, clothing=clothing)
        recommendation = recommend_for_hour(assessment)
        timeline.append({**assessment, "recommendation": recommendation})
    return timeline


def _site_label(site_id: str | None, names: dict[str, str] | None) -> str:
    if not site_id:
        return "unknown site"
    return (names or {}).get(site_id) or site_id.replace("_", " ").title()


def _hour_clock(hour_local: str | None) -> str:
    dt = _parse_hour(str(hour_local or ""))
    return dt.strftime("%H:%M") if dt else (hour_local or "—")


def _hour_int(hour_local: str | None) -> int | None:
    dt = _parse_hour(str(hour_local or ""))
    return None if dt is None else dt.hour


def _effective(row: dict[str, Any]) -> float | None:
    value = row.get("effective_wbgt_c")
    if value is None:
        value = row.get("screening_wbgt_c")
    return float(value) if value is not None else None


def todays_actions(
    timelines_by_site: dict[str, list[dict[str, Any]]],
    workload: Workload,
    *,
    site_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Four manager moves — a shift plan, not a stack of per-site warnings."""
    names = site_names or {}
    rows: list[dict[str, Any]] = []
    for site_id, timeline in timelines_by_site.items():
        for row in timeline:
            rows.append({**row, "site_id": row.get("site_id") or site_id})

    return [
        _move_morning(rows, workload, names),
        _move_midday(rows, names),
        _move_afternoon(rows, workload, names),
        _move_crews(rows, workload, names),
    ]


def _move(code: str, number: int, title: str, detail: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "priority": number,
        "move": number,
        "code": code,
        "title": title,
        "detail": detail,
    }
    payload.update(extra)
    return payload


def _move_morning(
    rows: list[dict[str, Any]],
    workload: Workload,
    names: dict[str, str],
) -> dict[str, Any]:
    morning = [
        row
        for row in rows
        if _hour_int(row.get("hour_local")) is not None
        and _hour_int(row.get("hour_local")) < 12
        and row.get("level") in {"green", "amber"}
    ]
    if not morning:
        return _move(
            "do_this_morning",
            1,
            "Do this morning",
            f"No morning hours support planned outdoor {workload} work in today's calculated results.",
            site_id=None,
            hour_local=None,
            hours=[],
            workload=workload,
            risk_level=None,
        )
    best = sorted(morning, key=lambda a: _score(a["level"], _effective(a)))[0]
    same_site = [
        row
        for row in morning
        if row.get("site_id") == best["site_id"] and row.get("level") == best["level"]
    ]
    hours = sorted({row["hour_local"] for row in same_site if row.get("hour_local")})
    if not hours:
        clocks = "—"
    elif hours[0] == hours[-1]:
        clocks = _hour_clock(hours[0])
    else:
        clocks = f"{_hour_clock(hours[0])}–{_hour_clock(hours[-1])}"
    wbgt = _effective(best)
    wbgt_txt = f"{wbgt:.1f}°C" if wbgt is not None else "unknown"
    label = _site_label(best.get("site_id"), names)
    return _move(
        "do_this_morning",
        1,
        "Do this morning",
        (
            f"{workload.replace('_', ' ').title()} work at {label}, {clocks} "
            f"({best['level']}, effective WBGT {wbgt_txt})."
        ),
        site_id=best.get("site_id"),
        hour_local=best.get("hour_local"),
        hours=hours,
        workload=workload,
        risk_level=best["level"],
        explanation=best.get("reason"),
    )


def _move_midday(rows: list[dict[str, Any]], names: dict[str, str]) -> dict[str, Any]:
    flagged = [
        row
        for row in rows
        if in_midday_break(str(row.get("hour_local") or "")) and row.get("level") in {"amber", "red"}
    ]
    if not flagged:
        return _move(
            "pause_shade_window",
            2,
            "Pause / shade window",
            "No amber/red hours fall in 12:30–15:00 in today's calculated results.",
            site_ids=[],
            hours=[],
            risk_level=None,
        )
    site_ids = sorted({row["site_id"] for row in flagged if row.get("site_id")})
    hours = sorted({row["hour_local"] for row in flagged if row.get("hour_local")})
    labels = ", ".join(_site_label(sid, names) for sid in site_ids)
    worst = max(flagged, key=lambda r: {"amber": 1, "red": 2}.get(r.get("level"), 0))
    return _move(
        "pause_shade_window",
        2,
        "Pause / shade window",
        (
            f"12:30–15:00: pause outdoor work or move crews to shade/indoor at {labels} "
            f"(amber/red in this window — operational practice, not Florida law)."
        ),
        site_id=worst.get("site_id"),
        site_ids=site_ids,
        hour_local=worst.get("hour_local"),
        hours=hours,
        risk_level=worst.get("level"),
    )


def _move_afternoon(
    rows: list[dict[str, Any]],
    workload: Workload,
    names: dict[str, str],
) -> dict[str, Any]:
    after = [
        row
        for row in rows
        if (_hour_int(row.get("hour_local")) or 0) >= 15 and row.get("level") == "red"
    ]
    if not after:
        return _move(
            "do_not_do_this_afternoon",
            3,
            "Do not do this afternoon",
            f"No site stays red for outdoor {workload} work after 15:00 in today's calculated results.",
            site_ids=[],
            hours=[],
            workload=workload,
            risk_level=None,
        )
    site_ids = sorted({row["site_id"] for row in after if row.get("site_id")})
    hours = sorted({row["hour_local"] for row in after if row.get("hour_local")})
    labels = ", ".join(_site_label(sid, names) for sid in site_ids)
    clocks = "–".join(_hour_clock(h) for h in (hours[0], hours[-1]) if hours)
    return _move(
        "do_not_do_this_afternoon",
        3,
        "Do not do this afternoon",
        (
            f"Do not schedule outdoor {workload} work after 15:00 at {labels} "
            f"({clocks} stay red vs the {workload} TLV)."
        ),
        site_id=site_ids[0] if site_ids else None,
        site_ids=site_ids,
        hour_local=hours[0] if hours else None,
        hours=hours,
        workload=workload,
        risk_level="red",
    )


def _move_crews(
    rows: list[dict[str, Any]],
    workload: Workload,
    names: dict[str, str],
) -> dict[str, Any]:
    ten = [row for row in rows if row.get("hour_local") and "T10:" in str(row["hour_local"])]
    pool = ten or rows
    usable = [row for row in pool if row.get("level") not in {None, "unknown"}]
    if len({row.get("site_id") for row in usable}) < 2:
        return _move(
            "move_work",
            4,
            "Move work",
            "Not enough site hours to recommend moving crews.",
            site_id=None,
            hour_local=None,
            workload=workload,
        )
    ranked = sorted(usable, key=lambda a: _score(a["level"], _effective(a)))
    best, worst = ranked[0], ranked[-1]
    hour_local = best.get("hour_local") if ten else (ten[0]["hour_local"] if ten else best.get("hour_local"))
    if ten:
        hour_local = ten[0]["hour_local"]
        best = sorted(ten, key=lambda a: _score(a["level"], _effective(a)))[0]
        worst = sorted(ten, key=lambda a: _score(a["level"], _effective(a)))[-1]
    cool_name = _site_label(best.get("site_id"), names)
    hot_name = _site_label(worst.get("site_id"), names)
    clock = _hour_clock(hour_local)
    same_site = best.get("site_id") == worst.get("site_id")
    if same_site:
        detail = (
            f"{cool_name} is the only comparable site at {clock}; "
            f"hold outdoor {workload} work if the hour is {best.get('level')}."
        )
    else:
        detail = (
            f"Send {workload} crews to {cool_name} at {clock} ({best.get('level')}); "
            f"hold {hot_name} for light/indoor ({worst.get('level')})."
        )
    return _move(
        "move_work",
        4,
        "Move work",
        detail,
        site_id=best.get("site_id"),
        from_site_id=worst.get("site_id"),
        hour_local=hour_local,
        workload=workload,
        risk_level=best.get("level"),
        cooler_level=best.get("level"),
        hotter_level=worst.get("level"),
        explanation=best.get("reason"),
    )


def _flip_site(row: dict[str, Any], names: dict[str, str] | None) -> dict[str, Any]:
    return {
        "site_id": row.get("site_id"),
        "site_name": _site_label(row.get("site_id"), names),
        "level": row.get("level"),
        "effective_wbgt_c": row.get("effective_wbgt_c"),
        "screening_wbgt_c": row.get("screening_wbgt_c"),
        "screening_air_temp_c": row.get("screening_air_temp_c"),
        "screening_air_temp_source": row.get("screening_air_temp_source"),
        "temp_c_mean": row.get("temp_c_mean"),
        "wet_bulb_temperature_celsius": row.get("wet_bulb_temperature_celsius"),
        "solar_ghi": row.get("solar_ghi"),
    }


def threshold_flip(
    hours: list[dict[str, Any]],
    workload: Workload,
    *,
    acclimatized: bool = DEFAULT_ACCLIMATIZED,
    clothing: ClothingId | str = DEFAULT_CLOTHING,
    site_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Documented hour where OSHA Table 2 changes a work decision.

    Preference: same workload, one site below Action Limit (green) and another
    at/above TLV (red). Else same-workload AL or TLV band flip. Else same site
    heavy vs light. Never invents temperatures.
    """
    limits = limits_for(workload)
    empty = {
        "found": False,
        "kind": None,
        "hour_local": None,
        "workload": workload,
        "action_limit_c": limits.action_limit_c,
        "tlv_c": limits.tlv_c,
        "decision": "No OSHA Table 2 decision-change was present in today's calculated hours.",
        "cooler_site": None,
        "hotter_site": None,
        "note": (
            "Green = below Action Limit; amber = Action Limit to TLV; red = at/above TLV "
            f"for {workload} (unacclimatized default)."
        ),
    }
    if not hours:
        return empty

    by_hour: dict[str, list[dict[str, Any]]] = {}
    for hour in hours:
        assessed = assess_hour(hour, workload, acclimatized=acclimatized, clothing=clothing)
        if assessed.get("hour_local"):
            by_hour.setdefault(str(assessed["hour_local"]), []).append(assessed)

    def _pack(
        kind: str,
        hour_local: str,
        cooler: dict[str, Any],
        hotter: dict[str, Any],
        decision: str,
        note: str,
    ) -> dict[str, Any]:
        return {
            "found": True,
            "kind": kind,
            "hour_local": hour_local,
            "workload": workload,
            "action_limit_c": limits.action_limit_c,
            "tlv_c": limits.tlv_c,
            "cooler_site": _flip_site(cooler, site_names),
            "hotter_site": _flip_site(hotter, site_names),
            "decision": decision,
            "note": note,
        }

    ranked_hours = sorted(by_hour.items())

    def _pair(usable: list[dict[str, Any]], low: str, high: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        lows = [r for r in usable if r.get("level") == low]
        highs = [r for r in usable if r.get("level") == high]
        if not lows or not highs:
            return None
        cooler = min(lows, key=lambda r: _effective(r) if _effective(r) is not None else 999)
        hotter = max(highs, key=lambda r: _effective(r) if _effective(r) is not None else -1)
        if cooler.get("site_id") == hotter.get("site_id"):
            return None
        return cooler, hotter

    searches = (
        ("same_workload_green_red", "green", "red", "Action Limit / TLV"),
        ("same_workload_tlv", "amber", "red", "TLV"),
        ("same_workload_al", "green", "amber", "Action Limit"),
    )
    for kind, low, high, limit_name in searches:
        for hour_local, group in ranked_hours:
            usable = [r for r in group if r.get("level") in {"green", "amber", "red"}]
            pair = _pair(usable, low, high)
            if not pair:
                continue
            cooler, hotter = pair
            clock = _hour_clock(hour_local)
            cool_name = _site_label(cooler.get("site_id"), site_names)
            hot_name = _site_label(hotter.get("site_id"), site_names)
            return _pack(
                kind,
                hour_local,
                cooler,
                hotter,
                (
                    f"Send {workload} crews to {cool_name} at {clock}; "
                    f"hold {hot_name} for light/indoor."
                ),
                (
                    f"Same {workload} workload, OSHA Table 2 {limit_name} flip. "
                    f"{cool_name} effective WBGT {cooler.get('effective_wbgt_c')}°C is {cooler.get('level')}; "
                    f"{hot_name} {hotter.get('effective_wbgt_c')}°C is {hotter.get('level')} "
                    f"(AL {limits.action_limit_c:.0f}°C / TLV {limits.tlv_c:.0f}°C)."
                ),
            )

    other: Workload = "light" if workload != "light" else "heavy"
    other_limits = limits_for(other)
    for hour in sorted(hours, key=lambda h: h.get("hour_local") or ""):
        primary = assess_hour(hour, workload, acclimatized=acclimatized, clothing=clothing)
        secondary = assess_hour(hour, other, acclimatized=acclimatized, clothing=clothing)
        if primary.get("level") in {None, "unknown"} or secondary.get("level") in {None, "unknown"}:
            continue
        if primary.get("level") == secondary.get("level"):
            continue
        levels = {primary.get("level"), secondary.get("level")}
        if "green" in levels and "red" in levels:
            rank = 0
        elif "green" in levels or "red" in levels:
            rank = 1
        else:
            rank = 2
        if rank > 1 and not (primary.get("level") != secondary.get("level")):
            continue
        site_name = _site_label(primary.get("site_id"), site_names)
        clock = _hour_clock(primary.get("hour_local"))
        hold = primary if {"red", "amber"} & {primary.get("level")} else secondary
        go = secondary if hold is primary else primary
        go_wl = other if go is secondary else workload
        hold_wl = workload if hold is primary else other
        return {
            "found": True,
            "kind": "same_site_workload",
            "hour_local": primary.get("hour_local"),
            "workload": workload,
            "other_workload": other,
            "action_limit_c": limits.action_limit_c,
            "tlv_c": limits.tlv_c,
            "cooler_site": {**_flip_site(go, site_names), "workload": go_wl},
            "hotter_site": {**_flip_site(hold, site_names), "workload": hold_wl},
            "decision": (
                f"At {site_name} {clock}, keep {go_wl} work; do not treat this hour as "
                f"outdoor {hold_wl} work ({hold.get('level')} vs {go.get('level')})."
            ),
            "note": (
                f"Same site, different OSHA Table 2 workload rows. "
                f"{go_wl} AL {limits_for(go_wl).action_limit_c:.0f}°C / TLV {limits_for(go_wl).tlv_c:.0f}°C; "
                f"{hold_wl} AL {other_limits.action_limit_c:.0f}°C / TLV {other_limits.tlv_c:.0f}°C. "
                f"Effective WBGT {primary.get('effective_wbgt_c')}°C."
            ),
        }

    return empty
