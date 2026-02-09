# Quick Start

Get up and running with OBSIDIAN MM in 5 minutes.

---

## Installation

```bash
# Clone repository
git clone https://github.com/aetherveil/obsidian-mm.git
cd obsidian-mm

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install package
pip install -e .
```

---

## Verify Installation

```bash
python -m obsidian.cli version
```

You should see:
```
OBSIDIAN MM v0.1.0
Market-Maker Regime Engine
```

---

## Run Your First Diagnostic

```bash
python -m obsidian.cli diagnose SPY
```

**Note**: This will show a message that the data pipeline is not yet implemented. The CLI structure is complete and ready for integration with API clients.

---

## Python API

Create a file `test_diagnostic.py`:

```python
from obsidian.engine import (
    Baseline,
    Scorer,
    Classifier,
    Explainer,
)

# Initialize components
baseline = Baseline(window=63, min_periods=21)
scorer = Scorer()
classifier = Classifier()
explainer = Explainer()

print("✓ OBSIDIAN MM components loaded successfully")
print(f"  Baseline window: {baseline.window} days")
print(f"  Scorer window: {scorer.window} days")
print(f"  Classifier: {len([r for r in classifier.__class__.__dict__ if 'THRESHOLD' in r])} thresholds")
```

Run it:
```bash
python test_diagnostic.py
```

---

## Dashboard

Launch the interactive Streamlit dashboard:

```bash
streamlit run src/obsidian/dashboard/app.py
```

This will open a browser window at `http://localhost:8501` with:

- **📊 Daily State**: Current regime and unusualness score
- **📈 Historical Regimes**: Regime timeline and transitions
- **🎯 Drivers & Contributors**: Feature breakdown analysis
- **✅ Baseline Status**: Data quality indicators

**Note**: The dashboard currently shows placeholder data. Once the data pipeline is connected, it will display real diagnostics.

---

## Next Steps

- **[User Guide](user-guide/index.md)** — Learn how to interpret diagnostics
- **[API Reference](api/index.md)** — Dive into the Python API
- **[Examples](examples/index.md)** — See practical usage patterns

---

## Need Help?

- **Documentation**: Browse the guides in the sidebar
- **Examples**: Check out [examples/](../examples/)
- **Issues**: [Report a problem](https://github.com/aetherveil/obsidian-mm/issues)
