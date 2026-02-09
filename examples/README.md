# OBSIDIAN MM Examples

This directory contains practical examples demonstrating how to use OBSIDIAN MM.

---

## Available Examples

### 1. Basic Diagnostic ([01_basic_diagnostic.py](01_basic_diagnostic.py))

**Purpose**: Show the most basic usage pattern for running a single diagnostic.

**What it demonstrates**:
- Generating/loading feature data
- Computing z-scores with Baseline
- Scoring with Scorer
- Classifying with Classifier
- Generating explanations with Explainer
- Both text and JSON output formats

**Run it**:
```bash
cd examples
python 01_basic_diagnostic.py
```

**Expected output**: Complete diagnostic with regime classification, unusualness score, and explanation.

---

### 2. Batch Processing ([02_batch_processing.py](02_batch_processing.py))

**Purpose**: Process multiple days of data and analyze historical patterns.

**What it demonstrates**:
- Time series processing
- Computing percentile scores from historical data
- Tracking regime changes over time
- Regime distribution analysis
- Identifying extreme days
- Exporting results to CSV

**Run it**:
```bash
cd examples
python 02_batch_processing.py
```

**Expected output**:
- Regime distribution statistics
- Recent regime transitions
- Extreme unusualness days
- Exported CSV file with all results

---

### 3. Custom Analysis ([03_custom_analysis.py](03_custom_analysis.py))

**Purpose**: Advanced usage patterns and detailed analysis.

**What it demonstrates**:
- Detailed regime rule evaluation (why specific regime was assigned)
- Feature importance breakdown
- Baseline drift detection
- Historical regime persistence analysis
- Custom analytical functions

**Run it**:
```bash
cd examples
python 03_custom_analysis.py
```

**Expected output**:
- Which regime rules matched/didn't match
- Feature contribution breakdown
- Drift detection results
- Regime persistence statistics

---

## Running the Examples

### Prerequisites

```bash
# Install OBSIDIAN MM
pip install -e .

# Navigate to examples directory
cd examples
```

### Run Individual Examples

```bash
# Basic diagnostic
python 01_basic_diagnostic.py

# Batch processing
python 02_batch_processing.py

# Custom analysis
python 03_custom_analysis.py
```

### Run All Examples

```bash
# Bash/Linux/macOS
for f in 0*.py; do python "$f"; done

# Or individually
python 01_basic_diagnostic.py && python 02_batch_processing.py && python 03_custom_analysis.py
```

---

## Example Data

All examples use **synthetic data** for demonstration purposes. In production, you would:

1. **Fetch real data** from APIs (Unusual Whales, Polygon, FMP)
2. **Extract features** using feature modules
3. **Cache data** in Parquet format
4. **Run diagnostics** on real market data

---

## Modifying Examples

### Using Real Data

Replace the `generate_synthetic_feature_data()` function with real data loading:

```python
def load_real_feature_data(ticker: str, start_date: str, end_date: str) -> dict[str, pd.Series]:
    """Load real feature data from cache or APIs."""
    from obsidian.cache import ParquetStore
    from obsidian.features import compute_dark_share, compute_gex, ...

    # Load raw data from cache
    store = ParquetStore()
    raw_data = store.read(ticker, start_date, end_date)

    # Extract features
    features = {
        'dark_share': compute_dark_share(raw_data),
        'gex': compute_gex(raw_data),
        # ... other features
    }

    return features
```

### Customizing Analysis

Examples are designed to be **starting points**. Feel free to:
- Modify thresholds (not recommended for regime rules)
- Add custom visualization
- Export to different formats
- Integrate with your own systems

---

## Common Patterns

### Pattern 1: Single-Day Diagnostic

```python
from obsidian.engine import Baseline, Scorer, Classifier, Explainer

# 1. Compute z-scores
baseline = Baseline()
z_scores = {...}  # From your feature data

# 2. Score
scorer = Scorer()
raw_score, contributions = scorer.compute_raw_score(z_scores)

# 3. Classify
classifier = Classifier()
regime = classifier.classify(...)

# 4. Explain
explainer = Explainer()
output = explainer.explain(...)
print(output.format_full())
```

### Pattern 2: Historical Analysis

```python
# Compute z-scores for entire series
z_scores_ts = {name: baseline.compute_z_scores(series) for name, series in features.items()}

# Process each day
for date in dates:
    z_scores_day = {name: series.loc[date] for name, series in z_scores_ts.items()}
    # ... classify, score, etc.
```

### Pattern 3: Export Results

```python
import pandas as pd

results = []
for date, regime, score in zip(dates, regimes, scores):
    results.append({
        'date': date,
        'regime': regime.value,
        'score': score,
    })

df = pd.DataFrame(results)
df.to_csv('results.csv', index=False)
```

---

## Troubleshooting

### Issue: All NaN z-scores

**Cause**: Not enough historical data (cold start period).

**Solution**: Ensure at least 21 trading days of data before computing z-scores.

```python
if len(feature_data['gex']) < 21:
    print("Insufficient data for z-score computation")
```

### Issue: UND (Undetermined) regime

**Cause**: Baseline insufficient or all features excluded.

**Solution**: Check feature counts and NaN values:

```python
feature_counts = {name: series.notna().sum() for name, series in features.items()}
print(feature_counts)  # Should be >= 21 for valid features
```

### Issue: Import errors

**Cause**: Package not installed or incorrect path.

**Solution**:
```bash
# Make sure you're in the project root
cd /path/to/obsidian-mm

# Install in editable mode
pip install -e .
```

---

## Next Steps

After running these examples:

1. **Integrate with real data**: Replace synthetic data with API calls
2. **Build dashboards**: Use Streamlit to visualize results
3. **Automate workflows**: Schedule daily diagnostics
4. **Extend analysis**: Add custom metrics and visualizations

---

## Resources

- **User Guide**: [../docs/USER_GUIDE.md](../docs/USER_GUIDE.md)
- **API Reference**: [../docs/API.md](../docs/API.md)
- **Specification**: [../reference/OBSIDIAN_MM_SPEC.md](../reference/OBSIDIAN_MM_SPEC.md)

---

## Support

Questions about the examples?
- **GitHub Issues**: [Report a problem](https://github.com/aetherveil/obsidian-mm/issues)
- **Documentation**: See links above

---

*Happy analyzing! 📊*
