# HeatGuard dashboard

Manager-facing UI for the same-day heat planner. This folder is the source. Vercel serves a copy from `public/`.

It does **not** call FortyGuard and does **not** calculate Green / Amber / Red. It reads `/planner` and displays what the backend already scored.

## What a manager should see in about 10 seconds

- Which Miami sites need attention
- When heat risk increases during the workday
- What to do this morning, at midday, and where to send heavy crews

## Screens

| Piece | Role |
| --- | --- |
| Command strip | Date, workload (light / moderate / heavy), BACKUP vs LIVE chip, acclimatization and coveralls toggles |
| Site map | Five polygons colored by the selected hour’s OSHA screening level |
| Site × hour grid | G / A / R for the 12-hour window |
| Today's moves | Three clickable actions from the calculated shift plan |
| Selected hour | Screening WBGT vs Action Limit (AL) and Threshold Limit Value (TLV) |
| Supervisor notes | Short bullets plus optional Q&A over the same planner JSON |

## Data contract

```text
GET  /planner?workload=heavy
GET  /health
POST /planner/ask
POST /demo/refresh-live   (local + API key only)
```

Rules:

- Never treat `null` as `0`. Show unavailable values as `—`.
- Never derive risk colors from temperature in the browser.
- Heat index / apparent temperature are display-only. OSHA color uses screening WBGT from the API.
- **BACKUP** means the 26 August 2026 demo day. **LIVE** means a FortyGuard pull starting at the current Florida hour.

## Local run

Start the backend from the repo root (`./run.sh` or uvicorn). Open http://127.0.0.1:8000. The dashboard is served by FastAPI from this folder.

If you change `index.html`, `app.js`, or `styles.css`, copy them to `public/` so the Vercel demo stays in sync.
