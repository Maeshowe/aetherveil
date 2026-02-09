# OBSIDIAN MM API Reference

**Developer documentation for using OBSIDIAN MM programmatically**

This guide covers the Python API for integrating OBSIDIAN MM into your applications.

---

## Table of Contents

1. [Installation](#installation)
2. [Core Components](#core-components)
3. [Baseline System](#baseline-system)
4. [Scoring System](#scoring-system)
5. [Classification System](#classification-system)
6. [Explainability System](#explainability-system)
7. [Complete Pipeline](#complete-pipeline)
8. [Configuration](#configuration)
9. [Error Handling](#error-handling)
10. [Examples](#examples)

---

## Installation

```bash
pip install obsidian-mm
```

Or for development:
```bash
git clone https://github.com/aetherveil/obsidian-mm.git
cd obsidian-mm
pip install -e ".[dev]"
```

---

## Core Components

### Module Structure

```python
from obsidian.engine import (
    # Baseline
    Baseline,
    BaselineState,
    BaselineStats,

    # Scoring
    Scorer,
    ScoringResult,
    InterpretationBand,
    FEATURE_WEIGHTS,

    # Classification
    Classifier,
    RegimeType,
    RegimeResult,

    # Explainability
    Explainer,
    DiagnosticOutput,
    ExcludedFeature,
)
```

---

## Baseline System

The baseline system computes rolling statistics and z-scores for normalization.

### `Baseline`

**Purpose**: Compute rolling mean/std and normalize features to z-scores.

**Constructor**:
```python
Baseline(window: int = 63, min_periods: int = 21, drift_threshold: float = 0.10)
```

**Parameters**:
- `window` (int): Rolling window size in trading days (default: 63)
- `min_periods` (int): Minimum observations required for valid statistics (default: 21)
- `drift_threshold` (float): Relative change threshold for drift detection (default: 0.10)

**Methods**:

#### `compute_statistics(data, use_expanding=True) -> pd.Series`

Compute rolling statistics (mean, std, count) for a feature.

```python
import pandas as pd
from obsidian.engine import Baseline

# Sample feature data
feature_data = pd.Series([0.45, 0.52, 0.48, ...], index=pd.date_range('2024-01-01', periods=100))

baseline = Baseline(window=63, min_periods=21)
stats_series = baseline.compute_statistics(feature_data, use_expanding=True)

# Each element is a BaselineStats object
for date, stats in stats_series.items():
    if stats.is_valid:
        print(f"{date}: mean={stats.mean:.4f}, std={stats.std:.4f}, n={stats.n}")
```

**Returns**: `pd.Series` of `BaselineStats` objects.

---

#### `compute_z_scores(data, use_expanding=True) -> pd.Series`

Normalize feature to z-scores using rolling statistics.

```python
z_scores = baseline.compute_z_scores(feature_data, use_expanding=True)

# z_scores is a Series with NaN where insufficient data
print(z_scores.tail())
```

**Formula**: `Z_X(t) = (X_t - μ_X) / σ_X`

**Returns**: `pd.Series` of z-scores (float). NaN if insufficient data or σ = 0.

---

#### `get_state(feature_counts: dict[str, int]) -> BaselineState`

Determine baseline state based on feature observation counts.

```python
from obsidian.engine import BaselineState

feature_counts = {
    'gex': 25,        # Valid (≥ 21)
    'dark_share': 18, # Invalid (< 21)
    'venue_mix': 30,  # Valid
}

state = baseline.get_state(feature_counts)
print(state)  # BaselineState.PARTIAL
```

**Returns**:
- `BaselineState.EMPTY`: All features n < 21
- `BaselineState.PARTIAL`: Some features valid, some not
- `BaselineState.COMPLETE`: All features n ≥ 21

---

#### `detect_drift(current_mean: float, previous_mean: float) -> bool`

Detect if baseline has drifted beyond threshold.

```python
drift_detected = baseline.detect_drift(
    current_mean=0.0055,
    previous_mean=0.0050,
)
# drift_detected = True if |(0.0055 - 0.0050) / 0.0050| > 0.10
```

**Returns**: `bool` — True if drift detected.

---

### `BaselineStats`

**Dataclass** holding baseline statistics for a single time point.

**Attributes**:
- `mean` (float): Rolling mean
- `std` (float): Rolling standard deviation
- `n` (int): Number of observations
- `is_valid` (bool): Whether statistics are valid (n ≥ min_periods, std > 0)

---

### `BaselineState`

**Enum** representing baseline data sufficiency.

**Values**:
- `EMPTY`: All features below minimum observations
- `PARTIAL`: Some features valid, some not
- `COMPLETE`: All features meet minimum observations

---

## Scoring System

The scoring system computes unusualness scores from z-scores.

### `Scorer`

**Purpose**: Compute weighted absolute z-sum and map to percentile scores.

**Constructor**:
```python
Scorer(window: int = 63, weights: Optional[dict[str, float]] = None)
```

**Parameters**:
- `window` (int): Window for percentile computation (default: 63)
- `weights` (dict): Custom feature weights (default: `FEATURE_WEIGHTS`)

**Methods**:

#### `compute_raw_score(z_scores, excluded_features=None) -> tuple[float, dict[str, float]]`

Compute raw weighted absolute z-score sum.

```python
from obsidian.engine import Scorer

scorer = Scorer()

z_scores = {
    'gex': -2.31,
    'dark_share': 1.84,
    'venue_mix': 0.50,
    'block_intensity': 0.80,
}

raw_score, contributions = scorer.compute_raw_score(
    z_scores=z_scores,
    excluded_features=['iv_skew'],  # Excluded due to missing data
)

print(f"Raw score: {raw_score:.4f}")
print(f"Contributions: {contributions}")
```

**Formula**: `S_t = Σ w_k × |Z_k(t)|` for valid features only.

**Returns**: `tuple[float, dict[str, float]]`
- Raw score (float)
- Feature contributions (dict)

**Important**: Weights are NOT renormalized when features are excluded.

---

#### `compute_percentile_scores(raw_scores, use_expanding=True) -> pd.Series`

Map raw scores to percentile ranks [0, 100].

```python
import pandas as pd

# Historical raw scores
raw_scores = pd.Series([0.85, 0.92, 1.15, ...], index=pd.date_range('2024-01-01', periods=100))

percentile_scores = scorer.compute_percentile_scores(raw_scores, use_expanding=True)

print(percentile_scores.tail())
```

**Returns**: `pd.Series` of percentile scores (float).

---

#### `get_interpretation(percentile_score: float) -> InterpretationBand`

Map percentile score to interpretation band.

```python
from obsidian.engine import InterpretationBand

band = scorer.get_interpretation(78.0)
print(band)  # InterpretationBand.UNUSUAL
print(band.value)  # "Unusual"
```

**Returns**: `InterpretationBand` enum value.

---

### `ScoringResult`

**Dataclass** holding unusualness scoring results.

**Attributes**:
- `raw_score` (float): Weighted absolute z-score sum
- `percentile_score` (float): Percentile rank [0, 100]
- `interpretation` (InterpretationBand): Interpretation band
- `feature_contributions` (dict[str, float]): Contribution per feature
- `excluded_features` (list[str]): Features excluded from scoring

**Example**:
```python
from obsidian.engine import ScoringResult, InterpretationBand

result = ScoringResult(
    raw_score=1.15,
    percentile_score=78.0,
    interpretation=InterpretationBand.UNUSUAL,
    feature_contributions={'gex': 0.5775, 'dark_share': 0.46},
    excluded_features=['charm'],
)
```

---

### `InterpretationBand`

**Enum** for unusualness score interpretation.

**Values**:
- `NORMAL`: 0–30 (within historical norms)
- `ELEVATED`: 30–60 (measurable deviation)
- `UNUSUAL`: 60–80 (significant departure)
- `EXTREME`: 80–100 (rare configuration)

---

### `FEATURE_WEIGHTS`

**Constant** dict of fixed diagnostic weights.

```python
from obsidian.engine import FEATURE_WEIGHTS

print(FEATURE_WEIGHTS)
# {
#     'dark_share': 0.25,
#     'gex': 0.25,
#     'venue_mix': 0.20,
#     'block_intensity': 0.15,
#     'iv_skew': 0.15,
# }
```

**Important**: These are **conceptual allocations**, not optimized or tunable.

---

## Classification System

The classification system assigns regime types using priority-ordered rules.

### `Classifier`

**Purpose**: Classify market microstructure into one of 7 regimes.

**Constructor**:
```python
Classifier()
```

**Methods**:

#### `classify(z_scores, raw_features, baseline_medians, daily_return, baseline_sufficient=True) -> RegimeResult`

Classify regime using priority-ordered rules.

```python
from obsidian.engine import Classifier

classifier = Classifier()

regime_result = classifier.classify(
    z_scores={'gex': -2.31, 'dex': 0.5, 'block_intensity': 0.8},
    raw_features={'dark_share': 0.65, 'efficiency': 0.0032, 'impact': 0.0087},
    baseline_medians={'efficiency': 0.0041, 'impact': 0.0052},
    daily_return=-0.015,
    baseline_sufficient=True,
)

print(regime_result.regime)  # RegimeType.GAMMA_NEGATIVE
print(regime_result.interpretation)
print(regime_result.triggering_conditions)
```

**Parameters**:
- `z_scores` (dict): Feature z-scores
- `raw_features` (dict): Raw feature values
- `baseline_medians` (dict): Median values from baseline
- `daily_return` (float): Close-to-close return (ΔP/P)
- `baseline_sufficient` (bool): Whether baseline is adequate

**Returns**: `RegimeResult` with classification details.

**Rules** (priority order):
1. **Γ⁺**: Z_GEX > +1.5 AND Efficiency < median
2. **Γ⁻**: Z_GEX < −1.5 AND Impact > median
3. **DD**: DarkShare > 0.70 AND Z_block > +1.0
4. **ABS**: Z_DEX < −1.0 AND return ≥ −0.5% AND DarkShare > 0.50
5. **DIST**: Z_DEX > +1.0 AND return ≤ +0.5%
6. **NEU**: No rule matched
7. **UND**: Baseline insufficient

---

### `RegimeResult`

**Dataclass** holding regime classification results.

**Attributes**:
- `regime` (RegimeType): Assigned regime
- `triggering_conditions` (dict): Conditions that triggered the regime
- `interpretation` (str): Human-readable interpretation
- `baseline_sufficient` (bool): Whether baseline was adequate

**Example**:
```python
from obsidian.engine import RegimeType, RegimeResult

result = RegimeResult(
    regime=RegimeType.GAMMA_NEGATIVE,
    triggering_conditions={
        'Z_GEX': (-2.31, -1.5, True),
        'Impact_vs_median': (0.0087, 0.0052, True),
    },
    interpretation="Dealers short gamma, amplifying moves",
    baseline_sufficient=True,
)
```

**Method**:
- `format_conditions() -> str`: Format conditions as human-readable string

---

### `RegimeType`

**Enum** for regime types.

**Values**:
- `GAMMA_POSITIVE`: Γ⁺ (volatility suppression)
- `GAMMA_NEGATIVE`: Γ⁻ (liquidity vacuum)
- `DARK_DOMINANT`: DD (institutional positioning)
- `ABSORPTION`: ABS (sell pressure absorbed)
- `DISTRIBUTION`: DIST (buy pressure distributed)
- `NEUTRAL`: NEU (balanced state)
- `UNDETERMINED`: UND (insufficient data)

**Methods**:
- `get_description() -> str`: Human-readable description
- `get_interpretation() -> str`: Microstructure interpretation

---

## Explainability System

The explainability system generates human-readable diagnostic output.

### `Explainer`

**Purpose**: Combine engine outputs into coherent explanations.

**Constructor**:
```python
Explainer()
```

**Methods**:

#### `explain(...) -> DiagnosticOutput`

Generate complete diagnostic output.

```python
from obsidian.engine import Explainer, ExcludedFeature, BaselineState

explainer = Explainer()

output = explainer.explain(
    regime_result=regime_result,
    scoring_result=scoring_result,
    excluded_features=[
        ExcludedFeature('charm', 'n = 9 < 21'),
    ],
    baseline_state=BaselineState.PARTIAL,
    ticker='SPY',
    date='2024-01-15',
)

# Human-readable text
print(output.format_full())

# Structured data
data = output.to_dict()
```

**Returns**: `DiagnosticOutput` with all diagnostic components.

---

#### `create_exclusion(feature_name, n_obs=None, min_required=21, reason=None) -> ExcludedFeature`

Create standardized exclusion record.

```python
excluded = explainer.create_exclusion('charm', n_obs=14, min_required=21)
# ExcludedFeature(feature_name='charm', reason='n = 14 < 21')

excluded = explainer.create_exclusion('vanna', reason='NaN value')
# ExcludedFeature(feature_name='vanna', reason='NaN value')
```

**Returns**: `ExcludedFeature` with formatted reason.

---

### `DiagnosticOutput`

**Dataclass** holding complete diagnostic output.

**Attributes**:
- `regime_result` (RegimeResult): Regime classification
- `scoring_result` (ScoringResult | None): Unusualness score
- `excluded_features` (list[ExcludedFeature]): Excluded features
- `baseline_state` (BaselineState): Data sufficiency
- `ticker` (str): Instrument symbol
- `date` (str): Diagnosis date

**Methods**:

#### `format_full() -> str`

Format complete diagnostic output.

```python
print(output.format_full())
```

**Example output**:
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

---

#### `format_regime() -> str`

Format regime section only.

---

#### `format_score() -> str`

Format score section only.

---

#### `format_excluded_features() -> str`

Format excluded features section.

---

#### `format_baseline_state() -> str`

Format baseline state section.

---

#### `to_dict() -> dict`

Convert to structured dictionary for JSON serialization.

```python
data = output.to_dict()
import json
print(json.dumps(data, indent=2))
```

---

### `ExcludedFeature`

**Dataclass** for excluded feature records.

**Attributes**:
- `feature_name` (str): Name of excluded feature
- `reason` (str): Why it was excluded

---

## Complete Pipeline

### End-to-End Example

```python
import pandas as pd
from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    Explainer,
    ExcludedFeature,
    BaselineState,
)

# Step 1: Prepare feature data (normally from API/cache)
feature_data = {
    'gex': pd.Series([...]),  # 100 days of GEX values
    'dark_share': pd.Series([...]),
    'dex': pd.Series([...]),
    # ... other features
}

# Step 2: Compute z-scores
baseline = Baseline(window=63, min_periods=21)

z_scores = {}
feature_counts = {}
for feature_name, series in feature_data.items():
    z_series = baseline.compute_z_scores(series, use_expanding=True)
    z_scores[feature_name] = z_series.iloc[-1]  # Latest z-score
    feature_counts[feature_name] = series.notna().sum()

# Step 3: Determine baseline state
baseline_state = baseline.get_state(feature_counts)

# Step 4: Compute unusualness score
scorer = Scorer()
raw_score, contributions = scorer.compute_raw_score(
    z_scores=z_scores,
    excluded_features=[],
)

# Compute percentile (requires historical raw scores)
# For single-day: Use scorer.get_interpretation() directly
percentile_score = 78.0  # Placeholder
interpretation = scorer.get_interpretation(percentile_score)

from obsidian.engine import ScoringResult
scoring_result = ScoringResult(
    raw_score=raw_score,
    percentile_score=percentile_score,
    interpretation=interpretation,
    feature_contributions=contributions,
    excluded_features=[],
)

# Step 5: Classify regime
classifier = Classifier()
regime_result = classifier.classify(
    z_scores=z_scores,
    raw_features={'dark_share': 0.65, 'efficiency': 0.003, 'impact': 0.008},
    baseline_medians={'efficiency': 0.004, 'impact': 0.005},
    daily_return=-0.015,
    baseline_sufficient=(baseline_state != BaselineState.EMPTY),
)

# Step 6: Generate explanation
explainer = Explainer()
output = explainer.explain(
    regime_result=regime_result,
    scoring_result=scoring_result,
    excluded_features=[],
    baseline_state=baseline_state,
    ticker='SPY',
    date='2024-01-15',
)

# Step 7: Output
print(output.format_full())

# Or as JSON
import json
print(json.dumps(output.to_dict(), indent=2))
```

---

## Configuration

### Environment Variables

```bash
# .env file
UNUSUAL_WHALES_API_KEY=your_key_here
POLYGON_API_KEY=your_key_here
FMP_API_KEY=your_key_here
```

### Pydantic Settings

```python
from obsidian.config import Settings

settings = Settings()

print(settings.unusual_whales_api_key)
print(settings.polygon_api_key)
```

---

## Error Handling

### Common Exceptions

**`ValueError`**: Invalid parameters
```python
try:
    baseline = Baseline(window=0)  # Invalid
except ValueError as e:
    print(f"Error: {e}")
```

**`KeyError`**: Missing required features
```python
try:
    scorer.compute_raw_score(z_scores={})  # No features
except KeyError as e:
    print(f"Missing feature: {e}")
```

### NaN Handling

OBSIDIAN MM uses NaN to represent missing or invalid data. Always check for NaN:

```python
import numpy as np

z_score = z_scores.get('gex', np.nan)
if not np.isnan(z_score):
    # Use z_score
    pass
else:
    # Handle missing data
    pass
```

---

## Examples

### Example 1: Simple Diagnostic

```python
from obsidian.engine import Classifier, RegimeType

classifier = Classifier()

result = classifier.classify(
    z_scores={'gex': 2.0},
    raw_features={'efficiency': 0.003},
    baseline_medians={'efficiency': 0.004},
    daily_return=0.01,
)

if result.regime == RegimeType.GAMMA_POSITIVE:
    print("Dealers are long gamma — volatility suppression expected")
```

### Example 2: Batch Processing

```python
import pandas as pd
from obsidian.engine import Baseline, Scorer

baseline = Baseline()
scorer = Scorer()

# Process multiple days
for date in date_range:
    z_scores = baseline.compute_z_scores(feature_data[date])
    raw_score, _ = scorer.compute_raw_score(z_scores)
    print(f"{date}: {raw_score:.4f}")
```

### Example 3: Custom Weights

```python
from obsidian.engine import Scorer

# Custom weights (not recommended)
custom_weights = {
    'gex': 0.30,
    'dark_share': 0.30,
    'venue_mix': 0.20,
    'block_intensity': 0.10,
    'iv_skew': 0.10,
}

scorer = Scorer(weights=custom_weights)
```

---

## API Stability

**Current Version**: 0.1.0 (Alpha)

**Stability Guarantees**:
- ✅ `Baseline`, `Scorer`, `Classifier`, `Explainer`: Stable
- ✅ `RegimeType`, `InterpretationBand`, `BaselineState`: Stable
- ⚠️ Internal methods and private APIs may change

**Deprecation Policy**: Breaking changes will be announced one minor version in advance.

---

## Support

For API questions:
- **Documentation**: [OBSIDIAN_MM_SPEC.md](../reference/OBSIDIAN_MM_SPEC.md)
- **Examples**: [examples/](../examples/)
- **GitHub Issues**: [Report a bug](https://github.com/aetherveil/obsidian-mm/issues)

---

*OBSIDIAN MM — Programmatic microstructure diagnostics*
