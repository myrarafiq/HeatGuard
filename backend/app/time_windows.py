from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def florida_now(timezone: str = "America/New_York") -> datetime:
    return datetime.now(ZoneInfo(timezone)).replace(minute=0, second=0, microsecond=0)


def parse_local_hour(value: str | None, timezone: str = "America/New_York") -> datetime:
    if not value:
        return florida_now(timezone)
    if "T" in value:
        dt = datetime.fromisoformat(value)
    else:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return dt.replace(minute=0, second=0, microsecond=0)


def single_hour(dt: datetime) -> dict[str, Any]:
    local = dt.astimezone(dt.tzinfo) if dt.tzinfo else dt
    return {
        "start_date": local.strftime("%Y-%m-%d"),
        "start_time": local.strftime("%H:%M"),
        "filter_type": 1,
    }


def hour_range(start: datetime, hours: int = 12) -> dict[str, Any]:
    end = start + timedelta(hours=hours)
    if end.date() != start.date():
        end = datetime.combine(start.date(), datetime.max.time()).replace(tzinfo=start.tzinfo)
        end = end.replace(hour=23, minute=0, second=0, microsecond=0)
    return {
        "start_date": start.strftime("%Y-%m-%d"),
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "filter_type": 2,
    }


def next_hours(start: datetime, hours: int = 12) -> list[datetime]:
    return [start + timedelta(hours=i) for i in range(hours)]
