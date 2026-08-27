from __future__ import annotations

"""Environment and FortyGuard settings. Missing API key is allowed: the demo uses backup data."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _api_key() -> str:
    key = os.getenv("FORTYGUARD_API_KEY", "").strip()
    if key:
        return key
    api_txt = ROOT / "api.txt"
    if api_txt.exists():
        for line in api_txt.read_text().splitlines():
            if line.lower().startswith("api key:"):
                return line.split(":", 1)[1].strip()
    # Dashboard demo works from fixtures without a live key.
    return ""


FORTYGUARD_API_KEY = _api_key()
FORTYGUARD_BASE_URL = os.getenv("FORTYGUARD_BASE_URL", "https://api.fortyguard.com/v1").rstrip("/")
FORTYGUARD_ENV_PARAMS = [
    p.strip()
    for p in os.getenv(
        "FORTYGUARD_ENV_PARAMS",
        "wet_bulb_temperature_celsius,apparent_temperature_celsius,relative_humidity_percent",
    ).split(",")
    if p.strip()
]
_default_db = str(ROOT / "backend" / "data" / "heat_planner.db")
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    # Serverless filesystem is read-only except /tmp. Never use the repo path.
    os.environ["DATABASE_PATH"] = "/tmp/heat_planner.db"
    _default_db = "/tmp/heat_planner.db"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", _default_db))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT / DATABASE_PATH
SITES_PATH = ROOT / "backend" / "data" / "sites.json"
RAW_DIR = ROOT / "backend" / "data" / "raw"

# Snapshot (tcm) is the only layer used for hourly OSHA risk. 60 m matches
# construction-lot polygons better than 100 m (more tiles → real min/mean/max).
HEATMAP_GRANULARITY_M = int(os.getenv("HEATMAP_GRANULARITY_M", "60"))
HEATMAP_ANALYTIC_RISK = "tcm"
DURATION_THRESHOLD_C = float(os.getenv("DURATION_THRESHOLD_C", "30"))
FETCH_MAX_WORKERS = int(os.getenv("FETCH_MAX_WORKERS", "2"))
ENABLE_DURATION_METRICS = os.getenv("HEATGUARD_DURATION_METRICS", "1").strip() not in {"0", "false", "no"}

# One Miami-metro city reading for "normal weather vs FortyGuard" contrast.
CITY_FORECAST_LAT = float(os.getenv("CITY_FORECAST_LAT", "25.7617"))
CITY_FORECAST_LON = float(os.getenv("CITY_FORECAST_LON", "-80.1918"))
CITY_FORECAST_NAME = os.getenv("CITY_FORECAST_NAME", "Miami")
CITY_FORECAST_TZ = os.getenv("CITY_FORECAST_TZ", "America/New_York")
