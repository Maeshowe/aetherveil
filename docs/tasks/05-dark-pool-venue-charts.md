# Task 05 — Dark Pool & Venue Breakdown Charts

## Priority: MEDIUM
## Status: TODO

## Problem
Dark pool data is collected and used for features, but the dashboard never shows the
raw dark pool breakdown — venue distribution, block trade sizes, dark pool share trend.
This is the most unique data OBSIDIAN has.

## Goal
Add dark pool-specific visualizations to the Drivers page or a new dedicated page.

## Key Files
- `src/obsidian/dashboard/views/drivers.py` — extend
- `src/obsidian/features/dark_pool.py` — feature extraction (reference)
- `src/obsidian/features/venue.py` — venue mix (reference)
- `src/obsidian/cache/parquet_store.py` — read raw dark pool parquet

## Visualizations
1. **Venue Mix Pie/Donut** — distribution across dark pool venues for today
2. **Dark Pool Share Timeline** — DarkShare % over last N days
3. **Block Trade Distribution** — histogram of trade sizes (block vs small)
4. **Volume Comparison** — dark pool volume vs lit exchange volume

## Acceptance Criteria
- [ ] At least 2 dark pool visualizations implemented
- [ ] Reads directly from cached parquet (not just z-scores)
- [ ] Shows actual venue names and percentages
