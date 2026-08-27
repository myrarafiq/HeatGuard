from __future__ import annotations

"""Backup 12-hour Miami workday used when a live FortyGuard pull is unavailable.

Peak-hour temperatures come from a real FortyGuard pull. Other hours follow a
smooth diurnal curve so the dashboard still has a full 06:00–17:00 story.
The calendar stamp is 26 August 2026 so the hosted demo matches judging.
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.config import ROOT
from backend.app.db import clear_hours, connect, upsert_hour
from backend.app.sites import load_sites

FIXTURES_PATH = ROOT / "backend" / "data" / "fixtures" / "demo_day.json"

# Peak-hour temps from a live FortyGuard pull. Other hours are a diurnal curve.
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
        "temp_c_min": 31.05,
        "temp_c_max": 33.25,
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
    """°C offset vs 2:00 PM peak. Morning is cooler so heavy work can start green."""
    # Keep 2:00 PM pinned to the live FortyGuard peak-hour temps (offset ≈ 0).
    return 5.0 * math.cos((hour - 14) / 12 * math.pi) - 5.0


def build_demo_day(
    start: datetime | None = None,
    hours: int = 12,
) -> list[dict[str, Any]]:
    tz = ZoneInfo("America/New_York")
    if start is None:
        start = datetime(2026, 8, 26, 6, 0, tzinfo=tz)
    sites = {s.id: s for s in load_sites()}
    rows: list[dict[str, Any]] = []
    for site_id, anchor in LIVE_ANCHORS.items():
        site = sites.get(site_id)
        for i in range(hours):
            when = start + timedelta(hours=i)
            off = _diurnal_offset(when.hour)
            solar_scale = max(0.05, math.cos((when.hour - 13) / 10 * math.pi))
            temp = round(anchor["temp_c_mean"] + off, 2)
            tmin = round(anchor["temp_c_min"] + off, 2)
            tmax = round(anchor["temp_c_max"] + off, 2)
            tw = round(anchor["wet_bulb_temperature_celsius"] + off * 0.55, 2)
            city_temp = round(31.0 + off * 0.85, 2)
            record = {
                "site_id": site_id,
                "site_name": site.name if site else site_id,
                "city": site.city if site else "",
                "lat": site.lat if site else None,
                "lon": site.lon if site else None,
                "hour_local": when.isoformat(),
                "temp_c_min": tmin,
                "temp_c_mean": temp,
                "temp_c_max": tmax,
                "temp_c_p90": round(tmin + 0.85 * (tmax - tmin), 2),
                "temp_c_stdev": round(max(0.05, (tmax - tmin) / 3), 2),
                "tile_spread_c": round(tmax - tmin, 2),
                "tile_count": 16 if site_id == "doral" else 9,
                "tile_temperatures_c": [tmin, temp, tmax],
                "apparent_temperature_celsius": round(anchor["apparent_temperature_celsius"] + off, 2),
                "wet_bulb_temperature_celsius": tw,
                "relative_humidity_percent": anchor["relative_humidity_percent"],
                "heat_index_celsius": None,
                "solar_ghi": round(anchor["solar_ghi"] * solar_scale, 1),
                "city_temp_c": city_temp,
                "city_forecast_source": "open-meteo",
                "city_forecast_name": "Miami",
                "site_minus_city_c": round(temp - city_temp, 2),
                "heatmap_activity_id": "fixture",
                "env_activity_id": "fixture",
                "heatmap_analytic_type": "tcm",
                "api_timestamp": when.isoformat(),
                "missing_fields": [],
                "source": "demo_fixture_from_live_1400_anchors",
                "data_source": "fixture",
                "heatmap_scope": "hour",
                "duration_used_in_risk": False,
                "duration_threshold_c": 30.0,
            }
            rows.append(record)
        _stamp_duration(rows, site_id)
    return rows


def _stamp_duration(rows: list[dict[str, Any]], site_id: str, threshold: float = 30.0) -> None:
    site_rows = [row for row in rows if row["site_id"] == site_id]
    above = [1 if (row.get("temp_c_mean") or 0) > threshold else 0 for row in site_rows]
    exceedance = sum(above)
    longest = 0
    run = 0
    for flag in above:
        if flag:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    for row in site_rows:
        row["exceedance_hours_mean"] = float(exceedance)
        row["exceedance_hours_max"] = float(exceedance)
        row["persistence_hours_max"] = float(longest)


def write_fixtures(path: Path | None = None) -> Path:
    out = path or FIXTURES_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_demo_day()
    payload = {
        "description": (
            "12-hour demo day for Miami sites, stamped 2026-08-26. Peak-hour temps at 14:00 "
            "use live FortyGuard values for brickell/miami_beach/doral; coconut_grove/little_haiti "
            "interpolated between coastal and inland. Diurnal curve is synthetic for demo resilience. "
            "Doral includes a within-site hotspot (~2°C tile spread). Each hour stores Miami city "
            "temperature (Open-Meteo-shaped) vs site mean, plus exceedance/persistence hours above 30°C."
        ),
        "hours": rows,
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


def load_fixtures_into_db(path: Path | None = None, *, replace: bool = True) -> int:
    """Load backup demo hours.

    replace=True (default) clears existing rows first so live and fixture data
    are never mixed silently.
    """
    fixture_path = path or FIXTURES_PATH
    if not fixture_path.exists():
        write_fixtures(fixture_path)
    data = json.loads(fixture_path.read_text())
    rows = data["hours"] if isinstance(data, dict) else data
    with connect() as conn:
        if replace:
            clear_hours(conn)
        for row in rows:
            stored = dict(row)
            stored["data_source"] = "fixture"
            upsert_hour(conn, stored)
    return len(rows)
