# Safety methodology (Person 2)

## Sources (do not invent thresholds)

HeatGuard maps FortyGuard environmental data to published occupational heat guidance:

| Source | What we use |
| --- | --- |
| [OSHA — Heat Hazard Recognition](https://www.osha.gov/heat-exposure/hazards) | Workload categories (light / moderate / heavy / very heavy) and examples |
| NIOSH / ACGIH via OSHA Table 2 | Action Limit (unacclimatized) and TLV (acclimatized) as **effective WBGT °C** by workload |
| Plan Midday Break | Recommended outdoor pause **12:30–15:00** when site risk is amber/red — operational guidance (OSHA: schedule strenuous work in cooler hours). **Not Florida statute.** Florida has no statewide midday outdoor-work ban; UAE/Abu Dhabi-style midday rules inspired the product feature. |

We do **not** invent numeric cutoffs. Limits below are copied from OSHA’s simplified NIOSH/ACGIH table.

### Workload → effective WBGT limits (°C)

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
| Air temperature | heatmap `temp_c_mean` / tiles | Yes |
| Humidity / evaporative cooling | `wet_bulb_temperature_celsius`, `relative_humidity_percent` | Yes |
| Radiant / solar | `solar_ghi` (clear-sky) | Partial — not globe temperature |
| Wind | — | **Not provided** |

## Screening WBGT used in code

Because globe temperature and wind are unavailable, we compute a **documented screening estimate** (not a lab WBGT meter reading):

```text
screening_wbgt_c = 0.7 * Tw + 0.3 * Ta
```

- `Tw` = FortyGuard wet-bulb (°C)  
- `Ta` = site mean air temperature (°C) from the heatmap  

When `solar_ghi` is high (≥ 600 W/m²), we apply a small radiant bump of **+0.5 °C** to the screening value (conservative outdoor sun adjustment), still below the “Heat Index +7.5 °C in sun” note OSHA cites for heat-index screening — we keep this tiny and labeled.

**Label every risk result:** `method: screening_wbgt_estimate` so judges and managers know this is screening guidance, not a certified WBGT instrument.

## Risk bands (Green / Amber / Red)

For the selected workload:

| Band | Rule |
| --- | --- |
| **green** | `screening_wbgt < Action Limit` |
| **amber** | `Action Limit ≤ screening_wbgt < TLV` |
| **red** | `screening_wbgt ≥ TLV` |
| **unknown** | Missing Tw or Ta → do not invent a color |

Default planning assumption: treat workers as needing **Action Limit** caution (many construction crews include new/unacclimatized workers). Recommendations escalate earlier rather than later.

## Work intensity definitions (OSHA examples, construction-focused)

- **light** — standing watch, slow walking, minimal arm work  
- **moderate** — general carpentry with hand tools, continuous walking, painting  
- **heavy** — carrying loads, shoveling, roofing, mixing cement, stacking lumber  
- **very_heavy** — intense digging, climbing with loads (supported; UI focuses on light/moderate/heavy)

## Recommendation rules (explainable)

Each action cites inputs (`screening_wbgt`, limits, hour, site):

1. Prefer **heavy** outdoor work in the coolest green/amber morning windows.  
2. If hour is in **12:30–15:00** and risk is amber/red → recommend **midday outdoor break / shift to shaded or indoor tasks**.  
3. Red hours → stop or sharply reduce outdoor heavy work; move to light tasks or reschedule.  
4. Compare sites at the same hour → answer “best site for heavy work at 10 AM”.  
5. Missing data → skip that hour/site; never treat null as 0.

## AI rule (Day 8)

The AI brief / Q&A receives **only** the already-calculated planner JSON.  
Prompts forbid inventing temperatures, WBGT, risk colors, or thresholds.  
If the model cannot answer from the payload, it must say so.
