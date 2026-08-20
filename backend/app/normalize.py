from __future__ import annotations

from typing import Any


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


def _get(d: dict[str, Any], *names: str, default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in d.items()}
    for name in names:
        if name in d:
            return d[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def extract_heatmap_stats(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result") if "result" in result else result
    if "data" in result and isinstance(result["data"], dict) and "result" in result["data"]:
        payload = result["data"]["result"]
    stats = _get(payload or {}, "stats_data", "statsData", default={}) or {}
    temp_stats = _get(stats, "Temperature_stats", "temperature_stats", default={}) or {}
    return {
        "temp_c_min": _as_float(_get(temp_stats, "minimum", "Minimum", "min")),
        "temp_c_max": _as_float(_get(temp_stats, "maximum", "Maximum", "max")),
        "temp_c_mean": _as_float(_get(temp_stats, "mean", "Mean", "average")),
        "temp_c_stdev": _as_float(_get(temp_stats, "standard_deviation", "Standard_deviation", "std")),
        "raw_stats": stats,
    }


def extract_tile_temperatures(result: dict[str, Any]) -> list[float]:
    payload = result.get("result") if "result" in result else result
    if "data" in result and isinstance(result["data"], dict) and "result" in result["data"]:
        payload = result["data"]["result"]
    map_data = _get(payload or {}, "map_data", "mapData", default={}) or {}
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


def extract_env_series(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result") if "result" in result else result
    if "data" in result and isinstance(result["data"], dict) and "result" in result["data"]:
        payload = result["data"]["result"]
    payload = payload or {}
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
        "solar_ghi": _nested_float(clear_sky, "ghi"),
        "solar_dni": _nested_float(clear_sky, "dni"),
        "solar_dhi": _nested_float(clear_sky, "dhi"),
        "elevation": location.get("elevation"),
        "input_temperature": location.get("temperature"),
    }


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
    out["solar_ghi"] = series.get("solar_ghi")
    return out


def merge_hour_record(
    *,
    site_id: str,
    hour_local: str,
    heatmap: dict[str, Any] | None,
    env: dict[str, Any] | None,
    heatmap_activity_id: str | None,
    env_activity_id: str | None,
) -> dict[str, Any]:
    tiles = extract_tile_temperatures(heatmap) if heatmap else []
    stats = extract_heatmap_stats(heatmap) if heatmap else {}
    env_vals = env_values_at_index(extract_env_series(env), 0) if env else {}
    mean = stats.get("temp_c_mean")
    if mean is None and tiles:
        mean = round(sum(tiles) / len(tiles), 3)
    return {
        "site_id": site_id,
        "hour_local": hour_local,
        "temp_c_min": stats.get("temp_c_min") if stats.get("temp_c_min") is not None else (min(tiles) if tiles else None),
        "temp_c_max": stats.get("temp_c_max") if stats.get("temp_c_max") is not None else (max(tiles) if tiles else None),
        "temp_c_mean": mean,
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
        "missing_fields": [
            name
            for name, value in (
                ("temp_c_mean", mean),
                ("wet_bulb_temperature_celsius", env_vals.get("wet_bulb_temperature_celsius")),
                ("relative_humidity_percent", env_vals.get("relative_humidity_percent")),
            )
            if value is None
        ],
    }


def _as_float(value: Any) -> float | None:
    if value in (None, "", -999, "-999"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested_float(obj: Any, key: str) -> float | None:
    if not isinstance(obj, dict):
        return _as_float(obj)
    value = obj.get(key)
    if isinstance(value, list):
        return _as_float(value[0] if value else None)
    return _as_float(value)
