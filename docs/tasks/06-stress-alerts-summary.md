# Task 06 — Stress Alerts & Threshold Summary

## Priority: MEDIUM
## Status: TODO

## Problem
The spec defines stress thresholds (U>=70, |Z_GEX|>=2.0, DarkShare>=0.65, |Z_block|>=2.0)
but the dashboard doesn't highlight when these are crossed. Users must manually scan the
Overview table to find stressed tickers.

## Goal
Add a prominent "Alerts" section to the Overview page (or a dedicated Alerts page)
that surfaces tickers crossing stress thresholds.

## Key Files
- `src/obsidian/dashboard/views/overview.py` — add alerts section
- `src/obsidian/dashboard/data.py` — alert computation helper
- `src/obsidian/pipeline/processor.py` — DiagnosticResult fields

## Spec Thresholds (from IDEA.md)
- U >= 70 (extreme unusualness)
- |Z_GEX| >= 2.0 (gamma stress)
- DarkShare >= 0.65 (dark pool dominance)
- |Z_block| >= 2.0 (block trade stress)

## Sections
1. **Active Alerts** — cards for each ticker crossing a threshold
2. **Threshold Heatmap** — matrix of tickers vs thresholds (red/green)
3. **Alert History** — which tickers triggered alerts over last N days (requires Task 01)

## Acceptance Criteria
- [ ] Stress thresholds clearly defined and configurable
- [ ] Tickers crossing thresholds highlighted prominently
- [ ] Visual distinction between severity levels
