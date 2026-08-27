# HeatGuard backend

FortyGuard forecasts → OSHA/NIOSH screening risk → recommendations → dashboard API.

Thresholds are copied from OSHA’s NIOSH/ACGIH table. We do not invent cutoffs. Because FortyGuard does not provide globe temperature or wind, risk uses a **screening WBGT estimate**: `0.7*Tw + 0.3*Ta_hotspot`. Full citations: [`safety/METHODOLOGY.md`](safety/METHODOLOGY.md).

## Setup

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Add `FORTYGUARD_API_KEY` to `.env` only if you want live pulls. The dashboard runs from backup data without a key.

## Run

```bash
./run.sh
# or
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

Open http://127.0.0.1:8000

If the database is empty, `/planner` loads the backup demo day automatically.

## Backup data vs live FortyGuard

The hosted demo and a fresh local database use a **backup 12-hour Miami day (26 August 2026)**. Peak-hour (2:00 PM) temps for Brickell / Miami Beach / Doral are from a real FortyGuard pull; other hours follow a diurnal curve so the 12-hour story never goes blank.

That is a judging fallback, not the product limit. FortyGuard’s API can load **today**:

```bash
python -m backend.scripts.fetch_all_sites --hours 12
python -m backend.scripts.prove_idea --sites brickell,miami_beach,doral
```

`--when` defaults to the current Florida hour. After a live pull, the dashboard chip reads **LIVE**.

Reload backup data:

```bash
python -m backend.scripts.load_fixtures
```

**Why the public Vercel demo stays on the backup day:** heatmap jobs take minutes, Vercel functions time out at 30 seconds, and auto-refreshing on every judge visit would spend API credits. Locally, use **Load today** on the dashboard or `POST /demo/refresh-live`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | Liveness, data mode, whether live refresh is available |
| `GET` | `/sites` | Site polygons + metadata |
| `GET` | `/workloads` | Light / moderate / heavy definitions and OSHA clothing CAF |
| `GET` | `/hours?site_id=` | Raw stored environmental hours |
| `GET` | `/planner?workload=heavy` | Sites, risk timeline, today's actions, comparison |
| `GET` | `/planner/snapshot` | Alias for `/planner` |
| `GET` | `/planner/compare` | Best/worst site at an hour |
| `GET` | `/planner/brief` | Text operations brief |
| `POST` | `/planner/ask` | Explain calculated results only |
| `POST` | `/demo/load-fixtures` | Reload backup demo day |
| `POST` | `/demo/refresh-live` | Pull today (local + API key; not on Vercel) |

Planner query flags: `acclimatized=true` (TLV as the only red line), `extra_ppe=true` (OSHA SMS polypropylene coveralls, +0.5°C CAF).

## Tests

```bash
python -m unittest backend.tests.test_normalize backend.tests.test_safety backend.tests.test_pipeline
```
