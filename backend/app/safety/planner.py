from __future__ import annotations

from typing import Any

from .recommend import (
    best_windows_for_site,
    build_site_timeline,
    compare_sites_at_hour,
    todays_actions,
)
from .thresholds import SOURCE_CITATION, WORKLOAD_DEFINITIONS, Workload


def build_planner(
    sites: list[dict[str, Any]],
    hours: list[dict[str, Any]],
    workload: Workload = "heavy",
) -> dict[str, Any]:
    by_site_hours: dict[str, list[dict[str, Any]]] = {}
    for row in hours:
        by_site_hours.setdefault(row["site_id"], []).append(row)

    timelines: dict[str, list[dict[str, Any]]] = {}
    site_summaries: list[dict[str, Any]] = []
    all_assessments: list[dict[str, Any]] = []

    for site in sites:
        site_id = site["id"]
        timeline = build_site_timeline(by_site_hours.get(site_id, []), workload)
        timelines[site_id] = timeline
        all_assessments.extend(timeline)

        levels = [r["level"] for r in timeline if r["level"] != "unknown"]
        if not levels:
            current = "unknown"
        elif "red" in levels:
            current = "red"
        elif "amber" in levels:
            current = "amber"
        else:
            current = "green"

        site_summaries.append(
            {
                **{k: site[k] for k in ("id", "name", "city", "surface", "lat", "lon") if k in site},
                "polygon_aoi": site.get("polygon_aoi"),
                "current_risk": current,
                "hours": timeline,
                "best_windows": best_windows_for_site(timeline, site_id),
            }
        )

    comparison = compare_sites_at_hour(all_assessments)
    # Also answer the Day 5 question for ~10:00 if present
    ten_am = next(
        (
            a["hour_local"]
            for a in all_assessments
            if a.get("hour_local") and "T10:" in a["hour_local"]
        ),
        None,
    )
    at_10 = compare_sites_at_hour(all_assessments, hour_local=ten_am) if ten_am else None

    return {
        "workload": workload,
        "workload_definition": WORKLOAD_DEFINITIONS[workload],
        "methodology": {
            "source": SOURCE_CITATION,
            "method": "screening_wbgt_estimate",
            "formula": "0.7*Tw + 0.3*Ta (+0.5°C if solar_ghi≥600)",
            "notes": (
                "Screening estimate only — FortyGuard does not provide globe temperature or wind. "
                "Not a substitute for on-site WBGT monitoring."
            ),
            "doc": "backend/safety/METHODOLOGY.md",
        },
        "sites": site_summaries,
        "todays_actions": todays_actions(timelines, workload),
        "comparison": comparison,
        "comparison_at_10am": at_10,
        "ai_context": _ai_context(site_summaries, workload, todays_actions(timelines, workload), comparison, at_10),
    }


def _ai_context(
    sites: list[dict[str, Any]],
    workload: Workload,
    actions: list[dict[str, Any]],
    comparison: dict[str, Any],
    at_10: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact structured facts for the explainer — no raw inventable blanks."""
    return {
        "workload": workload,
        "sites": [
            {
                "id": s["id"],
                "name": s.get("name"),
                "current_risk": s.get("current_risk"),
                "hours": [
                    {
                        "hour_local": h["hour_local"],
                        "level": h["level"],
                        "screening_wbgt_c": h.get("screening_wbgt_c"),
                        "temp_c_mean": h.get("temp_c_mean"),
                        "wet_bulb_temperature_celsius": h.get("wet_bulb_temperature_celsius"),
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
