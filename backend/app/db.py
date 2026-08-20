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
    UNIQUE(site_id, hour_local)
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def upsert_hour(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO hourly_conditions (
            site_id, hour_local, temp_c_min, temp_c_mean, temp_c_max, temp_c_stdev,
            tile_count, apparent_temperature_celsius, wet_bulb_temperature_celsius,
            relative_humidity_percent, heat_index_celsius, solar_ghi,
            heatmap_activity_id, env_activity_id, payload_json, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            fetched_at=excluded.fetched_at
        """,
        (
            record["site_id"],
            record["hour_local"],
            record.get("temp_c_min"),
            record.get("temp_c_mean"),
            record.get("temp_c_max"),
            record.get("temp_c_stdev"),
            record.get("tile_count"),
            record.get("apparent_temperature_celsius"),
            record.get("wet_bulb_temperature_celsius"),
            record.get("relative_humidity_percent"),
            record.get("heat_index_celsius"),
            record.get("solar_ghi"),
            record.get("heatmap_activity_id"),
            record.get("env_activity_id"),
            json.dumps(record),
            datetime.now(timezone.utc).isoformat(),
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
        out.append(payload)
    return out
