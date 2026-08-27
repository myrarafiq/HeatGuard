from __future__ import annotations

"""One Open-Meteo Miami 2 m reading for city-vs-site contrast. Not an OSHA input."""

from datetime import datetime, timedelta
from typing import Any

import httpx

from .config import CITY_FORECAST_LAT, CITY_FORECAST_LON, CITY_FORECAST_NAME, CITY_FORECAST_TZ
from .time_windows import hour_bucket

CITY_SOURCE = "open-meteo"


def fetch_city_hourly(
    start: datetime,
    hours: int = 12,
    *,
    latitude: float = CITY_FORECAST_LAT,
    longitude: float = CITY_FORECAST_LON,
) -> dict[str, Any]:
    """One Miami-metro 2 m air-temperature series for city-vs-site contrast.

    Not used in OSHA screening. Failure returns empty temps — never invent a city forecast.
    """
    hours = max(1, hours)
    end = start + timedelta(hours=hours - 1)
    start_date = start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m",
        "timezone": CITY_FORECAST_TZ,
        "start_date": start_date,
        "end_date": end_date,
    }
    today = datetime.now(start.tzinfo).date() if start.tzinfo else datetime.now().date()
    base = (
        "https://archive-api.open-meteo.com/v1/archive"
        if start.date() < today
        else "https://api.open-meteo.com/v1/forecast"
    )
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(base, params=params)
            response.raise_for_status()
            body = response.json()
    except Exception as exc:  # noqa: BLE001 — city contrast is optional
        return {
            "source": CITY_SOURCE,
            "name": CITY_FORECAST_NAME,
            "temps_by_hour": {},
            "error": str(exc),
        }

    hourly = body.get("hourly") or {}
    times = hourly.get("time") or []
    values = hourly.get("temperature_2m") or []
    temps: dict[str, float] = {}
    for stamp, raw in zip(times, values):
        if raw is None:
            continue
        try:
            temps[hour_bucket(str(stamp))] = float(raw)
        except (TypeError, ValueError):
            continue
    return {
        "source": CITY_SOURCE,
        "name": CITY_FORECAST_NAME,
        "latitude": latitude,
        "longitude": longitude,
        "temps_by_hour": temps,
        "error": None,
    }


def city_temp_for_hour(city: dict[str, Any], hour_local: str) -> float | None:
    temps = city.get("temps_by_hour") or {}
    return temps.get(hour_bucket(hour_local))
