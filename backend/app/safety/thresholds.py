from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Workload = Literal["light", "moderate", "heavy", "very_heavy"]
RiskLevel = Literal["green", "amber", "red", "unknown"]

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


@dataclass(frozen=True)
class WorkloadLimits:
    workload: Workload
    action_limit_c: float
    tlv_c: float
