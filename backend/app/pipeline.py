from __future__ import annotations

"""Pull FortyGuard heatmaps and environmental parameters, then store hourly rows.

Each site gets one TCM (snapshot) heatmap plus env_params. Missing heatmap
temperature is stored as unknown — we never invent a site temperature.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from .city_forecast import city_temp_for_hour, fetch_city_hourly
from .config import (
    DURATION_THRESHOLD_C,
    ENABLE_DURATION_METRICS,
    FETCH_MAX_WORKERS,
    HEATMAP_ANALYTIC_RISK,
    HEATMAP_GRANULARITY_M,
    RAW_DIR,
)
from .db import connect, upsert_hour
from .fortyguard_client import FortyGuardClient
from .normalize import extract_duration_hours, heatmap_mean_c, merge_hour_record, split_heatmap_hourly
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
    duration_metrics: bool | None = None,
    city_forecast: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """One TCM heatmap (risk) + one env_params job per site.

    Exceedance/persistence are optional second metrics — never used as OSHA inputs.
    """
    hour_times = same_day_hours(start, hours)
    if not hour_times:
        return []

    date_time = (
        single_hour(hour_times[0])
        if len(hour_times) == 1
        else hour_range(start, len(hour_times))
    )
    use_duration = ENABLE_DURATION_METRICS if duration_metrics is None else duration_metrics

    heatmap_id: str | None = None
    heatmap: dict[str, Any] | None = None
    heatmap_error: str | None = None
    try:
        heatmap_id = client.submit_heatmap(
            site.polygon_aoi,
            date_time,
            granularity=HEATMAP_GRANULARITY_M,
            analytic_type=HEATMAP_ANALYTIC_RISK,
        )
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
    if not skip_env_reason:
        assert temperature is not None
        try:
            env_id = client.submit_env_params(site.lat, site.lon, float(temperature), date_time)
            env = client.wait_for_result(env_id)
        except Exception as exc:  # noqa: BLE001
            env_error = str(exc)

    duration = (
        _fetch_duration_metrics(client, site, date_time)
        if use_duration and not heatmap_error
        else {
            "exceedance_hours_mean": None,
            "exceedance_hours_max": None,
            "persistence_hours_max": None,
            "duration_threshold_c": DURATION_THRESHOLD_C,
            "duration_used_in_risk": False,
        }
    )

    if city_forecast is None:
        city_forecast = fetch_city_hourly(start, len(hour_times))

    if save_raw:
        stamp = hour_times[0].isoformat()
        if heatmap is not None:
            _write_raw(site.id, stamp, "heatmap_tcm", heatmap)
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
            record["heatmap_analytic_type"] = HEATMAP_ANALYTIC_RISK
            record["heatmap_granularity_m"] = HEATMAP_GRANULARITY_M
            if skip_env_reason:
                record["env_skipped"] = skip_env_reason
            if env_error:
                record["error"] = env_error
            if temperature is None:
                record.setdefault("error", skip_env_reason)

        city_temp = city_temp_for_hour(city_forecast, hour_local)
        record["city_temp_c"] = city_temp
        record["city_forecast_source"] = city_forecast.get("source") if city_temp is not None else None
        record["city_forecast_name"] = city_forecast.get("name")
        if city_temp is not None and record.get("temp_c_mean") is not None:
            record["site_minus_city_c"] = round(float(record["temp_c_mean"]) - float(city_temp), 2)
        else:
            record["site_minus_city_c"] = None
        if city_forecast.get("error"):
            record["city_forecast_error"] = city_forecast["error"]

        record.update(duration)
        records.append(record)
        if persist:
            with connect() as conn:
                upsert_hour(conn, record)

    return records


def fetch_sites_parallel(
    sites: list[Site],
    start: datetime,
    hours: int = 12,
    *,
    max_workers: int | None = None,
    persist: bool = True,
    duration_metrics: bool | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch several sites at once. Caps workers so we do not stampede API credits."""
    workers = max(1, max_workers or FETCH_MAX_WORKERS)
    city = fetch_city_hourly(start, hours)
    out: dict[str, list[dict[str, Any]]] = {}

    def _one(site: Site) -> tuple[str, list[dict[str, Any]]]:
        with FortyGuardClient() as client:
            rows = fetch_site_hours(
                client,
                site,
                start,
                hours=hours,
                persist=persist,
                city_forecast=city,
                duration_metrics=duration_metrics,
            )
        return site.id, rows

    if workers == 1 or len(sites) == 1:
        for site in sites:
            site_id, rows = _one(site)
            out[site_id] = rows
        return out

    with ThreadPoolExecutor(max_workers=min(workers, len(sites))) as pool:
        futures = [pool.submit(_one, site) for site in sites]
        for future in as_completed(futures):
            site_id, rows = future.result()
            out[site_id] = rows
    return out


def _fetch_duration_metrics(
    client: FortyGuardClient,
    site: Site,
    date_time: dict[str, Any],
) -> dict[str, Any]:
    """Exceedance + persistence for the same window. Failures are recorded, not fatal."""
    empty = {
        "exceedance_hours_mean": None,
        "exceedance_hours_max": None,
        "persistence_hours_max": None,
        "duration_threshold_c": DURATION_THRESHOLD_C,
        "duration_used_in_risk": False,
        "duration_note": (
            "Exceedance/persistence are FortyGuard duration layers (hours above "
            f"{DURATION_THRESHOLD_C}°C air temperature). Not OSHA WBGT inputs."
        ),
    }
    try:
        exceed_id = client.submit_heatmap(
            site.polygon_aoi,
            date_time,
            granularity=HEATMAP_GRANULARITY_M,
            analytic_type="exceedance",
            threshold=DURATION_THRESHOLD_C,
            direction="above",
        )
        persist_id = client.submit_heatmap(
            site.polygon_aoi,
            date_time,
            granularity=HEATMAP_GRANULARITY_M,
            analytic_type="persistence",
            threshold=DURATION_THRESHOLD_C,
            direction="above",
        )
        exceed = client.wait_for_result(exceed_id)
        persist = client.wait_for_result(persist_id)
    except Exception as exc:  # noqa: BLE001
        empty["duration_error"] = str(exc)
        return empty

    exceed_stats = extract_duration_hours(exceed)
    persist_stats = extract_duration_hours(persist)
    empty["exceedance_hours_mean"] = exceed_stats["hours_mean"]
    empty["exceedance_hours_max"] = exceed_stats["hours_max"]
    empty["persistence_hours_max"] = persist_stats["hours_max"]
    empty["exceedance_activity_id"] = exceed_id
    empty["persistence_activity_id"] = persist_id
    return empty


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
        "tile_spread_c": None,
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
        "heatmap_analytic_type": HEATMAP_ANALYTIC_RISK,
        "data_source": "live",
        "missing_fields": [
            "temp_c_mean",
            "wet_bulb_temperature_celsius",
            "relative_humidity_percent",
        ],
        "error": error,
        "env_skipped": "missing_heatmap_temperature",
        "duration_used_in_risk": False,
    }


def _write_raw(site_id: str, hour_local: str, kind: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = hour_local.replace(":", "").replace("+", "_")
    path = RAW_DIR / f"{site_id}_{stamp}_{kind}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
