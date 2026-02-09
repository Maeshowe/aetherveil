# OBSIDIAN MM

**O**bservational **B**ehavioral **S**ystem for **I**nstitutional & **D**ealer-**I**nformed **A**nomaly **N**etworks — **M**arket **M**aker Regime Engine

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-504%20passing-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

> **Explainable microstructure diagnostics for retail quants**
> Deterministic, rule-based regime classification with full transparency

---

## What is OBSIDIAN MM?

OBSIDIAN MM is a **diagnostic engine** that analyzes daily market microstructure patterns to classify institutional and dealer behavior into explainable regimes. Unlike ML-based systems, every classification is:

- **Deterministic** — Same inputs → same outputs, always
- **Rule-based** — Priority-ordered conditional logic, no black boxes
- **Explainable** — Every output includes triggering conditions and top drivers
- **Non-predictive** — Diagnostic only; never forecasts prices or generates signals

### Key Features

✅ **7 Market Microstructure Regimes**
- Γ⁺ (Gamma-Positive Control) — Volatility suppression
- Γ⁻ (Gamma-Negative Liquidity Vacuum) — Amplification regime
- DD (Dark-Dominant Accumulation) — Institutional positioning
- ABS (Absorption-Like) — Sell pressure absorbed
- DIST (Distribution-Like) — Buy pressure distributed
- NEU (Neutral / Mixed) — Balanced state
- UND (Undetermined) — Insufficient data

✅ **Unusualness Scoring**
- Weighted absolute z-score sum across 5 feature dimensions
- Percentile-mapped to [0, 100] scale
- Interpretation bands: Normal, Elevated, Unusual, Extreme

✅ **Full Explainability**
- Regime triggering conditions with threshold checks
- Top 2-3 contributing features ranked by impact
- Excluded features with reasons (n < 21, NaN, etc.)
- Baseline state transparency (EMPTY/PARTIAL/COMPLETE)

✅ **NaN Philosophy**
> "False negatives are acceptable. False confidence is not."

Missing data → NaN. Never interpolated, imputed, or approximated.

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/Maeshowe/aetherveil.git
cd aetherveil

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Run diagnostic for SPY
python -m obsidian.cli diagnose SPY

# Specify date
python -m obsidian.cli diagnose SPY --date 2024-01-15

# JSON output
python -m obsidian.cli diagnose SPY --format json

# Show version
python -m obsidian.cli version
```

### Python API

```python
from obsidian.engine import (
    Baseline,
    Classifier,
    Explainer,
    Scorer,
)

# 1. Compute z-scores from features
baseline = Baseline(window=63, min_periods=21)
z_scores = baseline.compute_z_scores(feature_series)

# 2. Score unusualness
scorer = Scorer()
scoring_result = scorer.compute_score(z_scores_dict)

# 3. Classify regime
classifier = Classifier()
regime_result = classifier.classify(
    z_scores=z_scores_dict,
    raw_features=raw_features_dict,
    baseline_medians=medians_dict,
    daily_return=return_value,
)

# 4. Generate explanation
explainer = Explainer()
output = explainer.explain(
    regime_result=regime_result,
    scoring_result=scoring_result,
    excluded_features=[],
    baseline_state=baseline_state,
    ticker="SPY",
    date="2024-01-15",
)

# Print human-readable output
print(output.format_full())
```

---

## Architecture

```
                     ┌─────────────────────────────┐
                     │     Pass 1: Focus Update     │
                     │  ETF Holdings (Structural)   │
                     │  Earnings Calendar (Event)   │
                     │  FRED CPI/NFP (Macro)        │
                     │  FOMC Dates (Config)          │
                     └──────────────┬──────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │   CORE + FOCUS Tickers       │
                     └──────────────┬──────────────┘
                                    ▼
Sources (APIs) ──► Raw Cache (Parquet, immutable)
                                    │
                                    ▼
                     Feature Extraction (per-instrument)
                                    │
                                    ▼
                     Baseline (63d rolling z-scores)
                                    │
                                    ▼
                     Scoring + Classification
                                    │
                                    ▼
                     Explainability (top drivers)
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │    Pass 2: Stress Check      │
                     │  Promote stressed tickers    │
                     │  Expire inactive (3d)        │
                     │  Enforce 30-ticker cap       │
                     └──────────────┬──────────────┘
                                    ▼
                     Output (CLI / Dashboard)
```

### Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Orchestrator** | Pipeline coordinator | [src/obsidian/pipeline/orchestrator.py](src/obsidian/pipeline/orchestrator.py) |
| **Fetcher** | API → Parquet cache | [src/obsidian/pipeline/fetcher.py](src/obsidian/pipeline/fetcher.py) |
| **Processor** | Cache → Features → Engine | [src/obsidian/pipeline/processor.py](src/obsidian/pipeline/processor.py) |
| **Baseline** | Rolling statistics, z-score normalization | [src/obsidian/engine/baseline.py](src/obsidian/engine/baseline.py) |
| **Scorer** | Weighted absolute z-sum → percentile | [src/obsidian/engine/scoring.py](src/obsidian/engine/scoring.py) |
| **Classifier** | Priority-ordered regime rules | [src/obsidian/engine/classifier.py](src/obsidian/engine/classifier.py) |
| **Explainer** | Human-readable output generation | [src/obsidian/engine/explainability.py](src/obsidian/engine/explainability.py) |
| **Universe** | CORE + FOCUS ticker management | [src/obsidian/universe/manager.py](src/obsidian/universe/manager.py) |
| **Structural** | ETF top-N holdings → FOCUS | [src/obsidian/universe/structural.py](src/obsidian/universe/structural.py) |
| **Events** | Earnings, macro, FOMC events | [src/obsidian/universe/events.py](src/obsidian/universe/events.py) |
| **Dashboard** | Streamlit UI (4 pages) | [src/obsidian/dashboard/app.py](src/obsidian/dashboard/app.py) |
| **CLI** | Command-line interface | [src/obsidian/cli.py](src/obsidian/cli.py) |

---

## Example Output

```
=== OBSIDIAN MM Diagnostic: SPY @ 2024-01-15 ===

Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
Z_GEX = -2.3100 (threshold: -1.5000) ✓
Impact_vs_median = 0.0087 (threshold: 0.0052) ✓

Unusualness: 78 (Unusual)
Top drivers: GEX contrib=0.58; DARK_SHARE contrib=0.46

Excluded: charm (n = 9 < 21)
Baseline: PARTIAL
```

**Interpretation:** Dealers are significantly short gamma (Z_GEX = -2.31), amplifying directional moves. Price impact is elevated above the 63-day median, signaling a liquidity vacuum. The unusualness score of 78 places this in the "Unusual" band (60-80th percentile).

---

## Documentation

- **[OBSIDIAN_MM_SPEC.md](reference/OBSIDIAN_MM_SPEC.md)** — Complete quantitative specification (503 lines)
- **[USER_GUIDE.md](docs/USER_GUIDE.md)** — End-user guide for interpreting diagnostics
- **[API.md](docs/API.md)** — Developer API reference
- **[IDEA.md](Idea/IDEA.md)** — Product vision and build order
- **[CHANGELOG.md](CHANGELOG.md)** — Version history

---

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_engine/test_classifier.py

# Run with coverage
pytest tests/ --cov=obsidian --cov-report=html

# Test counts
# - Engine (baseline, scoring, classifier, explainer): 125 tests
# - Features (dark pool, greeks, price, venue, volatility): 77 tests
# - Pipeline (orchestrator, fetcher, processor): 56 tests
# - Universe (manager, structural, events): 86 tests
# - CLI: 31 tests
# - Cache: 29 tests
# - Clients (base, UW, Polygon, FMP, FRED): 58 tests
# - Dashboard (data layer): 5 tests
# - Config: 7 tests
# - Memory store: 18 tests
# Total: 504 tests
```

---

## Project Structure

```
obsidian-mm/
├── src/
│   └── obsidian/
│       ├── engine/          # Core diagnostic engine
│       │   ├── baseline.py
│       │   ├── scoring.py
│       │   ├── classifier.py
│       │   └── explainability.py
│       ├── features/        # Feature extraction (5 modules)
│       ├── pipeline/        # Data pipeline
│       │   ├── orchestrator.py  # Main coordinator
│       │   ├── fetcher.py       # API → Cache
│       │   └── processor.py     # Cache → Features → Engine
│       ├── universe/        # Ticker universe (CORE + FOCUS)
│       │   ├── manager.py       # State machine
│       │   ├── structural.py    # ETF top-N holdings
│       │   └── events.py        # Earnings, macro, FOMC
│       ├── dashboard/       # Streamlit UI (4 pages)
│       ├── cache/           # Parquet storage
│       ├── clients/         # API clients (UW, Polygon, FMP, FRED)
│       ├── config.py        # Settings
│       └── cli.py           # CLI interface
├── tests/                   # 504 tests
├── reference/               # Specifications
├── memory/                  # Persistent memory system
└── docs/                    # User and API documentation
```

---

## Design Principles

### 1. NaN Philosophy
**"False negatives are acceptable. False confidence is not."**

- Missing data → NaN, never imputed
- NaN feature → excluded from scoring and classification
- Explainability always lists excluded features

### 2. Instrument Isolation
- Every instrument has its own baseline (B_i ≠ B_j)
- Never pool, average, or borrow statistics across instruments
- Prevents cross-contamination

### 3. Fixed Weights
- Feature weights are **conceptual allocations**, not optimized
- Weights are NOT renormalized when features are excluded
- Transparent, reproducible across time

### 4. No Predictions
- O(t) ⇏ E[ΔP(t+1)] — outputs are diagnostic, never predictive
- No price forecasts, trade signals, or directional probability
- Designed for understanding, not trading

---

## Requirements

- **Python**: 3.12+
- **API Keys** (via `.env`):
  - Unusual Whales API key (required)
  - Polygon API key (required)
  - FMP API key (required)
  - FRED API key (optional — enables CPI/NFP macro event detection)
- **Dependencies**:
  - `httpx>=0.27.0` — Async HTTP for API calls
  - `pandas>=2.2.0` — DataFrame operations
  - `pydantic>=2.6.0` — Config validation
  - `pyarrow>=15.0.0` — Parquet I/O
  - `streamlit>=1.31.0` — Dashboard
  - `plotly>=5.18.0` — Charts
  - `numpy>=1.26.0` — Numerical operations

---

## Development Status

### ✅ Completed (v0.2.0)
- [x] Config & secrets management
- [x] API client layer (async, rate-limited)
- [x] Parquet raw cache
- [x] Feature extraction (5 modules, 11 features)
- [x] Baseline system (rolling stats, z-scores)
- [x] Scoring system (weighted |Z| sum → percentile)
- [x] Regime classifier (7 priority-ordered rules)
- [x] Explainability engine
- [x] CLI interface (wired to full pipeline)
- [x] Streamlit dashboard (4 interactive pages)
- [x] Multi-ticker support (CORE + FOCUS universe)
- [x] Concurrent data fetching and processing
- [x] Edge case hardening (retry, corrupted cache, NaN guards)
- [x] **Focus Universe** — Two-pass pipeline with structural, event, and stress-based FOCUS
  - FRED client for macro event detection (CPI, NFP)
  - FMP ETF holdings for structural focus (SPY/QQQ/DIA top-N)
  - Earnings calendar + FOMC date integration
  - Stress-based promotion (U≥70, |Z_GEX|≥2.0, DarkShare≥0.65, |Z_block|≥2.0)
  - 30-ticker FOCUS cap with priority-based eviction
  - Dashboard Focus Decomposition panel
- [x] **Dashboard polish** — ETF-aware Focus Decomposition, FOCUS Regime Snapshot, Z-Score Cross-Reference
- [x] IV Rank integration (replaced IV Skew), UW concurrency semaphore, OTC earnings filter
- [x] Comprehensive test suite (504 tests)

### 📋 Planned
- [ ] Regime Transition Matrix (RTM)
- [ ] Baseline drift detection alerts
- [ ] Export to CSV/JSON
- [ ] Documentation site

---

## Contributing

This is a private project. For issues or questions, contact the development team.

---

## License

Proprietary. All rights reserved.

---

## Acknowledgments

Inspired by market microstructure research and the need for transparent, explainable diagnostics in quantitative analysis.

**Built with:**
- Python 3.12
- pandas for data processing
- pydantic for config management
- pytest for testing
- Claude Code for development assistance

---

## Contact

For questions, support, or collaboration:
- **Email**: [your-email@example.com]
- **GitHub**: [https://github.com/Maeshowe/aetherveil]
- **Documentation**: [reference/OBSIDIAN_MM_SPEC.md](reference/OBSIDIAN_MM_SPEC.md)

---

*OBSIDIAN MM — Transparency in microstructure diagnostics*
