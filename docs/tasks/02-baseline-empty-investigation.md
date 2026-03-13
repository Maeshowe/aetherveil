# Task 02 — Baseline EMPTY Investigation (Dark Pool, Block, Venue)

## Priority: CRITICAL
## Status: RESOLVED (not a bug)

## Problem
Baseline Status page shows Block Intensity, Dark Pool Share, and Venue Mix as EMPTY
for DIA, despite the Mac Mini having 25 days of dark pool data cached. The processor
apparently fails to extract these features from the raw dark pool parquet files.

## Root Cause (Session 23)
**NOT a bug — insufficient accumulation time.**

- UW `/darkpool/recent` only returns current-day data (no historical backfill)
- After 25 collection runs, tickers have ~17 daily dark pool aggregates (some days
  had no prints for specific tickers, especially less-liquid ETFs like DIA)
- Spec requires N_min=21 non-NaN observations for valid baseline
- 17 < 21 → features correctly excluded from scoring
- Pipeline is working exactly as designed: "False negatives are acceptable.
  False confidence is not."

## Resolution
- ~4 more trading days of daily collection will naturally resolve this
- Improved Baseline Status dashboard to show:
  - Actual observation counts per feature (e.g., "17/21 obs")
  - "Need X more days" warning instead of just "EMPTY"
  - Estimated days remaining in Recommendations section
- File modified: `src/obsidian/dashboard/views/baseline_status.py`

## Acceptance Criteria
- [x] Root cause identified (insufficient accumulation, not a bug)
- [x] Dark pool features compute correctly from cached data (verified)
- [ ] Baseline shows COMPLETE for dark_share, block_intensity, venue_mix
      (will self-resolve after ~4 more trading days of collection)
- [ ] Scoring uses all 5 weighted features (blocked on above)
