# Changelog

All notable changes to OBSIDIAN MM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-02-08

### Added - Focus Universe (Phase 13)

#### FRED Client
- **FREDClient** — New async API client for Federal Reserve Economic Data
  - `get_release_dates()` for CPI (release_id=10) and NFP (release_id=50) dates
  - API key injection and rate limiting
  - **Optional** — pipeline degrades gracefully without FRED key (FOMC + earnings only)

#### FMP Client Extensions
- **3 new methods** on `FMPClient`:
  - `get_etf_holdings(symbol)` — ETF constituent holdings by weight
  - `get_earnings_calendar(date_from, date_to)` — Upcoming earnings reports
  - `get_sp500_constituents()` — S&P 500 member list

#### Structural Focus Module (`universe/structural.py`)
- **IndexConstituent** dataclass for ETF top-N holdings
- `fetch_structural_focus(fmp, etf)` — Top-N by weight (SPY:15, QQQ:10, DIA:10)
- `fetch_all_structural_focus(fmp)` — All ETFs in parallel
- `deduplicate_structural_tickers()` — Cross-ETF overlap resolution (keeps highest weight)
- IWM explicitly excluded per spec

#### Events Module (`universe/events.py`)
- **EventEntry** dataclass with event_type, event_date, ticker, description
- `fetch_earnings_events()` — FMP earnings calendar ±1 trading day window
- `fetch_macro_events()` — FRED CPI/NFP release dates (optional)
- `get_fomc_events()` — Hardcoded FOMC dates for 2025-2026
- `fetch_all_events()` — Combines all event sources

#### Two-Pass Pipeline (Orchestrator Refactor)
- **Pass 1**: Structural + Event FOCUS update (before main fetch)
  - Ephemeral FMP/FRED clients per run
  - Promotes structural and event tickers to FOCUS tier
  - FRED failure does not block pipeline
- **Main**: Fetch + Process all active tickers (CORE + FOCUS)
- **Pass 2**: Stress check on results
  - Promotes tickers meeting stress thresholds:
    - U ≥ 70 (unusualness percentile)
    - |Z_GEX| ≥ 2.0 (gamma exposure)
    - DarkShare ≥ 0.65 (dark pool share)
    - |Z_block| ≥ 2.0 (block intensity)
  - Increments inactive counter for non-stressed FOCUS tickers
  - Expires tickers inactive 3+ consecutive days
  - Enforces 30-ticker FOCUS cap (structural protected, then by score + |Z_GEX|)

#### DiagnosticResult Enhancement
- **New field**: `raw_features: dict[str, float]` — Actual feature values (not z-scores)
- Enables stress check to read dark_share from raw features (bug fix)
- Included in `to_dict()` serialization

#### UniverseManager Extensions
- `promote_if_stressed()` gains `z_block` parameter
- New method: `enforce_focus_cap(max_focus=30, scores, z_gex_values)`
  - Priority-based eviction: structural always stays → highest U_t → highest |Z_GEX|

#### Dashboard Focus Decomposition
- **Focus Decomposition** panel on Daily State page (CORE tickers only)
- Summary: total focus count with structural/stress/event breakdown
- Table: Ticker, Reason, Details, Days Inactive
- `get_focus_summary()` and `get_focus_entries()` data layer functions

#### Configuration
- `fred_api_key: str | None` — Optional FRED API key
- `fred_rate_limit: int = 5` — FRED requests/second

### Testing
- **80 new tests** (412 → 492 total)
  - FRED client: 7 tests
  - FMP extensions: 8 tests
  - Structural module: 19 tests
  - Events module: 24 tests
  - UniverseManager extensions: 9 tests
  - Orchestrator two-pass: 8 tests
  - Dashboard data layer: 5 tests

---

## [0.1.0] - 2026-02-08

### Added - Core Engine (Phases 4-8)

#### Phase 4: Baseline System
- **Baseline class** for rolling statistics and z-score normalization
  - 63-day rolling window with expanding window for cold start
  - Minimum 21 observations required per spec
  - Drift detection with 10% threshold
- **BaselineState enum** (EMPTY / PARTIAL / COMPLETE)
- **BaselineStats dataclass** for statistics tracking
- **39 comprehensive tests** for baseline system

#### Phase 5: Scoring System
- **Scorer class** for unusualness scoring
  - Weighted absolute z-score sum (S_t)
  - Percentile mapping to [0, 100] scale (U_t)
  - Fixed diagnostic weights (NOT renormalized)
- **InterpretationBand enum** (Normal / Elevated / Unusual / Extreme)
- **ScoringResult dataclass** for scoring output
- **FEATURE_WEIGHTS constant** with fixed allocations
- **33 comprehensive tests** for scoring system

#### Phase 6: Regime Classifier
- **Classifier class** with 7 priority-ordered regime rules
  - Γ⁺ (Gamma-Positive Control)
  - Γ⁻ (Gamma-Negative Liquidity Vacuum)
  - DD (Dark-Dominant Accumulation)
  - ABS (Absorption-Like)
  - DIST (Distribution-Like)
  - NEU (Neutral / Mixed)
  - UND (Undetermined)
- **RegimeType enum** with descriptions and interpretations
- **RegimeResult dataclass** with triggering conditions
- **31 comprehensive tests** for classifier

#### Phase 7: Explainability Engine
- **Explainer class** for human-readable output generation
- **DiagnosticOutput dataclass** with formatting methods
  - `format_full()`: Complete diagnostic text
  - `format_regime()`: Regime section
  - `format_score()`: Score and drivers section
  - `to_dict()`: Structured JSON output
- **ExcludedFeature dataclass** for transparency
- **22 comprehensive tests** for explainability

#### Phase 8: CLI Interface
- **Command-line interface** using argparse
  - `obsidian diagnose <ticker>`: Run full diagnostic
  - `obsidian version`: Show version information
- **Command-line arguments**:
  - `--date`: Specify date (YYYY-MM-DD)
  - `--format`: Output format (text or json)
  - `--cache-dir`: Cache directory path
  - `--no-cache`: Skip cache
- **24 comprehensive tests** for CLI

### Added - Pipeline & Dashboard (Phases 9-11)

#### Phase 9: Data Pipeline
- **Fetcher** for multi-source async API data retrieval (5 sources per ticker)
- **Processor** with full feature extraction and diagnostic engine pipeline
  - Data normalization for UW dark pool prints, Greek exposure, Polygon bars
  - `DiagnosticResult` dataclass with `to_dict()` serialization
- **Orchestrator** coordinating Universe, Fetcher, and Processor
  - `run_diagnostics()` for batch multi-ticker processing
  - `run_single_ticker()` for ad-hoc analysis
  - Automatic FOCUS universe updates from stress signals
- Retry with exponential backoff for transient API failures (429, 502, 503, 504)
- Corrupted parquet cache resilience (graceful skip)
- `_safe_last()` helper for safe Series access (no IndexError on empty data)

#### Phase 10: Streamlit Dashboard
- **Dashboard application** with 4 interactive pages
  - Daily State: regime badge, unusualness gauge, z-score breakdown
  - Historical Regimes: timeline chart, distribution, transition matrix
  - Drivers & Contributors: waterfall chart, feature contribution table
  - Baseline Status: per-feature data quality indicators
- **Async-to-sync bridge** (`_run_async`) using ThreadPoolExecutor
- Sidebar with ticker selection, date picker, fetch/run controls

#### Phase 11: Multi-Ticker & Universe System
- **UniverseManager** with two-tier CORE + FOCUS system
  - CORE tickers: SPY, QQQ, IWM, DIA (always active)
  - FOCUS promotion rules: structural (index weight), stress signals, calendar events
  - FOCUS expiry after 3 consecutive inactive days
- `process_all()` and `fetch_all()` for multi-ticker batch processing
- Instrument isolation enforced across all pipeline stages

#### Phase 11 (continued): Edge Case Hardening
- **RateLimiter lazy initialization** (Python 3.10+ compatible)
- **Retry with exponential backoff** (1s/2s/4s) for transient HTTP errors
- **Corrupted cache resilience** — read() returns None, read_range skips
- **None guards** in dashboard pages for missing z_scores/explanation
- All `print()` replaced with proper `logging` in orchestrator and processor

### Added - Documentation
- **README.md**: Comprehensive project overview
  - Quick start guide
  - Architecture diagram
  - Example output
  - Design principles
- **USER_GUIDE.md**: End-user documentation
  - Installation instructions
  - Running diagnostics
  - Understanding output
  - Regime type descriptions
  - Unusualness score interpretation
  - Limitations and FAQ
- **API.md**: Developer API reference
  - Complete API documentation
  - Usage examples
  - Error handling
  - Configuration
- **CHANGELOG.md**: Version history (this file)

### Added - Earlier Phases (1-3)
*(From previous sessions)*

#### Phase 1: Config & Secrets
- Pydantic-based settings management
- Environment variable support (.env)
- API key validation

#### Phase 2: API Client Layer
- Async HTTP client with httpx
- Rate limiting and connection pooling
- Client modules for Unusual Whales, Polygon, FMP

#### Phase 3: Raw Cache
- Parquet-based immutable storage
- Instrument-isolated caching
- Fast columnar I/O with pyarrow

#### Phase 3: Feature Extraction
- **5 feature modules**, **11 features total**:
  - `dark_pool.py`: DarkShare, Block Intensity
  - `greeks.py`: GEX, DEX, Vanna, Charm
  - `price.py`: Efficiency, Impact
  - `venue.py`: Venue Mix
  - `volatility.py`: IV Skew, IV Rank

### Testing
- **412 tests** across all modules (at Phase 12 completion)
  - Engine tests: 125 (baseline, scoring, classifier, explainability)
  - Feature tests: 77 (dark pool, greeks, price, venue, volatility)
  - Pipeline tests: 46 (orchestrator, fetcher, processor)
  - Universe manager tests: 38
  - CLI tests: 31
  - Cache tests: 29
  - Client tests: 43 (base, UW, Polygon, FMP)
  - Config tests: 7
  - Memory store tests: 16
- All tests passing
- Comprehensive edge case coverage
- NaN handling verification

### Technical Stack
- **Python**: 3.12+
- **Dependencies**:
  - httpx (async HTTP)
  - pandas (DataFrames)
  - pydantic (settings)
  - pyarrow (Parquet)
  - streamlit (dashboard)
  - plotly (charts)
  - pytest (testing)

---

## [Unreleased]

### Planned - Features
- Regime Transition Matrix (RTM)
  - Empirical transition probabilities
  - Self-transition (persistence) analysis
  - Transition entropy calculation
- Baseline drift alerts
- Export to CSV/JSON
- API endpoint for programmatic access

---

## Version History

### Version Numbering

- **0.x.x**: Alpha — Core engine development
- **1.x.x**: Beta — Dashboard and full integration
- **2.x.x**: Production — Public release

### Release Notes

**0.2.0 (Current)**: Focus Universe — Two-pass pipeline (Phase 13)
- FRED client for macro event detection
- Structural focus from ETF top-N holdings
- Event focus from earnings, FOMC, CPI/NFP
- Stress-based FOCUS promotion with 4 thresholds
- 30-ticker cap with priority eviction
- Dashboard Focus Decomposition panel
- 492 tests passing

**0.1.0**: Full diagnostic engine with dashboard (Phases 1-12)
- Baseline, Scoring, Classification, Explainability systems operational
- CLI with full pipeline integration
- Streamlit dashboard with 4 interactive pages
- Multi-ticker batch processing with CORE + FOCUS universe
- Concurrent data fetching and processing

**Next (0.3.0)**: Advanced features
- Regime Transition Matrix
- Baseline drift detection alerts
- Export to CSV/JSON

---

## Contributing

This is a private project. For internal development:

1. Create feature branch from `main`
2. Implement changes with tests
3. Update CHANGELOG.md under [Unreleased]
4. Submit pull request with description

---

## Semantic Versioning

Given a version number MAJOR.MINOR.PATCH:

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

Pre-release versions: `0.x.x` (alpha/beta)

---

## Migration Guide

### From 0.0.x to 0.1.0

**Breaking Changes**: None (initial release)

**New Features**:
- Complete diagnostic engine API
- CLI interface
- Comprehensive documentation

**Deprecations**: None

---

## License

Proprietary. All rights reserved.

---

## Acknowledgments

- Claude Code (Anthropic) for development assistance
- Market microstructure research community
- Open-source Python ecosystem

---

*Last updated: 2026-02-08*
*Maintained by: AETHERVEIL Development Team*
