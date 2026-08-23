# HeatGuard

### Same-Day Heat Safety Planner for Construction Sites

**FortyGuard Hackathon '26 submission** — *Building the World's Temperature AI*

> It's 6:30 AM. You manage five Florida construction sites. A normal weather app gives you one city forecast. Your workers need more than that.

**HeatGuard** turns FortyGuard's hyperlocal temperature intelligence into today's operating plan: which sites are safest for outdoor work, when risk peaks, and what a supervisor should prioritize before the heat does.

---

## Live demo

Dashboard and API are deployed on Vercel (see the project’s Vercel URL after deploy).

---

## The problem

Construction managers plan outdoor work with city-level weather. On a hot day in Miami, that forecast looks the same for Brickell, Doral, and Miami Beach — but the sites do not.

Shade, asphalt, waterfront wind, and urban heat islands change conditions block by block. Workers feel that difference. Schedules usually don't.

## What HeatGuard does

Every morning, HeatGuard:

1. Loads each site's polygon and work context  
2. Pulls the next **12 hours** of FortyGuard hyperlocal data (heatmap + environmental parameters)  
3. Converts conditions into a **heat-risk assessment** by workload (light / moderate / heavy)  
4. Compares sites side by side  
5. Recommends **when and where** outdoor work should happen  
6. Explains the plan with a supervisor brief and Q&A that only narrates calculated results — never invents safety math

**Demo story in one line:** different heat → different risk → different recommended work plan.

## Challenge tracks

**Primary track**

- **Industrial & Enterprise (Track 03)** — same-day heat operations for multi-site construction / HSE managers

**Secondary tracks**

- **Agentic AI (Track 06)** — structured risk outputs → supervisor briefing & Q&A that explains (not recalculates) decisions  
- **Data Analysis & Correlation (Track 07)** — site-vs-site thermal differences that a single city forecast cannot show

## Why FortyGuard

City weather is too coarse for site-level safety decisions. FortyGuard's Temperature API® gives us polygon heatmaps and environmental parameters (including wet-bulb, apparent temperature, and humidity) at construction-site scale — including forecasts up to 12 hours ahead.

**Proof (Miami metro, same hour):** Doral, Brickell, and Miami Beach diverged by **~1.3°C** mean site temperature on live API data. Same city. Different work decision.

## Product snapshot

| Screen | What a manager sees |
| --- | --- |
| Sites map | All sites with current risk status |
| 12-hour timeline | Risk by hour for the selected workload |
| Work type | Light / Moderate / Heavy outdoor work |
| Today's actions | What to prioritize, when, and where |
| Daily brief | Plain-language summary of the calculated plan |

## Repo layout

```
backend/                   # FortyGuard client, SQLite, risk engine, API
  app/                     # FastAPI app, pipeline, safety logic
  app/safety/              # Risk bands, recommendations, AI explainer
  safety/METHODOLOGY.md    # OSHA/NIOSH sources — thresholds not invented
  data/sites.json          # Five Miami-metro construction sites
  data/fixtures/           # Backup demo day (judging if live API fails)
  scripts/                 # Fetch, prove-idea, load-fixtures helpers
frontend/
  dashboard/               # Manager dashboard (index.html + assets)
  dashboard/template.txt   # Original wireframe
  README.md                # Dashboard design notes
vercel.json                # Vercel deploy config
theplan.txt                # Build plan
.env.example               # API keys (copy to .env)
```

More detail: [`backend/README.md`](backend/README.md) · Safety sources: [`backend/safety/METHODOLOGY.md`](backend/safety/METHODOLOGY.md)

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Live dashboard |
| `GET` | `/planner?workload=heavy` | Sites, 12h risk timeline, today's actions |
| `GET` | `/planner/snapshot` | Same as `/planner` |
| `GET` | `/planner/brief` | Text operations brief |
| `POST` | `/planner/ask` | Explain calculated results (`{"question":"...","workload":"heavy"}`) |
| `GET` | `/sites` | Site polygons + metadata |
| `POST` | `/demo/load-fixtures` | Reload backup demo data |

## Team

Built for FortyGuard Hackathon '26 by [Myra Rafiq](https://www.linkedin.com/in/myrarafiq/), [Aleezah Ahmad](https://www.linkedin.com/in/aleezah-ahmad-483b8b232/), and [Kayan Rafiq](https://www.linkedin.com/in/kayanrafiq/).

FortyGuard tells us what the heat will be.  
HeatGuard turns that intelligence into **today's operating plan**.

---

*Submission for [FortyGuard Hackathon '26](https://www.fortyguard.com/hackathon26) · Powered by the FortyGuard Temperature API®*
