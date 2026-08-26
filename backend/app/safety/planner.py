from __future__ import annotations

from typing import Any

from ..db import summarize_data_mode
from ..time_windows import florida_now, hour_bucket
from .recommend import (
    best_windows_for_site,
    build_site_timeline,
    compare_sites_at_hour,
    todays_actions,
)
from .thresholds import (
    DEFAULT_ACCLIMATIZED,
    DEFAULT_CLOTHING,
    SCREENING_AIR_TEMP_ORDER,
    SOURCE_CITATION,
    WORKLOAD_DEFINITIONS,
    WORK_REST_CITATION,
    ClothingId,
    Workload,
    planning_assumption,
)


_LEVEL_RANK = {"green": 0, "amber": 1, "red": 2}


def build_planner(
    sites: list[dict[str, Any]],
    hours: list[dict[str, Any]],
    workload: Workload = "heavy",
    *,
    acclimatized: bool = DEFAULT_ACCLIMATIZED,
    clothing: ClothingId | str = DEFAULT_CLOTHING,
    hour_local: str | None = None,
) -> dict[str, Any]:
    by_site_hours: dict[str, list[dict[str, Any]]] = {}
    for row in hours:
        by_site_hours.setdefault(row["site_id"], []).append(row)

    timelines: dict[str, list[dict[str, Any]]] = {}
    site_summaries: list[dict[str, Any]] = []
    all_assessments: list[dict[str, Any]] = []
    assumption = planning_assumption(acclimatized=acclimatized, clothing=clothing)

    for site in sites:
        site_id = site["id"]
        timeline = build_site_timeline(
            by_site_hours.get(site_id, []),
            workload,
            acclimatized=acclimatized,
            clothing=clothing,
        )
        timelines[site_id] = timeline
        all_assessments.extend(timeline)

        now_row = _now_row(timeline, selected_hour_local=hour_local)
        peak_row = _peak_row(timeline)
        now_risk = now_row["level"] if now_row else "unknown"
        peak = peak_row["level"] if peak_row else "unknown"

        site_summaries.append(
            {
                **{k: site[k] for k in ("id", "name", "city", "surface", "lat", "lon") if k in site},
                "polygon_aoi": site.get("polygon_aoi"),
                "now_risk": now_risk,
                "now_hour_local": now_row.get("hour_local") if now_row else None,
                "peak_risk": peak,
                "peak_hour_local": peak_row.get("hour_local") if peak_row else None,
                "current_risk": now_risk,
                "hours": timeline,
                "best_windows": best_windows_for_site(timeline, site_id),
            }
        )

    comparison = compare_sites_at_hour(all_assessments)
    ten_am = next(
        (
            a["hour_local"]
            for a in all_assessments
            if a.get("hour_local") and "T10:" in a["hour_local"]
        ),
        None,
    )
    at_10 = compare_sites_at_hour(all_assessments, hour_local=ten_am) if ten_am else None
    data_mode = summarize_data_mode(hours)
    actions = todays_actions(timelines, workload)

    return {
        "workload": workload,
        "workload_definition": WORKLOAD_DEFINITIONS[workload],
        "assumption": assumption,
        "data": data_mode,
        "methodology": {
            "source": SOURCE_CITATION,
            "work_rest_source": WORK_REST_CITATION,
            "method": "screening_wbgt_estimate",
            "formula": "0.7*Tw + 0.3*Ta_hotspot (+0.5°C if solar_ghi≥600) + clothing CAF",
            "screening_air_temp_order": list(SCREENING_AIR_TEMP_ORDER),
            "notes": (
                "Screening estimate only — FortyGuard does not provide globe temperature or wind. "
                "Not a substitute for on-site WBGT monitoring. "
                "now_risk is the current or selected hour; peak_risk is the worst hour in the window. "
                "Heat index / apparent temperature are display-only and are not used in the WBGT estimate."
            ),
            "doc": "backend/safety/METHODOLOGY.md",
        },
        "sites": site_summaries,
        "todays_actions": actions,
        "comparison": comparison,
        "comparison_at_10am": at_10,
        "ai_context": _ai_context(
            site_summaries, workload, actions, comparison, at_10, data_mode, assumption
        ),
    }


def _now_row(
    timeline: list[dict[str, Any]],
    *,
    selected_hour_local: str | None = None,
) -> dict[str, Any] | None:
    if not timeline:
        return None
    if selected_hour_local:
        for row in timeline:
            if row.get("hour_local") == selected_hour_local:
                return row
        selected_key = hour_bucket(selected_hour_local)
        for row in timeline:
            hour_local = row.get("hour_local")
            if hour_local and hour_bucket(str(hour_local)) == selected_key:
                return row
    now_key = hour_bucket(florida_now())
    for row in timeline:
        hour_local = row.get("hour_local")
        if hour_local and hour_bucket(str(hour_local)) == now_key:
            return row
    return timeline[0]


def _peak_row(timeline: list[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [row for row in timeline if row.get("level") and row["level"] != "unknown"]
    if not usable:
        return None
    return max(
        usable,
        key=lambda row: (
            _LEVEL_RANK.get(row["level"], 0),
            row.get("effective_wbgt_c") if row.get("effective_wbgt_c") is not None else -1,
        ),
    )


def _peak_risk(timeline: list[dict[str, Any]]) -> str:
    row = _peak_row(timeline)
    return row["level"] if row else "unknown"


def _ai_context(
    sites: list[dict[str, Any]],
    workload: Workload,
    actions: list[dict[str, Any]],
    comparison: dict[str, Any],
    at_10: dict[str, Any] | None,
    data_mode: dict[str, Any],
    assumption: dict[str, Any],
) -> dict[str, Any]:
    """Compact structured facts for the explainer — no raw inventable blanks."""
    return {
        "workload": workload,
        "assumption": assumption,
        "data": data_mode,
        "sites": [
            {
                "id": s["id"],
                "name": s.get("name"),
                "now_risk": s.get("now_risk"),
                "now_hour_local": s.get("now_hour_local"),
                "peak_risk": s.get("peak_risk"),
                "peak_hour_local": s.get("peak_hour_local"),
                "current_risk": s.get("current_risk"),
                "hours": [
                    {
                        "hour_local": h["hour_local"],
                        "level": h["level"],
                        "screening_wbgt_c": h.get("screening_wbgt_c"),
                        "effective_wbgt_c": h.get("effective_wbgt_c"),
                        "screening_air_temp_c": h.get("screening_air_temp_c"),
                        "screening_air_temp_source": h.get("screening_air_temp_source"),
                        "temp_c_mean": h.get("temp_c_mean"),
                        "wet_bulb_temperature_celsius": h.get("wet_bulb_temperature_celsius"),
                        "work_rest": (h.get("work_rest") or {}).get("code"),
                        "data_source": h.get("data_source"),
                        "primary_action": (h.get("recommendation") or {}).get("primary_action"),
                    }
                    for h in s.get("hours") or []
                ],
            }
            for s in sites
        ],
        "todays_actions": actions,
        "comparison": comparison,
        "comparison_at_10am": at_10,
    }
