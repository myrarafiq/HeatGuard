from __future__ import annotations

from typing import Any

from .time_windows import hour_bucket, timestamp_hour_keys


TILE_TEMP_KEYS = (
    "average_temperature",
    "min_temperature",
    "max_temperature",
    "value",
    "temperature",
    "temp",
    "temp_c",
    "tcm",
    "predicted_temperature",
    "Temperature",
)

HOUR_LIST_KEYS = ("hours", "hourly", "time_series", "timeseries", "snapshots")


def _get(d: dict[str, Any], *names: str, default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in d.items()}
    for name in names:
        if name in d:
            return d[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def unwrap_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {}
    payload = result.get("result") if "result" in result else result
    if "data" in result and isinstance(result["data"], dict) and "result" in result["data"]:
        payload = result["data"]["result"]
    return payload or {}


def extract_heatmap_stats(result: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_result(result)
    stats = _get(payload, "stats_data", "statsData", default={}) or {}
    temp_stats = _get(stats, "Temperature_stats", "temperature_stats", default={}) or {}
    return {
        "temp_c_min": _as_float(_get(temp_stats, "minimum", "Minimum", "min")),
        "temp_c_max": _as_float(_get(temp_stats, "maximum", "Maximum", "max")),
        "temp_c_mean": _as_float(_get(temp_stats, "mean", "Mean", "average")),
        "temp_c_stdev": _as_float(_get(temp_stats, "standard_deviation", "Standard_deviation", "std")),
        "raw_stats": stats,
    }


def extract_tile_temperatures(result: dict[str, Any]) -> list[float]:
    payload = unwrap_result(result)
    map_data = _get(payload, "map_data", "mapData", default={}) or {}
    features = map_data.get("features") if isinstance(map_data, dict) else None
    if not features:
        return []
    temps: list[float] = []
    for feature in features:
        props = feature.get("properties") or {}
        for key in TILE_TEMP_KEYS:
            if key in props and props[key] not in (None, -999):
                value = _as_float(props[key])
                if value is not None:
                    temps.append(value)
                    break
    return temps


def heatmap_mean_c(result: dict[str, Any] | None) -> float | None:
    """Site air temperature from heatmap stats or tiles. Never a hardcoded fallback."""
    if not result:
        return None
    stats = extract_heatmap_stats(result)
    mean = stats.get("temp_c_mean")
    if mean is not None:
        return mean
    tiles = extract_tile_temperatures(result)
    if tiles:
        return round(sum(tiles) / len(tiles), 3)
    return None


def tile_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return round(ordered[low] * (1 - frac) + ordered[high] * frac, 3)


def split_heatmap_hourly(result: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """If FortyGuard nested per-hour maps in a range result, index them by local hour.

    Empty dict means the payload is a single range snapshot — callers reuse it for every hour
    and label heatmap_scope='range'.
    """
    if not result:
        return {}
    payload = unwrap_result(result)
    items = None
    for key in HOUR_LIST_KEYS:
        candidate = _get(payload, key) or _get(result, key)
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            items = candidate
            break
    if not items:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for item in items:
        ts = item.get("timestamp") or item.get("date_time") or item.get("hour") or item.get("hour_local")
        if not ts:
            continue
        shaped = item if ("map_data" in item or "stats_data" in item or "result" in item) else {
            "map_data": item.get("map_data"),
            "stats_data": item.get("stats_data"),
        }
        wrapped = item if "data" in item or "result" in item else {"data": {"result": shaped}}
        for key in timestamp_hour_keys(str(ts)):
            out[key] = wrapped
    return out


def extract_env_series(result: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_result(result)
    metadata = payload.get("metadata") or {}
    locations = payload.get("locations") or []
    location = locations[0] if locations else {}
    parameters = location.get("parameters") or {}
    solar = location.get("solar_irradiance") or {}
    clear_sky = solar.get("clear_sky") if isinstance(solar, dict) else {}
    timestamps = metadata.get("timestamps") or []
    return {
        "timezone": metadata.get("timezone"),
        "timezone_offset_hours": metadata.get("timezone_offset_hours"),
        "timestamps": timestamps,
        "parameters": parameters,
        "solar_ghi": clear_sky.get("ghi") if isinstance(clear_sky, dict) else None,
        "solar_dni": clear_sky.get("dni") if isinstance(clear_sky, dict) else None,
        "solar_dhi": clear_sky.get("dhi") if isinstance(clear_sky, dict) else None,
        "elevation": location.get("elevation"),
        "input_temperature": location.get("temperature"),
    }


def env_index_for_hour(series: dict[str, Any], hour_local: str) -> int | None:
    """Pick the env series step whose timestamp matches hour_local. None = do not guess."""
    timestamps = series.get("timestamps") or []
    target = hour_bucket(hour_local)
    for index, stamp in enumerate(timestamps):
        if stamp is None:
            continue
        if target in timestamp_hour_keys(str(stamp)):
            return index

    params = series.get("parameters") or {}
    lengths = [len(values) for values in params.values() if isinstance(values, list)]
    n = max(lengths) if lengths else 0
    # Scalar / single-step response: safe to use index 0 only when there is one step.
    if not timestamps and n <= 1:
        return 0
    return None


def env_values_at_index(series: dict[str, Any], index: int = 0) -> dict[str, Any]:
    params = series.get("parameters") or {}
    out: dict[str, Any] = {}
    for key, values in params.items():
        if isinstance(values, list):
            out[key] = _as_float(values[index] if index < len(values) else None)
        else:
            out[key] = _as_float(values)
    timestamps = series.get("timestamps") or []
    out["timestamp"] = timestamps[index] if index < len(timestamps) else None
    out["solar_ghi"] = _series_value(series.get("solar_ghi"), index)
    out["solar_dni"] = _series_value(series.get("solar_dni"), index)
    out["solar_dhi"] = _series_value(series.get("solar_dhi"), index)
    return out


def env_values_for_hour(series: dict[str, Any] | None, hour_local: str) -> dict[str, Any]:
    if not series:
        return {}
    index = env_index_for_hour(series, hour_local)
    if index is None:
        return {
            "timestamp": None,
            "wet_bulb_temperature_celsius": None,
            "apparent_temperature_celsius": None,
            "relative_humidity_percent": None,
            "heat_index_celsius": None,
            "solar_ghi": None,
            "env_hour_unaligned": True,
        }
    return env_values_at_index(series, index)


def merge_hour_record(
    *,
    site_id: str,
    hour_local: str,
    heatmap: dict[str, Any] | None,
    env: dict[str, Any] | None,
    heatmap_activity_id: str | None,
    env_activity_id: str | None,
    heatmap_scope: str = "hour",
    data_source: str = "live",
) -> dict[str, Any]:
    tiles = extract_tile_temperatures(heatmap) if heatmap else []
    stats = extract_heatmap_stats(heatmap) if heatmap else {}
    env_vals = env_values_for_hour(extract_env_series(env), hour_local) if env else {}
    mean = stats.get("temp_c_mean")
    if mean is None and tiles:
        mean = round(sum(tiles) / len(tiles), 3)
    p90 = tile_percentile(tiles, 90) if tiles else None
    missing = [
        name
        for name, value in (
            ("temp_c_mean", mean),
            ("wet_bulb_temperature_celsius", env_vals.get("wet_bulb_temperature_celsius")),
            ("relative_humidity_percent", env_vals.get("relative_humidity_percent")),
        )
        if value is None
    ]
    if env_vals.get("env_hour_unaligned"):
        missing.append("env_timestamp_match")
    return {
        "site_id": site_id,
        "hour_local": hour_local,
        "temp_c_min": stats.get("temp_c_min") if stats.get("temp_c_min") is not None else (min(tiles) if tiles else None),
        "temp_c_max": stats.get("temp_c_max") if stats.get("temp_c_max") is not None else (max(tiles) if tiles else None),
        "temp_c_mean": mean,
        "temp_c_p90": p90,
        "temp_c_stdev": stats.get("temp_c_stdev"),
        "tile_count": len(tiles),
        "tile_temperatures_c": tiles,
        "apparent_temperature_celsius": env_vals.get("apparent_temperature_celsius"),
        "wet_bulb_temperature_celsius": env_vals.get("wet_bulb_temperature_celsius"),
        "relative_humidity_percent": env_vals.get("relative_humidity_percent"),
        "heat_index_celsius": env_vals.get("heat_index_celsius"),
        "solar_ghi": env_vals.get("solar_ghi"),
        "api_timestamp": env_vals.get("timestamp"),
        "heatmap_activity_id": heatmap_activity_id,
        "env_activity_id": env_activity_id,
        "heatmap_scope": heatmap_scope,
        "data_source": data_source,
        "missing_fields": missing,
    }


def _series_value(raw: Any, index: int) -> float | None:
    if isinstance(raw, list):
        return _as_float(raw[index] if index < len(raw) else None)
    return _as_float(raw)


def _as_float(value: Any) -> float | None:
    if value in (None, "", -999, "-999"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
