from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .config import RAW_DIR
from .db import connect, upsert_hour
from .fortyguard_client import FortyGuardClient
from .normalize import heatmap_mean_c, merge_hour_record, split_heatmap_hourly
from .sites import Site
from .time_windows import hour_bucket, hour_range, same_day_hours, single_hour


def fetch_site_hour(
    client: FortyGuardClient,
    site: Site,
    when: datetime,
    **kwargs: Any,
) -> dict[str, Any]:
    return fetch_site_hours(client, site, when, hours=1, **kwargs)[0]


def fetch_site_hours(
    client: FortyGuardClient,
    site: Site,
    start: datetime,
    hours: int = 12,
    *,
    persist: bool = True,
    save_raw: bool = True,
) -> list[dict[str, Any]]:
    """One heatmap job + one env_params job per site (range when hours > 1)."""
    hour_times = same_day_hours(start, hours)
    if not hour_times:
        return []

    date_time = (
        single_hour(hour_times[0])
        if len(hour_times) == 1
        else hour_range(start, len(hour_times))
    )

    heatmap_id: str | None = None
    heatmap: dict[str, Any] | None = None
    heatmap_error: str | None = None
    try:
        heatmap_id = client.submit_heatmap(site.polygon_aoi, date_time)
        heatmap = client.wait_for_result(heatmap_id)
    except Exception as exc:  # noqa: BLE001 — persist unknown hours, never invent temps
        heatmap_error = str(exc)

    temperature = heatmap_mean_c(heatmap) if heatmap and not heatmap_error else None
    skip_env_reason: str | None = None
    if heatmap_error:
        skip_env_reason = f"heatmap_failed: {heatmap_error}"
    elif temperature is None:
        skip_env_reason = "missing_heatmap_temperature"

    env_id: str | None = None
    env: dict[str, Any] | None = None
    env_error: str | None = None
    if skip_env_reason:
        pass
    else:
        assert temperature is not None
        try:
            env_id = client.submit_env_params(site.lat, site.lon, float(temperature), date_time)
            env = client.wait_for_result(env_id)
        except Exception as exc:  # noqa: BLE001
            env_error = str(exc)

    if save_raw:
        stamp = hour_times[0].isoformat()
        if heatmap is not None:
            _write_raw(site.id, stamp, "heatmap", heatmap)
        if env is not None:
            _write_raw(site.id, stamp, "env_params", env)

    by_hour_heatmap = split_heatmap_hourly(heatmap) if heatmap else {}
    heatmap_scope = "hour" if by_hour_heatmap or len(hour_times) == 1 else "range"

    records: list[dict[str, Any]] = []
    for when in hour_times:
        hour_local = when.isoformat()
        hour_heatmap = heatmap
        scope = heatmap_scope
        if by_hour_heatmap:
            matched = by_hour_heatmap.get(hour_bucket(hour_local))
            if matched is not None:
                hour_heatmap = matched
                scope = "hour"
            else:
                hour_heatmap = heatmap
                scope = "range"

        if heatmap_error or hour_heatmap is None:
            record = _unknown_hour(
                site,
                hour_local,
                error=heatmap_error or "heatmap_unavailable",
            )
        else:
            record = merge_hour_record(
                site_id=site.id,
                hour_local=hour_local,
                heatmap=hour_heatmap,
                env=env,
                heatmap_activity_id=heatmap_id,
                env_activity_id=env_id,
                heatmap_scope=scope,
                data_source="live",
            )
            record["site_name"] = site.name
            record["city"] = site.city
            record["lat"] = site.lat
            record["lon"] = site.lon
            if skip_env_reason:
                record["env_skipped"] = skip_env_reason
            if env_error:
                record["error"] = env_error
            if temperature is None:
                record.setdefault("error", skip_env_reason)

        records.append(record)
        if persist:
            with connect() as conn:
                upsert_hour(conn, record)

    return records


def _unknown_hour(site: Site, hour_local: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "site_id": site.id,
        "site_name": site.name,
        "city": site.city,
        "lat": site.lat,
        "lon": site.lon,
        "hour_local": hour_local,
        "temp_c_min": None,
        "temp_c_mean": None,
        "temp_c_max": None,
        "temp_c_p90": None,
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
        "heatmap_scope": "hour",
        "data_source": "live",
        "missing_fields": [
            "temp_c_mean",
            "wet_bulb_temperature_celsius",
            "relative_humidity_percent",
        ],
        "error": error,
        "env_skipped": "missing_heatmap_temperature",
    }


def _write_raw(site_id: str, hour_local: str, kind: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = hour_local.replace(":", "").replace("+", "_")
    path = RAW_DIR / f"{site_id}_{stamp}_{kind}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
