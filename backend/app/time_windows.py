from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

FLORIDA_TZ = "America/New_York"


def florida_now(timezone_name: str = FLORIDA_TZ) -> datetime:
    return datetime.now(ZoneInfo(timezone_name)).replace(minute=0, second=0, microsecond=0)


def parse_local_hour(value: str | None, timezone_name: str = FLORIDA_TZ) -> datetime:
    if not value:
        return florida_now(timezone_name)
    cleaned = str(value).strip().replace("Z", "+00:00")
    if "T" in cleaned:
        dt = datetime.fromisoformat(cleaned)
    else:
        dt = datetime.strptime(cleaned[:16], "%Y-%m-%d %H:%M")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt.replace(minute=0, second=0, microsecond=0)


def hour_bucket(value: str | datetime, timezone_name: str = FLORIDA_TZ) -> str:
    """YYYY-MM-DDTHH in Florida local time — used to align env timestamps to site hours."""
    if isinstance(value, datetime):
        dt = value
    else:
        cleaned = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned) if "T" in cleaned or "+" in cleaned[-6:] else datetime.strptime(
                cleaned[:16], "%Y-%m-%d %H:%M"
            )
        except ValueError:
            dt = datetime.fromisoformat(cleaned[:19])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%dT%H")


def timestamp_hour_keys(value: str | datetime, timezone_name: str = FLORIDA_TZ) -> set[str]:
    """Possible local-hour keys for an API timestamp (aware, naive-as-local, or naive-as-UTC)."""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
        return {hour_bucket(dt, timezone_name)}

    cleaned = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned) if "T" in cleaned else datetime.strptime(cleaned[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return {str(value)[:13]}

    keys = set()
    if dt.tzinfo is not None:
        keys.add(hour_bucket(dt, timezone_name))
        return keys
    keys.add(hour_bucket(dt.replace(tzinfo=ZoneInfo(timezone_name)), timezone_name))
    keys.add(hour_bucket(dt.replace(tzinfo=timezone.utc), timezone_name))
    return keys


def single_hour(dt: datetime) -> dict[str, Any]:
    local = dt.astimezone(dt.tzinfo) if dt.tzinfo else dt
    return {
        "start_date": local.strftime("%Y-%m-%d"),
        "start_time": local.strftime("%H:%M"),
        "filter_type": 1,
    }


def hour_range(start: datetime, hours: int = 12) -> dict[str, Any]:
    """Inclusive same-day range: 12 hours from 06:00 → 06:00–17:00, filter_type 2."""
    hours = max(1, hours)
    last = start + timedelta(hours=hours - 1)
    if last.date() != start.date():
        last = start.replace(hour=23, minute=0, second=0, microsecond=0)
    return {
        "start_date": start.strftime("%Y-%m-%d"),
        "start_time": start.strftime("%H:%M"),
        "end_time": last.strftime("%H:%M"),
        "filter_type": 2,
    }


def same_day_hours(start: datetime, hours: int = 12) -> list[datetime]:
    """Hours to persist for a filter_type 2 request (clamped to the start calendar day)."""
    return [hour for hour in next_hours(start, hours) if hour.date() == start.date()]


def next_hours(start: datetime, hours: int = 12) -> list[datetime]:
    return [start + timedelta(hours=i) for i in range(hours)]
