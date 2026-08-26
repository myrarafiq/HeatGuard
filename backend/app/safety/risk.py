from __future__ import annotations

from typing import Any

from .thresholds import (
    ACTION_LIMIT_C,
    SOURCE_CITATION,
    TLV_C,
    Workload,
    WorkloadLimits,
)


SOLAR_RADIANT_BUMP_GHI = 600.0
SOLAR_RADIANT_BUMP_C = 0.5


def limits_for(workload: Workload) -> WorkloadLimits:
    return WorkloadLimits(
        workload=workload,
        action_limit_c=ACTION_LIMIT_C[workload],
        tlv_c=TLV_C[workload],
    )


def screening_wbgt_c(
    *,
    wet_bulb_c: float | None,
    air_temp_c: float | None,
    solar_ghi: float | None = None,
) -> float | None:
    """Outdoor screening WBGT estimate when globe temp / wind are unavailable.

    screening_wbgt ≈ 0.7 * Tw + 0.3 * Ta
    Optional +0.5°C when solar_ghi ≥ 600 (documented radiant bump).
    """
    if wet_bulb_c is None or air_temp_c is None:
        return None
    value = 0.7 * float(wet_bulb_c) + 0.3 * float(air_temp_c)
    if solar_ghi is not None and float(solar_ghi) >= SOLAR_RADIANT_BUMP_GHI:
        value += SOLAR_RADIANT_BUMP_C
    return round(value, 2)


def risk_for_wbgt(wbgt_c: float | None, workload: Workload) -> dict[str, Any]:
    limits = limits_for(workload)
    if wbgt_c is None:
        return {
            "level": "unknown",
            "workload": workload,
            "screening_wbgt_c": None,
            "action_limit_c": limits.action_limit_c,
            "tlv_c": limits.tlv_c,
            "method": "screening_wbgt_estimate",
            "source": SOURCE_CITATION,
            "reason": "Missing wet-bulb and/or air temperature — risk not calculated.",
        }

    if wbgt_c < limits.action_limit_c:
        level = "green"
        reason = (
            f"Screening WBGT {wbgt_c:.1f}°C is below the {workload} Action Limit "
            f"({limits.action_limit_c:.0f}°C) for unacclimatized workers."
        )
    elif wbgt_c < limits.tlv_c:
        level = "amber"
        reason = (
            f"Screening WBGT {wbgt_c:.1f}°C is at/above the {workload} Action Limit "
            f"({limits.action_limit_c:.0f}°C) but below the TLV ({limits.tlv_c:.0f}°C)."
        )
    else:
        level = "red"
        reason = (
            f"Screening WBGT {wbgt_c:.1f}°C is at/above the {workload} TLV "
            f"({limits.tlv_c:.0f}°C) for acclimatized workers — outdoor {workload} work "
            f"should be reduced, paused, or rescheduled."
        )

    return {
        "level": level,
        "workload": workload,
        "screening_wbgt_c": wbgt_c,
        "action_limit_c": limits.action_limit_c,
        "tlv_c": limits.tlv_c,
        "method": "screening_wbgt_estimate",
        "source": SOURCE_CITATION,
        "reason": reason,
    }


def assess_hour(hour: dict[str, Any], workload: Workload) -> dict[str, Any]:
    wbgt = screening_wbgt_c(
        wet_bulb_c=hour.get("wet_bulb_temperature_celsius"),
        air_temp_c=hour.get("temp_c_mean"),
        solar_ghi=hour.get("solar_ghi"),
    )
    risk = risk_for_wbgt(wbgt, workload)
    return {
        **risk,
        "site_id": hour.get("site_id"),
        "hour_local": hour.get("hour_local"),
        "temp_c_mean": hour.get("temp_c_mean"),
        "temp_c_min": hour.get("temp_c_min"),
        "temp_c_max": hour.get("temp_c_max"),
        "wet_bulb_temperature_celsius": hour.get("wet_bulb_temperature_celsius"),
        "apparent_temperature_celsius": hour.get("apparent_temperature_celsius"),
        "relative_humidity_percent": hour.get("relative_humidity_percent"),
        "solar_ghi": hour.get("solar_ghi"),
        "temp_c_p90": hour.get("temp_c_p90"),
        "data_source": hour.get("data_source"),
        "heatmap_scope": hour.get("heatmap_scope"),
        "missing_fields": hour.get("missing_fields") or [],
    }
