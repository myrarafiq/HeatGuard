from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import RAW_DIR
from .db import connect, upsert_hour
from .fortyguard_client import FortyGuardClient
from .normalize import extract_heatmap_stats, merge_hour_record
from .sites import Site
from .time_windows import next_hours, single_hour


def fetch_site_hour(
    client: FortyGuardClient,
    site: Site,
    when: datetime,
    *,
    persist: bool = True,
    save_raw: bool = True,
) -> dict[str, Any]:
    date_time = single_hour(when)
    hour_local = when.isoformat()

    try:
        heatmap_id = client.submit_heatmap(site.polygon_aoi, date_time)
        heatmap = client.wait_for_result(heatmap_id)
        stats = extract_heatmap_stats(heatmap)
        temperature = stats.get("temp_c_mean")
        if temperature is None:
            temperature = 32.0

        env_id = client.submit_env_params(site.lat, site.lon, temperature, date_time)
        env = client.wait_for_result(env_id)
    except Exception as exc:  # noqa: BLE001 — persist a failed hour marker for the planner
        record = {
            "site_id": site.id,
            "site_name": site.name,
            "city": site.city,
            "lat": site.lat,
            "lon": site.lon,
            "hour_local": hour_local,
            "temp_c_min": None,
            "temp_c_mean": None,
            "temp_c_max": None,
            "temp_c_stdev": None,
            "tile_count": 0,
            "tile_temperatures_c": [],
            "apparent_temperature_celsius": None,
            "wet_bulb_temperature_celsius": None,
            "relative_humidity_percent": None,
            "heat_index_celsius": None,
            "solar_ghi": None,
            "heatmap_activity_id": None,
            "env_activity_id": None,
            "missing_fields": [
                "temp_c_mean",
                "wet_bulb_temperature_celsius",
                "relative_humidity_percent",
            ],
            "error": str(exc),
        }
        if persist:
            with connect() as conn:
                upsert_hour(conn, record)
        return record

    if save_raw:
        _write_raw(site.id, hour_local, "heatmap", heatmap)
        _write_raw(site.id, hour_local, "env_params", env)

    record = merge_hour_record(
        site_id=site.id,
        hour_local=hour_local,
        heatmap=heatmap,
        env=env,
        heatmap_activity_id=heatmap_id,
        env_activity_id=env_id,
    )
    record["site_name"] = site.name
    record["city"] = site.city
    record["lat"] = site.lat
    record["lon"] = site.lon

    if persist:
        with connect() as conn:
            upsert_hour(conn, record)
    return record


def fetch_site_hours(
    client: FortyGuardClient,
    site: Site,
    start: datetime,
    hours: int = 12,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    return [fetch_site_hour(client, site, hour, **kwargs) for hour in next_hours(start, hours)]


def _write_raw(site_id: str, hour_local: str, kind: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = hour_local.replace(":", "").replace("+", "_")
    path = RAW_DIR / f"{site_id}_{stamp}_{kind}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
