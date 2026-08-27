#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

echo ""
echo "HeatGuard running at http://127.0.0.1:8000"
echo "If the database is empty, the API loads the backup demo day automatically."
echo "To pull today from FortyGuard (uses credits): python -m backend.scripts.fetch_all_sites"
echo "Press Ctrl+C to stop."
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --app-dir .
