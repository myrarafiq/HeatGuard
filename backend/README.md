# Heat Safety Planner — Person 1 (data / backend)

Same-day heat planner for Florida construction sites. This folder is the FortyGuard → clean hourly dataset layer. It does **not** calculate heat risk (Person 2).

## What FortyGuard actually gives us

| Endpoint | What we use it for |
| --- | --- |
| `POST /v1/heatmap` | Polygon temperatures (min / mean / max + per-tile GeoJSON). Supports historical data and **forecast up to 12 hours**. |
| `POST /v1/env_params` | Point metrics at the site centroid: wet bulb, apparent temperature, humidity (Basic plan: **3 params per request**). |
| `GET /v1/status/{activity_id}` | Async results. Credits are charged only when status is `Completed`. |

US coverage only — Florida is valid. Env-params should be requested for the **same time/location as the heatmap**, using the heatmap mean temperature as the required `temperature` input.

## Setup

```bash
cd FortyGuardTemperatureAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env   # or keep the key in api.txt
```

## Day 1–2: prove the idea

Three Miami-metro sites, one shared hour:

```bash
python -m backend.scripts.prove_idea --sites brickell,miami_beach,doral
```

Historical hot afternoon (uses credits):

```bash
python -m backend.scripts.prove_idea --when 2024-07-15T14:00 --sites brickell,miami_beach,doral
```

GO test: same metro + same time, different site temperatures that could change a work plan.

## Day 4: one site, 12 hours

```bash
python -m backend.scripts.fetch_forecast brickell --hours 12
```

## API for Person 2 / 3

```bash
uvicorn backend.app.main:app --reload --app-dir .
```

- `GET /sites`
- `GET /hours?site_id=brickell`
- `GET /planner/snapshot` — sites + stored hourly rows, no risk fields

## Contract Person 2 should consume

Each hour row includes:

- `temp_c_min` / `temp_c_mean` / `temp_c_max` / `tile_count`
- `wet_bulb_temperature_celsius`
- `apparent_temperature_celsius`
- `relative_humidity_percent`
- `heat_index_celsius` (null on Basic unless we swap a parameter)
- `missing_fields` — never treat null as 0

Sites live in `backend/data/sites.json`.
