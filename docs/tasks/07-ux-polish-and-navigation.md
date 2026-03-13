# Task 07 — UX Polish & Navigation Improvements

## Priority: LOW
## Status: TODO

## Problem
Various UX issues that reduce the dashboard's usability and professional feel:
- Navigation is radio buttons in sidebar (not ideal for 7+ pages)
- No loading states for long operations
- Version number hardcoded in multiple places
- No keyboard shortcuts or quick-switch between tickers

## Goal
Polish the dashboard UX to production quality.

## Key Files
- `src/obsidian/dashboard/app.py` — main layout, navigation, sidebar
- `src/obsidian/dashboard/views/*.py` — all view files

## Items
1. **Tab-based navigation** — replace radio buttons with `st.tabs()` or similar
2. **Auto-refresh** — after "Run (cached)", auto-refresh the current page
3. **Ticker quick-switch** — on Overview, clicking a ticker navigates to its Daily State
4. **Consistent loading** — all async operations show progress
5. **Version from single source** — read from `__init__.py` or `pyproject.toml`
6. **Responsive improvements** — better mobile/tablet layout
7. **Export** — download current view as PNG or PDF
8. **Tooltip consistency** — all charts have consistent hover formatting

## Acceptance Criteria
- [ ] Navigation supports 7+ pages cleanly
- [ ] Loading states on all async operations
- [ ] Version sourced from single location
