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

Default assumption: **work clothing, CAF = 0**. The default is surfaced, not hidden.

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

Each action cites inputs (`effective_wbgt`, limits, work/rest code, hour, site):

1. Prefer **heavy** outdoor work in the coolest morning windows that are not `stop`.
2. Hour recommendation leads with the ACGIH cycle (`45/15`, `30/30`, `15/45`, or `stop`), not a vague “drink more water.”
3. If hour is in **12:30–15:00** and risk is amber/red → recommend **midday outdoor break / shift to shaded or indoor tasks**.
4. Compare sites at the same hour → answer “best site for heavy work at 10 AM”.
5. Missing data → skip that hour/site; never treat null as 0.

## AI rule (Day 8)

The AI brief / Q&A receives **only** the already-calculated planner JSON.  
Prompts forbid inventing temperatures, WBGT, risk colors, thresholds, or work/rest ratios.  
The brief must repeat the acclimatization assumption and must not call `peak_risk` “current.”  
If the model cannot answer from the payload, it must say so.
