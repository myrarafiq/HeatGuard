from __future__ import annotations

"""Published OSHA / NIOSH / ACGIH numbers used by HeatGuard.

AL = Action Limit (unacclimatized / new hires).
TLV = Threshold Limit Value (acclimatized).
CAF = clothing adjustment factor, added to screening WBGT before Table 2.
Do not invent or tune these values.
"""

from dataclasses import dataclass
from typing import Any, Literal

Workload = Literal["light", "moderate", "heavy", "very_heavy"]
RiskLevel = Literal["green", "amber", "red", "unknown"]
Acclimatization = Literal["unacclimatized", "acclimatized"]
ClothingId = Literal[
    "work_clothes",
    "cloth_coveralls",
    "sms_coveralls",
    "polyolefin_coveralls",
    "double_layer",
    "vapor_barrier",
]

# NIOSH / ACGIH via OSHA Heat Hazard Recognition Table 2 — effective WBGT °C.
# Do not invent or "tune" these numbers.
ACTION_LIMIT_C: dict[Workload, float] = {
    "light": 28.0,
    "moderate": 25.0,
    "heavy": 23.0,
    "very_heavy": 21.0,
}
TLV_C: dict[Workload, float] = {
    "light": 30.0,
    "moderate": 28.0,
    "heavy": 26.0,
    "very_heavy": 25.0,
}

WORKLOAD_DEFINITIONS: dict[Workload, dict[str, object]] = {
    "light": {
        "label": "Light",
        "osha_examples": [
            "Standing watch",
            "Slow / occasional walking",
            "Sitting with minimal hand/arm work",
        ],
        "construction_examples": [
            "Site supervision / observation",
            "Light layout marking",
            "Tool crib standing tasks",
        ],
        "metabolic_watts_typical": 180,
    },
    "moderate": {
        "label": "Moderate",
        "osha_examples": [
            "Continuous normal walking",
            "General carpentry with hand tools",
            "Painting / plastering",
            "Pushing light carts",
        ],
        "construction_examples": [
            "General carpentry",
            "Interior finishing",
            "Material staging with light carts",
        ],
        "metabolic_watts_typical": 300,
    },
    "heavy": {
        "label": "Heavy",
        "osha_examples": [
            "Carrying loads",
            "Shoveling",
            "Roofing",
            "Mixing cement",
            "Stacking lumber",
            "Drilling concrete",
        ],
        "construction_examples": [
            "Formwork / rebar handling",
            "Roofing",
            "Concrete placement support",
            "Heavy material carrying",
        ],
        "metabolic_watts_typical": 415,
    },
    "very_heavy": {
        "label": "Very heavy",
        "osha_examples": [
            "Intense digging / shoveling",
            "Climbing stairs/ladders with loads",
            "Near-maximum pace work",
        ],
        "construction_examples": [
            "Hand excavation at pace",
            "Loaded ladder climbs",
        ],
        "metabolic_watts_typical": 520,
    },
}

# Recommended outdoor midday pause window (local clock). Not Florida law.
MIDDAY_BREAK_START = (12, 30)
MIDDAY_BREAK_END = (15, 0)

SOURCE_CITATION = (
    "OSHA Heat Hazard Recognition / NIOSH–ACGIH effective WBGT limits "
    "(https://www.osha.gov/heat-exposure/hazards)"
)

WORK_REST_CITATION = (
    "ACGIH Screening Criteria for Heat Stress Exposure (WBGT °C), "
    "reproduced in NIOSH/OSHA heat guidance. Work minutes are the "
    "protective end of each published allocation band: "
    "75%→45/15, 50%→30/30, 25%→15/45, 0–25%→stop."
)

# Screening air temperature: hottest occupied area, not the site average.
# Preference order is written down so HSE screening is conservative and reproducible.
SCREENING_AIR_TEMP_ORDER = ("temp_c_p90", "temp_c_max", "temp_c_mean")

DEFAULT_ACCLIMATIZED = False
DEFAULT_CLOTHING: ClothingId = "work_clothes"
# Optional dashboard flag. Exact OSHA clothing-table row (not an invented bump):
# SMS polypropylene coveralls, +0.5°C added to WBGT before Table 2.
# Cotton/cloth coveralls are +0°C on the same table — we do not pretend they add heat.
EXTRA_PPE_CLOTHING: ClothingId = "sms_coveralls"

# OSHA Heat Hazard Recognition — clothing adjustment factors (°C) added to WBGT
# to obtain effective WBGT. Adapted from NIOSH 2016. Do not invent these numbers.
CLOTHING_ADJUSTMENT_C: dict[ClothingId, dict[str, Any]] = {
    "work_clothes": {
        "label": "Work clothing (baseline)",
        "adjustment_c": 0.0,
    },
    "cloth_coveralls": {
        "label": "Cloth coveralls",
        "adjustment_c": 0.0,
    },
    "sms_coveralls": {
        "label": "SMS polypropylene coveralls",
        "adjustment_c": 0.5,
    },
    "polyolefin_coveralls": {
        "label": "Polyolefin coveralls",
        "adjustment_c": 1.0,
    },
    "double_layer": {
        "label": "Double-layer cloth clothing",
        "adjustment_c": 3.0,
    },
    "vapor_barrier": {
        "label": "Limited-use vapor-barrier coveralls",
        "adjustment_c": 11.0,
    },
}

# ACGIH screening criteria (WBGT °C). None = published dash (that allocation is not listed).
# Rows are most work → least work. Unacclimatized = Action Limit columns; acclimatized = TLV columns.
ACGIH_ALLOCATION_LIMITS_C: dict[bool, dict[Workload, list[tuple[float | None, str, str]]]] = {
    False: {
        "light": [
            (28.0, "45/15", "75–100% work"),
            (28.5, "30/30", "50–75% work"),
            (29.5, "15/45", "25–50% work"),
            (30.0, "stop", "0–25% work"),
        ],
        "moderate": [
            (25.0, "45/15", "75–100% work"),
            (26.0, "30/30", "50–75% work"),
            (27.0, "15/45", "25–50% work"),
            (29.0, "stop", "0–25% work"),
        ],
        "heavy": [
            (None, "45/15", "75–100% work"),
            (24.0, "30/30", "50–75% work"),
            (25.5, "15/45", "25–50% work"),
            (28.0, "stop", "0–25% work"),
        ],
        "very_heavy": [
            (None, "45/15", "75–100% work"),
            (None, "30/30", "50–75% work"),
            (24.5, "15/45", "25–50% work"),
            (27.0, "stop", "0–25% work"),
        ],
    },
    True: {
        "light": [
            (31.0, "45/15", "75–100% work"),
            (31.0, "30/30", "50–75% work"),
            (32.0, "15/45", "25–50% work"),
            (32.5, "stop", "0–25% work"),
        ],
        "moderate": [
            (28.0, "45/15", "75–100% work"),
            (29.0, "30/30", "50–75% work"),
            (30.0, "15/45", "25–50% work"),
            (31.5, "stop", "0–25% work"),
        ],
        "heavy": [
            (None, "45/15", "75–100% work"),
            (27.5, "30/30", "50–75% work"),
            (29.0, "15/45", "25–50% work"),
            (30.5, "stop", "0–25% work"),
        ],
        "very_heavy": [
            (None, "45/15", "75–100% work"),
            (None, "30/30", "50–75% work"),
            (28.0, "15/45", "25–50% work"),
            (30.0, "stop", "0–25% work"),
        ],
    },
}

WORK_REST_MINUTES: dict[str, tuple[int, int]] = {
    "45/15": (45, 15),
    "30/30": (30, 30),
    "15/45": (15, 45),
    "stop": (0, 60),
}


def resolve_clothing(
    clothing: ClothingId | str | None = None,
    extra_ppe: bool = False,
) -> ClothingId | str:
    """Map the optional coveralls flag to the cited OSHA clothing-table row."""
    chosen: ClothingId | str = clothing or DEFAULT_CLOTHING
    if extra_ppe and chosen == DEFAULT_CLOTHING:
        return EXTRA_PPE_CLOTHING
    return chosen


def clothing_adjustment_c(clothing: ClothingId | str) -> float:
    row = CLOTHING_ADJUSTMENT_C.get(clothing)  # type: ignore[arg-type]
    if row is None:
        return CLOTHING_ADJUSTMENT_C[DEFAULT_CLOTHING]["adjustment_c"]
    return float(row["adjustment_c"])


def work_rest_for(
    effective_wbgt_c: float | None,
    workload: Workload,
    *,
    acclimatized: bool,
) -> dict[str, Any]:
    """Map effective WBGT to the least-restrictive published ACGIH allocation that still covers it."""
    if effective_wbgt_c is None:
        return {
            "code": "unknown",
            "work_min": None,
            "rest_min": None,
            "allocation": None,
            "limit_c": None,
            "source": WORK_REST_CITATION,
        }

    rows = ACGIH_ALLOCATION_LIMITS_C[acclimatized][workload]
    for limit_c, code, allocation in rows:
        if limit_c is None:
            continue
        if float(effective_wbgt_c) <= float(limit_c):
            work_min, rest_min = WORK_REST_MINUTES[code]
            return {
                "code": code,
                "work_min": work_min,
                "rest_min": rest_min,
                "allocation": allocation,
                "limit_c": limit_c,
                "source": WORK_REST_CITATION,
            }
    work_min, rest_min = WORK_REST_MINUTES["stop"]
    return {
        "code": "stop",
        "work_min": work_min,
        "rest_min": rest_min,
        "allocation": "above 0–25% screening allocation",
        "limit_c": None,
        "source": WORK_REST_CITATION,
    }


def planning_assumption(*, acclimatized: bool, clothing: ClothingId | str) -> dict[str, Any]:
    clothing_row = CLOTHING_ADJUSTMENT_C.get(clothing) or CLOTHING_ADJUSTMENT_C[DEFAULT_CLOTHING]
    if acclimatized:
        label = (
            "Planning assumption: acclimatized crew. "
            "TLV is the red line (Action Limit is not used as an earlier amber trip)."
        )
        caution = "tlv"
    else:
        label = (
            "Planning assumption: unacclimatized / new hires present. "
            "Action Limit is the amber trip; TLV is the red line."
        )
        caution = "action_limit"
    extra_ppe = str(clothing) != DEFAULT_CLOTHING
    return {
        "acclimatized": acclimatized,
        "crew": "acclimatized" if acclimatized else "unacclimatized",
        "label": label,
        "caution_limit": caution,
        "red_line": "tlv",
        "clothing": clothing,
        "clothing_label": clothing_row["label"],
        "clothing_adjustment_c": float(clothing_row["adjustment_c"]),
        "extra_ppe": extra_ppe,
        "extra_ppe_flag_clothing": EXTRA_PPE_CLOTHING,
        "extra_ppe_flag_label": CLOTHING_ADJUSTMENT_C[EXTRA_PPE_CLOTHING]["label"],
        "extra_ppe_flag_adjustment_c": float(
            CLOTHING_ADJUSTMENT_C[EXTRA_PPE_CLOTHING]["adjustment_c"]
        ),
        "clothing_source": SOURCE_CITATION,
        "screening_air_temp": (
            "Hotspot (temp_c_p90, else temp_c_max, else temp_c_mean). "
            "Site mean is kept for comparison only."
        ),
        "source": SOURCE_CITATION,
        "work_rest_source": WORK_REST_CITATION,
    }


@dataclass(frozen=True)
class WorkloadLimits:
    workload: Workload
    action_limit_c: float
    tlv_c: float
