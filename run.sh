#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

.venv/bin/python -m backend.scripts.load_fixtures
echo ""
echo "HeatGuard running at http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --app-dir .
