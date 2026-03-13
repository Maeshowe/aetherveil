# Task 01 — Batch Process All Cached Dates

## Priority: CRITICAL
## Status: TODO

## Problem
The Historical Regimes page, Feature Trends, and Day-over-Day comparison all rely on
`get_cached_diagnostic()` which reads from `st.session_state`. Currently the user must
click "Run (cached)" once per date to populate history. With 25+ days of cached data,
this is unusable.

## Goal
Add a "Process All Cached Dates" button to the sidebar that iterates over all cached
parquet dates for the selected ticker and runs `processor.process_ticker()` for each,
storing results in session_state.

## Key Files
- `src/obsidian/dashboard/app.py` — sidebar button
- `src/obsidian/dashboard/data.py` — new `batch_process_cached()` helper
- `src/obsidian/cache/parquet_store.py` — `list_dates()` to discover cached dates
- `src/obsidian/pipeline/processor.py` — `process_ticker()` for cache-only processing

## Acceptance Criteria
- [ ] "Process All Dates" button in sidebar
- [ ] Progress bar showing processing status
- [ ] After completion, Historical Regimes shows full timeline
- [ ] Feature Trends sparklines populate
- [ ] Day-over-Day comparison works automatically
- [ ] No API calls — purely cache-based
