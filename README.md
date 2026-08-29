# HeatGuard

### Same-Day Heat Safety Planner for Construction Sites

**FortyGuard Hackathon '26 submission** — *Building the World's Temperature AI*

> It's 6:30 AM. You manage five Florida construction sites. A normal weather app gives you one city forecast. Your workers need more than that.

**HeatGuard** turns FortyGuard's hyperlocal temperature intelligence into today's operating plan: which sites are safest for outdoor work, when risk peaks, and what a supervisor should do before the heat does.

### Project Demo and Slides Recording:
**https://youtu.be/J3KHnEv3CZY**

---

## Live demo

**https://forty-guard-temperature-ai.vercel.app/**

The hosted demo uses a **backup 12-hour Miami workday (26 August 2026)** so judging always sees a full site-by-site story. FortyGuard heatmap jobs take minutes, which is longer than serverless allows, and a failed live pull would leave the demo empty. The product can still load **today** locally with an API key (see [Live vs backup data](#live-vs-backup-data)).

---

## Who this is for

Construction and HSE managers who run **more than one outdoor site in the same metro**. They already get a city forecast. What they do not get is a same-morning answer to: which site can still take heavy work, which site should pause, and where to send crews at 10 AM.

## Why we built it

City weather treats Brickell, Doral, and Miami Beach as the same place. Shade, asphalt, and waterfront wind do not. A 1°C site-to-site gap can flip a crew across a published OSHA limit. HeatGuard makes that difference a **work decision**, not a weather trivia table.

## What HeatGuard does

Every morning, HeatGuard:

1. Loads each site's polygon and work context
2. Pulls the next **12 hours** of FortyGuard hyperlocal data (heatmap + wet-bulb and related environmental parameters)
3. Converts conditions into a **heat-risk assessment** by workload (light / moderate / heavy)
4. Compares sites side by side
5. Recommends **when and where** outdoor work should happen
6. Explains the plan in a supervisor brief that only narrates calculated results — it never invents safety math

**Demo story in one line:** different heat → different risk → different recommended work plan.

## Heat-risk thresholds (not invented)

Green / amber / red is **OSHA Table 2**, copied from [OSHA Heat Hazard Recognition](https://www.osha.gov/heat-exposure/hazards) (NIOSH / ACGIH effective WBGT in °C).

| Initials | Full name | What it means here |
| --- | --- | --- |
| **WBGT** | Wet Bulb Globe Temperature | The heat metric OSHA prefers. We use a **screening estimate** because FortyGuard has wet-bulb and air temperature, not globe temperature or wind. |
| **AL** | Action Limit | First caution line for **unacclimatized** workers / new hires. Default planning assumption. |
| **TLV** | Threshold Limit Value | Red line. For acclimatized crews this is the only trip; for mixed crews it is past both AL and TLV. |
| **CAF** | Clothing Adjustment Factor | °C added to screening WBGT before Table 2 (OSHA clothing table). Default work clothing = 0. Optional coveralls = SMS polypropylene **+0.5°C**. |
| **ACGIH** | American Conference of Governmental Industrial Hygienists | Source of the work/rest bands (45/15, 30/30, 15/45, stop). |
| **NIOSH** | National Institute for Occupational Safety and Health | Source of the AL/TLV table OSHA republishes. |
| **OSHA** | Occupational Safety and Health Administration | The public table we compare against. |
| **TCM** | FortyGuard snapshot heatmap | The only FortyGuard layer used for hourly OSHA risk. |

**OSHA Table 2 — continuous-work screening, effective WBGT °C**

| Workload | Action Limit (unacclimatized) | TLV (acclimatized) |
| --- | ---: | ---: |
| light | 28 | 30 |
| moderate | 25 | 28 |
| heavy | 23 | 26 |
| very heavy | 21 | 25 |

**Screening formula** (labeled `screening_wbgt_estimate`, not a certified WBGT meter):

```text
screening_wbgt_c = 0.7 * Tw + 0.3 * Ta_hotspot
effective_wbgt_c = screening_wbgt_c + clothing_CAF
```

`Tw` is FortyGuard wet-bulb. `Ta_hotspot` is the hottest occupied area of the polygon (`temp_c_p90`, else max, else mean). Heat index / apparent temperature are **display-only**.

Default assumption: **unacclimatized / new hires present**. Toggle **Acclimatized** to use TLV as the only red line. Full citations: [`backend/safety/METHODOLOGY.md`](backend/safety/METHODOLOGY.md).

## Live vs backup data

| Mode | When you see it | What it is |
| --- | --- | --- |
| **BACKUP** | Hosted Vercel demo, or any run with an empty database | A full 06:00–17:00 Miami day (26 August 2026). Peak-hour temps are from a real FortyGuard pull; other hours use a diurnal curve so the 12-hour story never goes blank. |
| **LIVE** | Local run after a FortyGuard pull | Today's hours from the Temperature API, starting at the current Florida hour. |

The pipeline **can** move to the latest day. The hosted demo **does not auto-refresh**, on purpose:

- FortyGuard heatmap jobs take minutes. Vercel functions time out at 30 seconds.
- A live pull spends API credits. Reloading the page for every judge would burn the key.
- Judges need a reliable 12-hour comparison, not an empty screen if the API is slow.

**Load today on your machine** (needs `FORTYGUARD_API_KEY` in `.env`):

```bash
python -m backend.scripts.fetch_all_sites --hours 12
# or, with the API running:
# click "Load today" on the dashboard, or POST /demo/refresh-live
```

The dashboard chip shows **BACKUP** or **LIVE** so the source is never ambiguous.

## Challenge tracks

**Primary track**

- **Industrial & Enterprise (Track 03)** — same-day heat operations for multi-site construction / HSE managers

**Secondary tracks**

- **Agentic AI (Track 06)** — structured risk outputs → supervisor briefing & Q&A that explains (not recalculates) decisions
- **Data Analysis & Correlation (Track 07)** — site-vs-site thermal differences that a single city forecast cannot show

## Why FortyGuard

City weather is too coarse for site-level safety decisions. FortyGuard's Temperature API® gives polygon heatmaps and environmental parameters (including wet-bulb, apparent temperature, and humidity) at construction-site scale — including forecasts up to 12 hours ahead.

**Proof (Miami metro, same hour):** Doral, Brickell, and Miami Beach diverged by **~1.3°C** mean site temperature on live API data. Same city. Different work decision.

## Product snapshot

| Screen | What a manager sees |
| --- | --- |
| Sites map | All sites with current risk status |
| Site × hour grid | Green / amber / red by workload for the 12-hour window |
| Work type | Light / Moderate / Heavy outdoor work |
| Today's moves | What to prioritize, when, and where |
| Daily brief | Plain-language summary of the calculated plan |

## Repo layout

```
backend/                   # FortyGuard client, SQLite, risk engine, API
  app/                     # FastAPI app, pipeline, safety logic
  app/safety/              # Risk bands, recommendations, AI explainer
  safety/METHODOLOGY.md    # OSHA/NIOSH sources — thresholds not invented
  data/sites.json          # Five Miami-metro construction sites
  data/fixtures/           # Backup demo day (judging if live API is unavailable)
  scripts/                 # Fetch live data, prove-idea, load-fixtures
frontend/dashboard/        # Manager dashboard (source)
public/                    # Same dashboard, copied for Vercel static hosting
api/                       # Vercel Python entrypoint
vercel.json                # Routes API paths to the Python function
requirements.txt           # Python deps for Vercel
.env.example               # API keys (copy to .env)
```

More detail: [`backend/README.md`](backend/README.md) · Dashboard: [`frontend/README.md`](frontend/README.md) · Safety sources: [`backend/safety/METHODOLOGY.md`](backend/safety/METHODOLOGY.md)

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Live dashboard |
| `GET` | `/planner?workload=heavy` | Sites, 12h risk timeline, today's actions |
| `GET` | `/planner/snapshot` | Same as `/planner` |
| `GET` | `/planner/brief` | Text operations brief |
| `POST` | `/planner/ask` | Explain calculated results (`{"question":"...","workload":"heavy"}`) |
| `GET` | `/sites` | Site polygons + metadata |
| `GET` | `/health` | Data mode, whether live refresh is available |
| `POST` | `/demo/load-fixtures` | Reload backup demo data |
| `POST` | `/demo/refresh-live` | Pull today from FortyGuard (local + API key only) |

## Team

Built for FortyGuard Hackathon '26 by [Myra Rafiq](https://www.linkedin.com/in/myrarafiq/), [Aleezah Ahmad](https://www.linkedin.com/in/aleezah-ahmad-483b8b232/), and [Kayan Rafiq](https://www.linkedin.com/in/kayanrafiq/) :)

FortyGuard tells us what the heat will be.
HeatGuard turns that intelligence into **today's operating plan**.

---

*Submission for [FortyGuard Hackathon '26](https://www.fortyguard.com/hackathon26) · Powered by the FortyGuard Temperature API®*
