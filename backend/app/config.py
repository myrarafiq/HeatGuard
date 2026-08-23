from __future__ import annotations

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
_default_db = (
    "/tmp/heat_planner.db"
    if (os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
    else str(ROOT / "backend" / "data" / "heat_planner.db")
)
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", _default_db))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT / DATABASE_PATH
SITES_PATH = ROOT / "backend" / "data" / "sites.json"
RAW_DIR = ROOT / "backend" / "data" / "raw"
