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
    raise RuntimeError(
        "Missing FORTYGUARD_API_KEY. Copy .env.example to .env or keep it in api.txt."
    )


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
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "backend" / "data" / "heat_planner.db")))
SITES_PATH = ROOT / "backend" / "data" / "sites.json"
RAW_DIR = ROOT / "backend" / "data" / "raw"
