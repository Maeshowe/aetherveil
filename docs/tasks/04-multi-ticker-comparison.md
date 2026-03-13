# Task 04 — Multi-Ticker Comparison View

## Priority: MEDIUM
## Status: TODO

## Problem
Overview page shows a flat table. No way to visually compare tickers across multiple
dimensions (U score, regime, z-scores) or see clusters of similar behavior.

## Goal
Add interactive comparison visualizations to the Overview page or as a separate
"Compare" page.

## Key Files
- `src/obsidian/dashboard/views/overview.py` — extend or new page
- `src/obsidian/dashboard/data.py` — data helpers

## Visualizations
1. **U Score Scatter** — all tickers plotted by U percentile, colored by regime
2. **Z-Score Radar** — overlay multiple tickers' z-score profiles
3. **Regime Distribution Pie** — how many tickers in each regime today
4. **Regime Transition Matrix** — from yesterday's regime to today's (if batch processed)

## Acceptance Criteria
- [ ] At least 2 comparison visualizations implemented
- [ ] Interactive (hover shows ticker details)
- [ ] Works with current session_state data (no new API calls)
