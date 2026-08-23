from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.config import ROOT
from backend.app.db import connect, upsert_hour
from backend.app.sites import load_sites

FIXTURES_PATH = ROOT / "backend" / "data" / "fixtures" / "demo_day.json"

# Anchors from live FortyGuard pull 2024-07-15 14:00 (America/New_York).
LIVE_ANCHORS: dict[str, dict[str, float]] = {
    "brickell": {
        "temp_c_mean": 31.26,
        "temp_c_min": 31.18,
        "temp_c_max": 31.34,
        "wet_bulb_temperature_celsius": 26.1,
        "relative_humidity_percent": 76.3,
        "apparent_temperature_celsius": 34.2,
        "solar_ghi": 844.0,
    },
    "miami_beach": {
        "temp_c_mean": 30.84,
        "temp_c_min": 30.84,
        "temp_c_max": 30.84,
        "wet_bulb_temperature_celsius": 26.0,
        "relative_humidity_percent": 71.8,
        "apparent_temperature_celsius": 33.5,
        "solar_ghi": 850.0,
    },
    "doral": {
        "temp_c_mean": 32.11,
        "temp_c_min": 32.11,
        "temp_c_max": 32.11,
        "wet_bulb_temperature_celsius": 26.4,
        "relative_humidity_percent": 72.3,
        "apparent_temperature_celsius": 35.0,
        "solar_ghi": 860.0,
    },
    "coconut_grove": {
        "temp_c_mean": 30.95,
        "temp_c_min": 30.70,
        "temp_c_max": 31.20,
        "wet_bulb_temperature_celsius": 25.8,
        "relative_humidity_percent": 74.0,
        "apparent_temperature_celsius": 33.8,
        "solar_ghi": 820.0,
    },
    "little_haiti": {
        "temp_c_mean": 31.70,
        "temp_c_min": 31.50,
        "temp_c_max": 31.90,
        "wet_bulb_temperature_celsius": 26.2,
        "relative_humidity_percent": 75.0,
        "apparent_temperature_celsius": 34.6,
        "solar_ghi": 840.0,
    },
}


def _diurnal_offset(hour: int) -> float:
    """°C offset vs 14:00 peak — cooler morning/evening."""
    # cosine peak near 14–15
    return 3.2 * math.cos((hour - 14) / 12 * math.pi) - 3.2


def build_demo_day(
    start: datetime | None = None,
    hours: int = 12,
) -> list[dict[str, Any]]:
    tz = ZoneInfo("America/New_York")
    if start is None:
        start = datetime(2024, 7, 15, 6, 0, tzinfo=tz)
    sites = {s.id: s for s in load_sites()}
    rows: list[dict[str, Any]] = []
    for site_id, anchor in LIVE_ANCHORS.items():
        site = sites.get(site_id)
        for i in range(hours):
            when = start + timedelta(hours=i)
            off = _diurnal_offset(when.hour)
            solar_scale = max(0.05, math.cos((when.hour - 13) / 10 * math.pi))
            temp = round(anchor["temp_c_mean"] + off, 2)
            tw = round(anchor["wet_bulb_temperature_celsius"] + off * 0.45, 2)
            record = {
                "site_id": site_id,
                "site_name": site.name if site else site_id,
                "city": site.city if site else "",
                "lat": site.lat if site else None,
                "lon": site.lon if site else None,
                "hour_local": when.isoformat(),
                "temp_c_min": round(anchor["temp_c_min"] + off, 2),
                "temp_c_mean": temp,
                "temp_c_max": round(anchor["temp_c_max"] + off, 2),
                "temp_c_stdev": 0.08,
                "tile_count": 9 if site_id == "brickell" else 3,
                "tile_temperatures_c": [temp],
                "apparent_temperature_celsius": round(anchor["apparent_temperature_celsius"] + off, 2),
                "wet_bulb_temperature_celsius": tw,
                "relative_humidity_percent": anchor["relative_humidity_percent"],
                "heat_index_celsius": None,
                "solar_ghi": round(anchor["solar_ghi"] * solar_scale, 1),
                "heatmap_activity_id": "fixture",
                "env_activity_id": "fixture",
                "api_timestamp": when.isoformat(),
                "missing_fields": [],
                "source": "demo_fixture_from_live_1400_anchors",
            }
            rows.append(record)
    return rows


def write_fixtures(path: Path | None = None) -> Path:
    out = path or FIXTURES_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_demo_day()
    payload = {
        "description": (
            "12-hour demo day for Miami sites. Anchors at 14:00 use live FortyGuard values "
            "from 2024-07-15 for brickell/miami_beach/doral; coconut_grove/little_haiti "
            "interpolated between coastal and inland. Diurnal curve is synthetic for demo resilience."
        ),
        "hours": rows,
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


def load_fixtures_into_db(path: Path | None = None) -> int:
    fixture_path = path or FIXTURES_PATH
    if not fixture_path.exists():
        write_fixtures(fixture_path)
    data = json.loads(fixture_path.read_text())
    rows = data["hours"] if isinstance(data, dict) else data
    with connect() as conn:
        for row in rows:
            upsert_hour(conn, row)
    return len(rows)
