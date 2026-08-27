# Heat Safety Planner — Person 3 (frontend / product)

Same-day heat planner for Florida construction sites. This folder is the **manager-facing dashboard** that turns backend data and Person 2's heat-risk output into a simple visual work-planning tool.

It does **not** call FortyGuard directly and does **not** calculate heat risk.

## What the frontend needs to show

| Component                   | What we use it for                                                    |
| --------------------------- | --------------------------------------------------------------------- |
| **Site map**                | Show all Florida construction sites and their current risk status     |
| **Site cards**              | Show site name, temperature and risk at a glance                      |
| **12-hour timeline**        | Show how heat/risk changes throughout the workday                     |
| **Heatmap**                 | Display FortyGuard's per-tile GeoJSON temperature data when available |
| **Work intensity**          | Let user select Light / Moderate / Heavy work                         |
| **Today's Recommendations** | Show Person 2's calculated work recommendations                       |
| **AI Supervisor Brief**     | Later: summarize the calculated plan in plain English                 |

The goal is **not to build another weather dashboard**.

The manager should open the application and understand in about **10 seconds**:

> Which sites need attention, when heat risk increases, and when outdoor work should be prioritized.

## Current proof of concept

ex)

Live Day 1–2 result at the same time:

**2026-08-26 2:00 PM — Miami metro**

| Site        | Mean temperature |
| ----------- | ---------------: |
| Doral       |          32.11°C |
| Brickell    |          31.26°C |
| Miami Beach |          30.84°C |

**Spread: 1.27°C**

This is our provisional GO result:

> Same metro + same time → different hyperlocal site temperatures.

The frontend should eventually make this difference immediately visible rather than forcing the user to compare numbers.

---

## Data sources

Clean backend API:

```text
GET /sites
GET /hours?site_id=brickell
GET /planner/snapshot
```

Run backend locally:

```bash
uvicorn backend.app.main:app --reload --app-dir .
```

Consume these endpoints.

Note: 
- Never calculate safety thresholds in the frontend.
- Need Person 2 will add the **risk classification and recommendations** later.

---

## Day 1–2: understand and prove the visual story

* Confirm the frontend can read `GET /sites`.
* Confirm the frontend can read stored hourly data.
* Display Brickell, Miami Beach and Doral.
* Show the three sites on the same screen.
* Display mean temperature for the shared test hour.
* Make the **1.27°C site-to-site difference** easy to see.
* Decide how sites will be visually distinguished once Person 2 supplies risk levels.

Day 1–2 goal:

> Make **same city + same time + different site conditions** visually obvious.

---

## Day 3: design the dashboard

Build/mock up **one primary manager dashboard**.

Suggested layout:

```text
------------------------------------------------
HEAT SAFETY PLANNER
Today's Florida Construction Operations
------------------------------------------------

[              SITE MAP                    ]

   Brickell       Miami Beach       Doral
   🟡 31.3°C      🟢 30.8°C         🔴 32.1°C

------------------------------------------------
SELECTED SITE: BRICKELL

12-HOUR HEAT / RISK OUTLOOK

7  8  9  10  11  12  1  2  3  4  5  6
🟢 🟢 🟡  🟡   🟠  🔴  🔴 🔴 🟠 🟡 🟡 🟢

Work intensity:
[ Light ] [ Moderate ] [ Heavy ]

------------------------------------------------
TODAY'S RECOMMENDATIONS

• Prioritize heavy outdoor work early.
• Heat risk increases later in the morning.
• Site X offers better conditions at XX:XX.

------------------------------------------------
AI SUPERVISOR BRIEF

[ Added later ]
------------------------------------------------
```

**Important:** the risk colors above are illustrative only.

Do not derive Green / Amber / Red from temperature yourself. Person 2 supplies the risk classification.

---

## Frontend data contract

From Person 1, each hourly record may include:

```text
temp_c_min
temp_c_mean
temp_c_max
tile_count

wet_bulb_temperature_celsius
apparent_temperature_celsius
relative_humidity_percent
heat_index_celsius

missing_fields
api_timestamp
```

Important rules:

* Never treat `null` as `0`.
* Display unavailable data as `—` or `Unavailable`.
* Do not invent missing environmental values.
* Use the backend timestamps rather than calculating FortyGuard time yourself.
* Prefer `temp_c_mean` for the simple site temperature display.
* `temp_c_max` can help show site hotspots.
* Do not independently turn temperature into a safety rating.

---

## Information needed from Person 2

Person 3 eventually needs Person 2 to provide something similar to:

```text
site_id
timestamp
work_intensity
risk_level
risk_reason
recommended_action
```

For example:

```text
site_id: brickell
timestamp: 10:00
work_intensity: heavy
risk_level: high
risk_reason: ...
recommended_action: ...
```

The exact schema can change.

---

## Day 4: one site working

Start with **Brickell only**.

Build:

* Site name
* Current/selected-hour temperature
* Min / mean / max
* 12-hour timeline
* Work-intensity selector
* Risk level from Person 2
* Recommended action from Person 2

Milestone:

> One site works **backend → risk → recommendation → dashboard**.

Functionality matters more than appearance.

---

## Day 5: multiple sites

Add:

* Brickell
* Miami Beach
* Doral
* Any additional approved test sites

The manager should be able to:

* See all sites on the map
* See their current risk
* Select a site
* View its 12-hour timeline
* Compare sites
* Identify which site has better conditions at a particular time

---

## Day 6: manager experience

Turn the prototype into a usable dashboard.

Prioritize:

1. **Which sites need attention?**
2. **When does risk increase?**
3. **What should the manager do?**

Avoid filling the screen with raw weather variables.

Detailed environmental data can sit behind an expandable **Details** section.

The main screen should prioritize decisions.

Target:

> A construction manager understands today's situation within **10 seconds**.

---

## Day 7: frontend testing

Test:

* Missing hourly data
* `null` environmental values
* API unavailable
* Site with no forecast
* Different work intensities
* Risk changing throughout the day
* Multiple sites with similar risk
* Multiple sites with very different risk
* Mobile/laptop sizing

Never display fake data as live data.

If data is unavailable, say so.

---

## Day 8: AI Supervisor Brief

Only add this after the dashboard works.

Person 2/backend should provide structured calculated results.

The frontend sends/displays those results for the AI summary.

Example:

> **Today's Supervisor Brief**
>
> Doral has the highest heat risk during the afternoon. Prioritize strenuous outdoor work earlier in the day...

Possible questions:

* “Which site has the highest risk today?”
* “Where should we prioritize heavy work this morning?”
* “Why is Doral higher risk?”
* “Which site has the best afternoon conditions?”

The AI should **explain existing calculated results**, not create safety classifications itself.

---

## Day 9: polish

No new features.

Focus on:

* Clean layout
* Readable map
* Clear risk indicators
* Simple timeline
* Useful recommendations
* Loading states
* Error states
* Consistent units
* Responsive layout
* README
* Demo reliability

---

## Day 10: demo

Build the demo around one story:

```text
Normal Florida weather forecast
        ↓
Several construction sites in the same metro
        ↓
FortyGuard shows hyperlocal differences
        ↓
Person 2 converts conditions into heat risk
        ↓
Dashboard shows when/where risk changes
        ↓
Manager receives today's recommended work plan
```

The key screen should make this immediately understandable:

> **Different sites → different heat conditions → different risk → different work decisions.**

## Person 3's main rule

Do not try to make the frontend smarter than the backend.

Your job is to make the team's intelligence **obvious, useful and easy to act on**.

The finished product should feel less like a weather application and more like a **construction operations dashboard**.
