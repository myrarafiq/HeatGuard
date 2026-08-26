from __future__ import annotations

from typing import Any

from .thresholds import (
    ACTION_LIMIT_C,
    DEFAULT_ACCLIMATIZED,
    DEFAULT_CLOTHING,
    SCREENING_AIR_TEMP_ORDER,
    SOURCE_CITATION,
    TLV_C,
    ClothingId,
    Workload,
    WorkloadLimits,
    clothing_adjustment_c,
    work_rest_for,
)


SOLAR_RADIANT_BUMP_GHI = 600.0
SOLAR_RADIANT_BUMP_C = 0.5


def limits_for(workload: Workload) -> WorkloadLimits:
    return WorkloadLimits(
        workload=workload,
        action_limit_c=ACTION_LIMIT_C[workload],
        tlv_c=TLV_C[workload],
    )


def screening_air_temp_c(hour: dict[str, Any]) -> tuple[float | None, str]:
    """Conservative HSE air temperature: hotspot first, mean only as fallback.

    Order (written down, not tuned): temp_c_p90 → temp_c_max → temp_c_mean.
    """
    for key in SCREENING_AIR_TEMP_ORDER:
        value = hour.get(key)
        if value is not None:
            return float(value), key
    return None, "missing"


def feels_like_display(hour: dict[str, Any]) -> tuple[float | None, str | None]:
    """Workers-feel layer. Never used as Ta in the WBGT screening formula."""
    apparent = hour.get("apparent_temperature_celsius")
    if apparent is not None:
        return float(apparent), "apparent_temperature_celsius"
    heat_index = hour.get("heat_index_celsius")
    if heat_index is not None:
        return float(heat_index), "heat_index_celsius"
    return None, None


def screening_wbgt_c(
    *,
    wet_bulb_c: float | None,
    air_temp_c: float | None,
    solar_ghi: float | None = None,
) -> float | None:
    """Outdoor screening WBGT estimate when globe temp / wind are unavailable.

    screening_wbgt ≈ 0.7 * Tw + 0.3 * Ta
    Optional +0.5°C when solar_ghi ≥ 600 (documented radiant bump).
    Apparent temperature / heat index are display-only and must not be passed as Ta.
    """
    if wet_bulb_c is None or air_temp_c is None:
        return None
    value = 0.7 * float(wet_bulb_c) + 0.3 * float(air_temp_c)
    if solar_ghi is not None and float(solar_ghi) >= SOLAR_RADIANT_BUMP_GHI:
        value += SOLAR_RADIANT_BUMP_C
    return round(value, 2)


def risk_for_wbgt(
    wbgt_c: float | None,
    workload: Workload,
    *,
    acclimatized: bool = DEFAULT_ACCLIMATIZED,
) -> dict[str, Any]:
    limits = limits_for(workload)
    crew = "acclimatized" if acclimatized else "unacclimatized"
    if wbgt_c is None:
        return {
            "level": "unknown",
            "workload": workload,
            "acclimatized": acclimatized,
            "screening_wbgt_c": None,
            "effective_wbgt_c": None,
            "action_limit_c": limits.action_limit_c,
            "tlv_c": limits.tlv_c,
            "method": "screening_wbgt_estimate",
            "source": SOURCE_CITATION,
            "reason": "Missing wet-bulb and/or air temperature — risk not calculated.",
        }

    if acclimatized:
        # TLV is the red line. No earlier amber trip — Action Limit is for unacclimatized crews.
        if wbgt_c < limits.tlv_c:
            level = "green"
            reason = (
                f"Effective WBGT {wbgt_c:.1f}°C is below the {workload} TLV "
                f"({limits.tlv_c:.0f}°C) for acclimatized workers."
            )
        else:
            level = "red"
            reason = (
                f"Effective WBGT {wbgt_c:.1f}°C is at/above the {workload} TLV "
                f"({limits.tlv_c:.0f}°C) for acclimatized workers — outdoor {workload} work "
                f"should be reduced, paused, or rescheduled."
            )
    elif wbgt_c < limits.action_limit_c:
        level = "green"
        reason = (
            f"Effective WBGT {wbgt_c:.1f}°C is below the {workload} Action Limit "
            f"({limits.action_limit_c:.0f}°C) for unacclimatized workers."
        )
    elif wbgt_c < limits.tlv_c:
        level = "amber"
        reason = (
            f"Effective WBGT {wbgt_c:.1f}°C is at/above the {workload} Action Limit "
            f"({limits.action_limit_c:.0f}°C) but below the TLV ({limits.tlv_c:.0f}°C) "
            f"({crew} crew)."
        )
    else:
        level = "red"
        reason = (
            f"Effective WBGT {wbgt_c:.1f}°C is at/above the {workload} TLV "
            f"({limits.tlv_c:.0f}°C). Planning assumes mixed/unacclimatized crews, "
            f"so this is past both the Action Limit and the TLV."
        )

    return {
        "level": level,
        "workload": workload,
        "acclimatized": acclimatized,
        "screening_wbgt_c": wbgt_c,
        "effective_wbgt_c": wbgt_c,
        "action_limit_c": limits.action_limit_c,
        "tlv_c": limits.tlv_c,
        "method": "screening_wbgt_estimate",
        "source": SOURCE_CITATION,
        "reason": reason,
    }


def assess_hour(
    hour: dict[str, Any],
    workload: Workload,
    *,
    acclimatized: bool = DEFAULT_ACCLIMATIZED,
    clothing: ClothingId | str = DEFAULT_CLOTHING,
) -> dict[str, Any]:
    hotspot_c, hotspot_source = screening_air_temp_c(hour)
    mean_c = hour.get("temp_c_mean")
    mean_c = float(mean_c) if mean_c is not None else None
    wet_bulb = hour.get("wet_bulb_temperature_celsius")
    solar = hour.get("solar_ghi")

    hotspot_wbgt = screening_wbgt_c(
        wet_bulb_c=wet_bulb,
        air_temp_c=hotspot_c,
        solar_ghi=solar,
    )
    mean_wbgt = screening_wbgt_c(
        wet_bulb_c=wet_bulb,
        air_temp_c=mean_c,
        solar_ghi=solar,
    )
    caf = clothing_adjustment_c(clothing)
    effective = None if hotspot_wbgt is None else round(hotspot_wbgt + caf, 2)
    feels_c, feels_source = feels_like_display(hour)

    risk = risk_for_wbgt(effective, workload, acclimatized=acclimatized)
    work_rest = work_rest_for(effective, workload, acclimatized=acclimatized)
    return {
        **risk,
        "site_id": hour.get("site_id"),
        "hour_local": hour.get("hour_local"),
        "temp_c_mean": hour.get("temp_c_mean"),
        "temp_c_min": hour.get("temp_c_min"),
        "temp_c_max": hour.get("temp_c_max"),
        "temp_c_p90": hour.get("temp_c_p90"),
        "screening_air_temp_c": hotspot_c,
        "screening_air_temp_source": hotspot_source,
        "screening_wbgt_c": hotspot_wbgt,
        "screening_wbgt_from_mean_c": mean_wbgt,
        "clothing": clothing,
        "clothing_adjustment_c": caf,
        "effective_wbgt_c": effective,
        "apparent_temperature_celsius": hour.get("apparent_temperature_celsius"),
        "wet_bulb_temperature_celsius": hour.get("wet_bulb_temperature_celsius"),
        "relative_humidity_percent": hour.get("relative_humidity_percent"),
        "heat_index_celsius": hour.get("heat_index_celsius"),
        "feels_like_c": feels_c,
        "feels_like_source": feels_source,
        "feels_like_used_in_risk": False,
        "solar_ghi": hour.get("solar_ghi"),
        "tile_spread_c": hour.get("tile_spread_c"),
        "city_temp_c": hour.get("city_temp_c"),
        "site_minus_city_c": hour.get("site_minus_city_c"),
        "exceedance_hours_mean": hour.get("exceedance_hours_mean"),
        "persistence_hours_max": hour.get("persistence_hours_max"),
        "duration_used_in_risk": hour.get("duration_used_in_risk", False),
        "work_rest": work_rest,
        "data_source": hour.get("data_source"),
        "heatmap_scope": hour.get("heatmap_scope"),
        "missing_fields": hour.get("missing_fields") or [],
    }
