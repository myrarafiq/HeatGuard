# HeatGuard

### Same-Day Heat Safety Planner for Construction Sites

**FortyGuard Hackathon '26 submission** — *Building the World's Temperature AI*

> It's 6:30 AM. You manage five Florida construction sites. A normal weather app gives you one city forecast. Your workers need more than that.

**HeatGuard** turns FortyGuard's hyperlocal temperature intelligence into today's operating plan: which sites are safest for outdoor work, when risk peaks, and what a supervisor should prioritize before the heat does.

---

## The problem

Construction managers plan outdoor work with city-level weather. On a hot day in Miami, that forecast looks the same for Brickell, Doral, and Miami Beach — but the sites do not.

Shade, asphalt, waterfront wind, and urban heat islands change conditions block by block. Workers feel that difference. Schedules usually don't.

## What we're building

Every morning, HeatGuard:

1. Loads each site's polygon and work context  
2. Pulls the next **12 hours** of FortyGuard hyperlocal data (heatmap + environmental parameters)  
3. Converts conditions into a **heat-risk assessment** by workload (light / moderate / heavy)  
4. Compares sites side by side  
5. Recommends **when and where** outdoor work should happen  
6. Optionally explains the plan with an AI brief that only narrates calculated results — it never invents safety math

**Demo story in one line:** different heat → different risk → different recommended work plan.

## Challenge tracks

**Primary track** (what we're judged on)

- **Industrial & Enterprise** — same-day heat operations for multi-site construction / HSE managers

**Secondary tracks**

- **Agentic AI** — structured risk outputs → supervisor briefing & Q&A that explains (not recalculates) decisions  
- **Data Analysis & Correlation** — site-vs-site thermal differences that a single city forecast cannot show

## Why FortyGuard

City weather is too coarse for site-level safety decisions. FortyGuard's Temperature API® gives us polygon heatmaps and environmental parameters (including wet-bulb, apparent temperature, and humidity) at construction-site scale — including forecasts up to 12 hours ahead.

**Early proof (Miami metro, same hour):** Doral, Brickell, and Miami Beach already diverged by **~1.3°C** mean site temperature. Same city. Different work decision.

## Product snapshot (MVP)

| Screen | What a manager sees |
| --- | --- |
| Sites map | All sites with current heat status |
| 12-hour timeline | Risk by hour for the selected workload |
| Work type | Light / Moderate / Heavy outdoor work |
| Today's actions | What to prioritize, when, and where |
| Daily brief | Plain-language summary of the calculated plan |

## Repo layout

```
backend/                 # Person 1 + Person 2 (API, FortyGuard, risk, recommendations, AI)
  app/safety/            # Risk engine + recommendation + AI explainer
  safety/METHODOLOGY.md  # OSHA/NIOSH sources — thresholds not invented
  data/fixtures/         # Demo backup day if live API fails
theplan.txt              # Team build plan
```

Backend + safety API docs: [`backend/README.md`](backend/README.md).  
Safety sources: [`backend/safety/METHODOLOGY.md`](backend/safety/METHODOLOGY.md).

**Person 3 (frontend)** plugs into `GET /planner?workload=heavy` — map, timeline, actions, and brief are already computed.

## Team

Built for FortyGuard Hackathon '26 by [Myra Rafiq](https://www.linkedin.com/in/myrarafiq/), [Aleezah Ahmad](https://www.linkedin.com/in/aleezah-ahmad-483b8b232/), and [Kayan Rafiq](https://www.linkedin.com/in/kayanrafiq/).

## What success looks like

A manager opens HeatGuard and, in about ten seconds, knows:

- which sites are hottest *right now*  
- which windows are safest for heavy outdoor work  
- what today's plan should be — and why

FortyGuard tells us what the heat will be.  
HeatGuard turns that intelligence into **today's operating plan**.

---

*Submission for [FortyGuard Hackathon '26](https://www.fortyguard.com/hackathon26) · Powered by the FortyGuard Temperature API®*
