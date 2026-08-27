from __future__ import annotations

"""Assemble the manager planner JSON from stored hours and published OSHA limits.

Does not call FortyGuard. now_risk is the selected/current hour; peak_risk is
the worst hour in the window. todays_actions is the four-move shift plan.
"""

from typing import Any

from ..db import summarize_data_mode
from ..time_windows import florida_now, hour_bucket
from .recommend import (
    best_windows_for_site,
    build_site_timeline,
    compare_sites_at_hour,
    threshold_flip,
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

        duration_src = next(
            (h for h in by_site_hours.get(site_id, []) if h.get("exceedance_hours_mean") is not None),
            (by_site_hours.get(site_id) or [None])[0],
        ) or {}
        spreads = [
            float(h["tile_spread_c"])
            for h in by_site_hours.get(site_id, [])
            if h.get("tile_spread_c") is not None
        ]

        site_summaries.append(
            {
                **{k: site[k] for k in ("id", "name", "city", "surface", "lat", "lon") if k in site},
                "polygon_aoi": site.get("polygon_aoi"),
                "approx_side_m": site.get("approx_side_m"),
                "heatmap_granularity_m": site.get("heatmap_granularity_m"),
                "now_risk": now_risk,
                "now_hour_local": now_row.get("hour_local") if now_row else None,
                "peak_risk": peak,
                "peak_hour_local": peak_row.get("hour_local") if peak_row else None,
                "current_risk": now_risk,
                "tile_spread_c_max": max(spreads) if spreads else None,
                "exceedance_hours_mean": duration_src.get("exceedance_hours_mean"),
                "persistence_hours_max": duration_src.get("persistence_hours_max"),
                "duration_threshold_c": duration_src.get("duration_threshold_c"),
                "duration_used_in_risk": False,
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
    site_names = {s["id"]: s.get("name") or s["id"] for s in sites if s.get("id")}
    actions = todays_actions(timelines, workload, site_names=site_names)
    contrast = _city_contrast(hours, hour_local=hour_local or ten_am)
    flip = threshold_flip(
        hours,
        workload,
        acclimatized=acclimatized,
        clothing=clothing,
        site_names=site_names,
    )

    return {
        "workload": workload,
        "workload_definition": WORKLOAD_DEFINITIONS[workload],
        "assumption": assumption,
        "data": data_mode,
        "city_contrast": contrast,
        "methodology": {
            "source": SOURCE_CITATION,
            "work_rest_source": WORK_REST_CITATION,
            "method": "screening_wbgt_estimate",
            "heatmap_analytic_type": "tcm",
            "duration_used_in_risk": False,
            "formula": "0.7*Tw + 0.3*Ta_hotspot (+0.5°C if solar_ghi≥600) + clothing CAF",
            "screening_air_temp_order": list(SCREENING_AIR_TEMP_ORDER),
            "notes": (
                "Screening estimate only — FortyGuard does not provide globe temperature or wind. "
                "Not a substitute for on-site WBGT monitoring. "
                "Hourly OSHA input is analytic_type tcm (snapshot) only. "
                "Exceedance/persistence are duration metrics (hours above 30°C air temperature) and are not used in the WBGT estimate. "
                "now_risk is the current or selected hour; peak_risk is the worst hour in the window. "
                "Heat index / apparent temperature / city forecast are display-only and are not used in the WBGT estimate."
            ),
            "doc": "backend/safety/METHODOLOGY.md",
            "twl": {
                "implemented": False,
                "reason": (
                    "Thermal Work Limit needs wind speed and globe temperature. "
                    "FortyGuard provides neither, so TWL is research notes only — "
                    "not a second scoring engine."
                ),
            },
            "feels_like": "apparent_temperature / heat_index are display-only and never drive Green/Amber/Red.",
        },
        "sites": site_summaries,
        "todays_actions": actions,
        "shift_plan": {a["code"]: a for a in actions},
        "threshold_flip": flip,
        "comparison": comparison,
        "comparison_at_10am": at_10,
        "ai_context": _ai_context(
            site_summaries,
            workload,
            actions,
            comparison,
            at_10,
            data_mode,
            assumption,
            contrast,
            flip,
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


def _city_contrast(
    hours: list[dict[str, Any]],
    *,
    hour_local: str | None,
) -> dict[str, Any]:
    """One Miami city reading next to each site mean for the same hour.

    Open-Meteo 2 m air temperature vs FortyGuard TCM site mean. Not an OSHA input.
    """
    note = (
        "City forecast is Open-Meteo Miami 2 m air temperature. "
        "Site values are FortyGuard TCM means for the same hour. Not used in OSHA screening."
    )
    empty = {
        "hour_local": hour_local,
        "city_name": None,
        "city_temp_c": None,
        "city_forecast_source": None,
        "sites": [],
        "hottest_vs_city": None,
        "note": note,
    }
    if not hours:
        return empty

    target = hour_local
    if not target:
        target = next(
            (h.get("hour_local") for h in hours if h.get("city_temp_c") is not None),
            hours[0].get("hour_local"),
        )
    if not target:
        return empty

    key = hour_bucket(str(target))
    matched = [
        h
        for h in hours
        if h.get("hour_local") and hour_bucket(str(h["hour_local"])) == key
    ]
    city_temp = None
    city_name = None
    source = None
    for row in matched:
        if row.get("city_temp_c") is not None:
            city_temp = row.get("city_temp_c")
            city_name = row.get("city_forecast_name")
            source = row.get("city_forecast_source")
            break

    sites: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in matched:
        site_id = row.get("site_id")
        if not site_id or site_id in seen:
            continue
        seen.add(site_id)
        mean = row.get("temp_c_mean")
        delta = row.get("site_minus_city_c")
        if delta is None and mean is not None and city_temp is not None:
            delta = round(float(mean) - float(city_temp), 2)
        sites.append(
            {
                "site_id": site_id,
                "site_name": row.get("site_name"),
                "site_temp_c_mean": mean,
                "tile_spread_c": row.get("tile_spread_c"),
                "temp_c_p90": row.get("temp_c_p90"),
                "temp_c_max": row.get("temp_c_max"),
                "city_temp_c": city_temp,
                "site_minus_city_c": delta,
            }
        )
    sites.sort(
        key=lambda s: (
            s.get("site_minus_city_c") is None,
            -(s.get("site_minus_city_c") or 0),
        )
    )
    return {
        "hour_local": matched[0]["hour_local"] if matched else target,
        "city_name": city_name or "Miami",
        "city_temp_c": city_temp,
        "city_forecast_source": source,
        "sites": sites,
        "hottest_vs_city": sites[0] if sites else None,
        "note": note,
    }


def _ai_context(
    sites: list[dict[str, Any]],
    workload: Workload,
    actions: list[dict[str, Any]],
    comparison: dict[str, Any],
    at_10: dict[str, Any] | None,
    data_mode: dict[str, Any],
    assumption: dict[str, Any],
    city_contrast: dict[str, Any] | None = None,
    threshold_flip_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact structured facts for the explainer — no raw inventable blanks."""
    return {
        "workload": workload,
        "assumption": assumption,
        "data": data_mode,
        "city_contrast": city_contrast,
        "threshold_flip": threshold_flip_doc,
        "todays_actions": actions,
        "sites": [
            {
                "id": s["id"],
                "name": s.get("name"),
                "now_risk": s.get("now_risk"),
                "now_hour_local": s.get("now_hour_local"),
                "peak_risk": s.get("peak_risk"),
                "peak_hour_local": s.get("peak_hour_local"),
                "current_risk": s.get("current_risk"),
                "tile_spread_c_max": s.get("tile_spread_c_max"),
                "exceedance_hours_mean": s.get("exceedance_hours_mean"),
                "persistence_hours_max": s.get("persistence_hours_max"),
                "duration_used_in_risk": False,
                "hours": [
                    {
                        "hour_local": h["hour_local"],
                        "level": h["level"],
                        "screening_wbgt_c": h.get("screening_wbgt_c"),
                        "effective_wbgt_c": h.get("effective_wbgt_c"),
                        "screening_air_temp_c": h.get("screening_air_temp_c"),
                        "screening_air_temp_source": h.get("screening_air_temp_source"),
                        "temp_c_mean": h.get("temp_c_mean"),
                        "temp_c_p90": h.get("temp_c_p90"),
                        "temp_c_max": h.get("temp_c_max"),
                        "tile_spread_c": h.get("tile_spread_c"),
                        "city_temp_c": h.get("city_temp_c"),
                        "site_minus_city_c": h.get("site_minus_city_c"),
                        "wet_bulb_temperature_celsius": h.get("wet_bulb_temperature_celsius"),
                        "feels_like_c": h.get("feels_like_c"),
                        "feels_like_used_in_risk": False,
                        "work_rest": (h.get("work_rest") or {}).get("code"),
                        "data_source": h.get("data_source"),
                        "primary_action": (h.get("recommendation") or {}).get("primary_action"),
                    }
                    for h in s.get("hours") or []
                ],
            }
            for s in sites
        ],
        "comparison": comparison,
        "comparison_at_10am": at_10,
    }
