"""Vercel serverless entrypoint for HeatGuard."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Writable temp DB on Vercel serverless
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    os.environ.setdefault("DATABASE_PATH", "/tmp/heat_planner.db")

from backend.app.main import app  # noqa: E402

__all__ = ["app"]
