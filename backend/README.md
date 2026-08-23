# HeatGuard backend

FortyGuard forecasts → OSHA/NIOSH screening risk → recommendations → AI explanation → dashboard.

## Methodology

See [`safety/METHODOLOGY.md`](safety/METHODOLOGY.md). Thresholds are from OSHA’s NIOSH/ACGIH table — not invented. We use a **screening WBGT estimate** `0.7*Tw + 0.3*Ta` because FortyGuard does not provide globe temperature or wind.

## Setup

```bash
cd FortyGuardTemperatureAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

## Run (API + dashboard)

```bash
./run.sh
# or
python -m backend.scripts.load_fixtures
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

Open http://127.0.0.1:8000

## Demo data (backup if API fails)

```bash
python -m backend.scripts.load_fixtures
```

Loads a 12-hour × 5-site day. 14:00 anchors for Brickell / Miami Beach / Doral use **live FortyGuard** values from 2024-07-15; other hours use a diurnal curve for demo resilience. If the DB is empty, `/planner` auto-loads fixtures.

## Live FortyGuard pulls (uses credits)

```bash
python -m backend.scripts.prove_idea --when 2024-07-15T14:00 --sites brickell,miami_beach,doral
python -m backend.scripts.fetch_forecast brickell --hours 12
python -m backend.scripts.fetch_all_sites --sites all --hours 12
```

## API reference

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | Liveness |
| `GET` | `/sites` | Site polygons + metadata |
| `GET` | `/workloads` | Light / moderate / heavy definitions |
| `GET` | `/hours?site_id=` | Raw stored environmental hours |
| `GET` | `/planner?workload=heavy` | Sites, risk timeline, today's actions, comparison |
| `GET` | `/planner/snapshot` | Alias for `/planner` |
| `GET` | `/planner/compare` | Best/worst site at an hour |
| `GET` | `/planner/brief` | Text operations brief |
| `POST` | `/planner/ask` | Explain calculated results only |
| `POST` | `/demo/load-fixtures` | Reload backup demo day |

## Tests

```bash
python -m unittest backend.tests.test_normalize backend.tests.test_safety
```
