from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS hourly_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    hour_local TEXT NOT NULL,
    temp_c_min REAL,
    temp_c_mean REAL,
    temp_c_max REAL,
    temp_c_stdev REAL,
    tile_count INTEGER,
    apparent_temperature_celsius REAL,
    wet_bulb_temperature_celsius REAL,
    relative_humidity_percent REAL,
    heat_index_celsius REAL,
    solar_ghi REAL,
    heatmap_activity_id TEXT,
    env_activity_id TEXT,
    payload_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    data_source TEXT,
    UNIQUE(site_id, hour_local)
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open SQLite, falling back to /tmp if the configured path is not writable."""
    primary = Path(path or DATABASE_PATH)
    candidates = [primary]
    fallback = Path("/tmp/heat_planner.db")
    if primary.resolve() != fallback.resolve():
        candidates.append(fallback)
    last_error: Exception | None = None
    for db_path in candidates:
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute(SCHEMA)
            _ensure_columns(conn)
            conn.execute("PRAGMA user_version")
            return conn
        except OSError as exc:
            last_error = exc
            continue
    raise last_error or OSError("Could not open a writable SQLite database")


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(hourly_conditions)")}
    if "data_source" not in cols:
        conn.execute("ALTER TABLE hourly_conditions ADD COLUMN data_source TEXT")
        conn.commit()


def infer_data_source(record: dict[str, Any]) -> str:
    explicit = record.get("data_source")
    if explicit in {"live", "fixture"}:
        return explicit
    activity = str(record.get("heatmap_activity_id") or "")
    source = str(record.get("source") or "")
    if activity == "fixture" or "fixture" in source:
        return "fixture"
    if activity:
        return "live"
    return "unknown"


def summarize_data_mode(hours: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [infer_data_source(row) for row in hours]
    kinds = {item for item in sources if item != "unknown"}
    if not hours:
        mode = "empty"
    elif "live" in kinds and "fixture" in kinds:
        mode = "mixed"
    elif "fixture" in kinds:
        mode = "fixture"
    elif "live" in kinds:
        mode = "live"
    else:
        mode = "unknown"
    live_ok = [
        row
        for row in hours
        if infer_data_source(row) == "live" and row.get("temp_c_mean") is not None
    ]
    last_pull = None
    if live_ok:
        last_pull = max((row.get("fetched_at") or "") for row in live_ok) or None
    return {
        "mode": mode,
        "mixed": mode == "mixed",
        "hour_count": len(hours),
        "live_hours": sources.count("live"),
        "fixture_hours": sources.count("fixture"),
        "unknown_hours": sources.count("unknown"),
        "last_successful_pull": last_pull,
    }


def clear_hours(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM hourly_conditions")
    conn.commit()


def upsert_hour(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    data_source = infer_data_source(record)
    stored = {**record, "data_source": data_source}
    conn.execute(
        """
        INSERT INTO hourly_conditions (
            site_id, hour_local, temp_c_min, temp_c_mean, temp_c_max, temp_c_stdev,
            tile_count, apparent_temperature_celsius, wet_bulb_temperature_celsius,
            relative_humidity_percent, heat_index_celsius, solar_ghi,
            heatmap_activity_id, env_activity_id, payload_json, fetched_at, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_id, hour_local) DO UPDATE SET
            temp_c_min=excluded.temp_c_min,
            temp_c_mean=excluded.temp_c_mean,
            temp_c_max=excluded.temp_c_max,
            temp_c_stdev=excluded.temp_c_stdev,
            tile_count=excluded.tile_count,
            apparent_temperature_celsius=excluded.apparent_temperature_celsius,
            wet_bulb_temperature_celsius=excluded.wet_bulb_temperature_celsius,
            relative_humidity_percent=excluded.relative_humidity_percent,
            heat_index_celsius=excluded.heat_index_celsius,
            solar_ghi=excluded.solar_ghi,
            heatmap_activity_id=excluded.heatmap_activity_id,
            env_activity_id=excluded.env_activity_id,
            payload_json=excluded.payload_json,
            fetched_at=excluded.fetched_at,
            data_source=excluded.data_source
        """,
        (
            stored["site_id"],
            stored["hour_local"],
            stored.get("temp_c_min"),
            stored.get("temp_c_mean"),
            stored.get("temp_c_max"),
            stored.get("temp_c_stdev"),
            stored.get("tile_count"),
            stored.get("apparent_temperature_celsius"),
            stored.get("wet_bulb_temperature_celsius"),
            stored.get("relative_humidity_percent"),
            stored.get("heat_index_celsius"),
            stored.get("solar_ghi"),
            stored.get("heatmap_activity_id"),
            stored.get("env_activity_id"),
            json.dumps(stored),
            datetime.now(timezone.utc).isoformat(),
            data_source,
        ),
    )
    conn.commit()


def list_hours(conn: sqlite3.Connection, site_id: str | None = None) -> list[dict[str, Any]]:
    if site_id:
        rows = conn.execute(
            "SELECT * FROM hourly_conditions WHERE site_id = ? ORDER BY hour_local",
            (site_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM hourly_conditions ORDER BY site_id, hour_local").fetchall()
    out = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload["fetched_at"] = row["fetched_at"]
        payload["data_source"] = infer_data_source(payload)
        out.append(payload)
    return out
