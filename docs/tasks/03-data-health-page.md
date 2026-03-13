# Task 03 — Data Health Dashboard Page

## Priority: HIGH
## Status: TODO

## Problem
There's no visibility into cache health, collection gaps, or data quality from within
the dashboard. The `check_status.py` script provides this info from CLI, but the
dashboard should show it natively.

## Goal
Add a "Data Health" page to the dashboard showing cache statistics, collection status,
and per-ticker data completeness — essentially a dashboard version of `check_status.py`.

## Key Files
- `src/obsidian/dashboard/app.py` — add page to navigation
- `src/obsidian/dashboard/views/data_health.py` — new page (create)
- `src/obsidian/dashboard/data.py` — data helpers
- `src/obsidian/cache/parquet_store.py` — `get_cache_stats()`, `list_dates()`, `list_sources()`
- `scripts/check_status.py` — reuse `scan_ticker()` and `analyze_cache()` logic

## Sections
1. **Collection Summary** — total tickers, files, size, last run date
2. **Baseline Readiness** — progress bar (COMPLETE/PARTIAL/EMPTY counts)
3. **CORE Ticker Detail** — per-source date counts, gap detection
4. **FOCUS Ticker Overview** — condensed table, missing sources highlighted
5. **Gap Analysis** — missing trading days calendar view

## Acceptance Criteria
- [ ] Data Health page accessible from navigation
- [ ] Shows real-time cache statistics (no session_state dependency)
- [ ] CORE tickers show per-source counts (bars, dark_pool, greeks, iv_rank, quote)
- [ ] Gaps highlighted visually
