# Safety methodology (Person 2)

## Sources (do not invent thresholds)

HeatGuard maps FortyGuard environmental data to published occupational heat guidance:

| Source | What we use |
| --- | --- |
| [OSHA — Heat Hazard Recognition](https://www.osha.gov/heat-exposure/hazards) | Workload categories (light / moderate / heavy / very heavy), Table 2 Action Limit / TLV, clothing adjustment factors |
| NIOSH / ACGIH via OSHA Table 2 | Action Limit (unacclimatized) and TLV (acclimatized) as **effective WBGT °C** by workload |
| ACGIH Screening Criteria for Heat Stress Exposure | Work/rest **allocation bands** (75–100% / 50–75% / 25–50% / 0–25% work) by workload and acclimatization |
| Plan Midday Break | Recommended outdoor pause **12:30–15:00** when site risk is amber/red — operational guidance (OSHA: schedule strenuous work in cooler hours). **Not Florida statute.** Florida has no statewide midday outdoor-work ban; UAE/Abu Dhabi-style midday rules inspired the product feature. |

We do **not** invent numeric cutoffs. Limits below are copied from OSHA’s simplified NIOSH/ACGIH table. Work/rest minutes are the arithmetic protective end of each published ACGIH **percent-work** band (75% → 45/15, 50% → 30/30, 25% → 15/45, 0–25% → stop). That conversion is not a new threshold.

### Workload → effective WBGT limits (°C)

OSHA Table 2 (continuous-work screening):

| Workload | Action Limit (unacclimatized) | TLV (acclimatized) |
| --- | ---: | ---: |
| light | 28 | 30 |
| moderate | 25 | 28 |
| heavy | 23 | 26 |
| very_heavy | 21 | 25 |

## What FortyGuard provides vs what WBGT needs

OSHA prefers on-site **WBGT** (dry bulb + natural wet bulb + black globe). FortyGuard gives us:

| Needed for full WBGT | FortyGuard field | Status |
| --- | --- | --- |
| Air temperature | heatmap tiles / `temp_c_p90` / `temp_c_max` / `temp_c_mean` | Yes — we screen on **hotspot**, not mean |
| Humidity / evaporative cooling | `wet_bulb_temperature_celsius`, `relative_humidity_percent` | Yes |
| Radiant / solar | `solar_ghi` (clear-sky) | Partial — not globe temperature |
| Wind | — | **Not provided** |

**Display-only (never used as Ta in the WBGT formula):** `apparent_temperature_celsius`, `heat_index_celsius`. OSHA: heat index is a less accurate substitute and does not replace WBGT.

## Screening air temperature (written down)

HSE screening uses the **hottest occupied area** of the polygon, not the site average.

Preference order (first available):

1. `temp_c_p90` — 90th percentile tile
2. `temp_c_max` — hottest tile
3. `temp_c_mean` — fallback only if hotspot stats are missing

Site mean is always stored as `temp_c_mean` and as `screening_wbgt_from_mean_c` for comparison. Same OSHA table — stricter **input**, not a new cutoff.

Every hour records `screening_air_temp_c` and `screening_air_temp_source`.

## Screening WBGT used in code

Because globe temperature and wind are unavailable, we compute a **documented screening estimate** (not a lab WBGT meter reading):

```text
screening_wbgt_c = 0.7 * Tw + 0.3 * Ta_hotspot
effective_wbgt_c = screening_wbgt_c + clothing_adjustment_c
```

- `Tw` = FortyGuard wet-bulb (°C)
- `Ta_hotspot` = screening air temperature above

When `solar_ghi` is high (≥ 600 W/m²), we apply a small radiant bump of **+0.5 °C** to the screening value (conservative outdoor sun adjustment), still below the “Heat Index +7.5 °C in sun” note OSHA cites for heat-index screening — we keep this tiny and labeled.

**Label every risk result:** `method: screening_wbgt_estimate` so judges and managers know this is screening guidance, not a certified WBGT instrument.

## Clothing adjustment (effective WBGT)

OSHA: add a clothing adjustment factor to measured WBGT **before** comparing to Table 2. Copied from [OSHA Heat Hazard Recognition](https://www.osha.gov/heat-exposure/hazards) (adapted from NIOSH 2016):

| Clothing | CAF (°C) |
| --- | ---: |
| Work clothing (baseline) | 0 |
| Cloth coveralls | 0 |
| SMS polypropylene coveralls | 0.5 |
| Polyolefin coveralls | 1.0 |
| Double-layer cloth clothing | 3.0 |
| Limited-use vapor-barrier coveralls | 11.0 |

Default assumption: **work clothing, CAF = 0**. Long sleeves and a hard hat are in that baseline (not an extra bump).

Optional dashboard flag **Extra PPE / coveralls** maps to one published coveralls row — **SMS polypropylene coveralls, +0.5°C** — not an invented “it feels hotter” fudge. Cloth (woven) coveralls are **+0°C** on the same OSHA table; we do not pretend cotton coveralls add heat. Other cited rows remain available via the `clothing` API parameter.

## Thermal Work Limit (not implemented)

TWL is **research notes only**. It is not a second scoring engine. TWL needs **wind speed** and **globe temperature**. FortyGuard provides neither. OSHA screening WBGT estimate (labeled) is the only risk engine.

## Acclimatization (surfaced, not methodology-only)

Default: **unacclimatized / new hires present.** OSHA: assume unacclimatized if workers have been doing the job for less than 1–2 weeks.

| Mode | Green | Amber | Red |
| --- | --- | --- | --- |
| **Unacclimatized (default)** | `effective_wbgt < Action Limit` | Action Limit ≤ WBGT < TLV | `effective_wbgt ≥ TLV` |
| **Acclimatized** (optional toggle) | `effective_wbgt < TLV` | — (not used) | `effective_wbgt ≥ TLV` (TLV is the red line) |

The planner JSON includes `assumption.label` so the manager sees the sentence:

> Planning assumption: unacclimatized / new hires present. Action Limit is the amber trip; TLV is the red line.

Query/API: `acclimatized=true` switches to TLV-as-red-line.

## now_risk vs peak_risk

| Field | Meaning |
| --- | --- |
| `now_risk` | Selected hour if the client passes `hour_local`; otherwise the Florida clock hour if present in the window; otherwise the first hour. **Not** “worst today.” |
| `now_hour_local` | Which hour `now_risk` refers to |
| `peak_risk` | Worst (red > amber > green) hour in the 12-hour window |
| `peak_hour_local` | Which hour `peak_risk` refers to |
| `current_risk` | Alias of `now_risk` (legacy field — still “now,” not peak) |

A site that is green at 7 AM and red at 2 PM is **now green, peak red**.

## Conservative site temperature (mean vs hotspot)

Every hour persists:

| Field | Meaning |
| --- | --- |
| `temp_c_mean` | Site average (tiles / stats) |
| `temp_c_max` / `temp_c_p90` | Within-site hotspot for screening |
| `tile_spread_c` | `max − min` inside the polygon |

OSHA cares about where people stand (roof, asphalt, unshaded slab). A 1.3°C **between-site** spread can flip a workload across a published limit; a 2–4°C **within-site** hotspot is the stronger FortyGuard story. Screening still uses the published OSHA table — hotspot is a stricter **input**, not a new cutoff.

## FortyGuard layer: TCM for hourly risk

Hourly OSHA/NIOSH screening uses **`analytic_type: "tcm"`** (snapshot) only. Wrong layer → confident wrong answer. Snapshot is the right layer for “what is it at 10 AM.”

Optional **duration** metrics are stored next to each hour and **never** enter `screening_wbgt_c`:

| Field | Meaning |
| --- | --- |
| `exceedance_hours_mean` / `_max` | Hours in the window above 30°C **air temperature** (or the configured `DURATION_THRESHOLD_C`) |
| `persistence_hours_max` | Longest continuous run above that threshold |
| `duration_used_in_risk` | Always `false` |

That is industrial (“how long does this site stay dangerous”). 30°C here is FortyGuard air-temperature duration, **not** the OSHA heavy Action Limit (23°C WBGT).

## City-forecast contrast (display-only)

One Open-Meteo Miami 2 m reading is stored beside the five site means for the same hour: `city_temp_c` vs `site_temp_c_mean` (`site_minus_city_c`). Planner JSON includes `city_contrast`. **Not** used as Ta in the WBGT formula.

## Polygon size vs heatmap granularity

Demo sites use `half_deg: 0.0025` (~555 m on a side) and **60 m** heatmap tiles so min/mean/max is a real distribution, not three noisy cells.

## Work/rest cycles (ACGIH allocation → minutes)

Green / amber / red is OSHA Table 2. Work/rest is a **separate** published table: ACGIH Screening Criteria for Heat Stress Exposure (WBGT °C).

Unacclimatized (Action Limit columns):

| Allocation | Shown as | Light | Moderate | Heavy | Very heavy |
| --- | --- | ---: | ---: | ---: | ---: |
| 75–100% work | 45/15 | 28.0 | 25.0 | — | — |
| 50–75% work | 30/30 | 28.5 | 26.0 | 24.0 | — |
| 25–50% work | 15/45 | 29.5 | 27.0 | 25.5 | 24.5 |
| 0–25% work | stop | 30.0 | 29.0 | 28.0 | 27.0 |

Acclimatized (TLV columns): light 31.0 / 31.0 / 32.0 / 32.5; moderate 28.0 / 29.0 / 30.0 / 31.5; heavy — / 27.5 / 29.0 / 30.5; very heavy — / — / 28.0 / 30.0.

Dashes mean that allocation is **not published** for that workload (e.g. unacclimatized heavy has no 75–100% / 45/15 row). The engine skips dashes and uses the next listed band — so heavy work with new hires is never treated as continuous under this table.

We pick the **least restrictive published row** whose limit is still ≥ effective WBGT. If every row is exceeded → `stop`.

Each hour includes `work_rest.code` (`45/15`, `30/30`, `15/45`, `stop`) plus `allocation` and `limit_c` so the recommendation is explainable.

## Risk bands (Green / Amber / Red)

Default planning assumption: unacclimatized (see table above). Missing Tw or hotspot Ta → **unknown**. Never treat null as 0.

## Work intensity definitions (OSHA examples, construction-focused)

- **light** — standing watch, slow walking, minimal arm work
- **moderate** — general carpentry with hand tools, continuous walking, painting
- **heavy** — carrying loads, shoveling, roofing, mixing cement, stacking lumber
- **very_heavy** — intense digging, climbing with loads (supported; UI focuses on light/moderate/heavy)

## Recommendation rules (explainable)

Each action cites inputs (`effective_wbgt`, limits, work/rest code, hour, site). `todays_actions` is a **four-move shift plan**, not a stack of per-site warnings:

1. **Do this morning** — which site, which hours, which workload (coolest morning window that is not `stop`).
2. **Pause / shade window** — 12:30–15:00 where the site is amber/red (operational, not Florida law).
3. **Do not do this afternoon** — which sites stay red after 15:00.
4. **Move work** — send the selected workload to the cooler site at 10:00; hold the hotter site for light/indoor.

Hour-level text still leads with the ACGIH cycle (`45/15`, `30/30`, `15/45`, or `stop`). Missing data → skip that hour/site; never treat null as 0.

## Threshold-flip test (demo GO)

The planner computes `threshold_flip` from **already-assessed hours** — it does not invent temperatures.

Preference order:

1. Same workload: Site A **green** (below Action Limit) and Site B **red** (at/above TLV)
2. Same workload: **amber vs red** (TLV flip) or **green vs amber** (Action Limit flip)
3. Same site: selected workload vs light/heavy — a Table 2 row change

On the backup demo day (heavy, unacclimatized, work clothing), **10:00** is the documented GO: Miami Beach stays **below the heavy TLV** (amber) while Doral is **at/above TLV** (red). That is the Industrial punchline — move heavy crews, don’t just show a 1.3°C table. **06:00** is the Action Limit cousin (Beach green, Doral amber). **14:00 Miami Beach** also flips **heavy red vs light green** on the same hour.

## Display-only: feels like

`apparent_temperature_celsius` / `heat_index_celsius` are shown as **feels like**. They **never** drive Green/Amber/Red. OSHA screening uses the WBGT estimate.

## AI rule (Day 8)

The AI brief / Q&A receives **only** the already-calculated planner JSON.  
Prompts forbid inventing temperatures, WBGT, risk colors, thresholds, or work/rest ratios.  
The brief must repeat the acclimatization assumption and must not call `peak_risk` “current.”  
If the model cannot answer from the payload, it must say so.
