# HeatGuard backend — Person 1 (data) + Person 2 (safety / intelligence)

FortyGuard forecasts → OSHA/NIOSH screening risk → recommendations → AI explanation.

Frontend (Person 3) is separate; this API is the contract for the dashboard.

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

## Demo data (backup if API fails)

```bash
python -m backend.scripts.load_fixtures
```

Loads a 12-hour × 5-site day. 14:00 anchors for Brickell / Miami Beach / Doral are **live FortyGuard** values from 2024-07-15; other hours use a diurnal curve for demo resilience.

## Live FortyGuard pulls (uses credits)

```bash
# Day 1–2 GO/NO-GO
python -m backend.scripts.prove_idea --when 2024-07-15T14:00 --sites brickell,miami_beach,doral

# One site, 12 hours
python -m backend.scripts.fetch_forecast brickell --hours 12

# Multiple sites
python -m backend.scripts.fetch_all_sites --sites brickell,miami_beach,doral --hours 12
```

## Run API

```bash
uvicorn backend.app.main:app --reload --app-dir .
```

### Endpoints for Person 3

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness |
| `GET` | `/sites` | Site polygons + metadata |
| `GET` | `/workloads` | Light / moderate / heavy definitions |
| `GET` | `/hours?site_id=` | Raw stored environmental hours |
| `GET` | `/planner?workload=heavy` | **Main payload**: risk timeline, today’s actions, comparison |
| `GET` | `/planner/compare?workload=heavy&hour_local=` | Best/worst site at an hour |
| `GET` | `/planner/brief?workload=heavy` | Text operations brief |
| `POST` | `/planner/ask` | `{"question":"...","workload":"heavy"}` — explains calculated results only |
| `POST` | `/demo/load-fixtures` | Reload backup demo day |

If the DB is empty, `GET /planner` auto-loads fixtures.

### Example: Day 5 question

`POST /planner/ask`

```json
{
  "question": "Which site has the best conditions for heavy outdoor work at 10 AM?",
  "workload": "heavy"
}
```

## Tests

```bash
python -m unittest backend.tests.test_normalize backend.tests.test_safety
```
