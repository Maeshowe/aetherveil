# Installation

Complete installation guide for OBSIDIAN MM.

---

## Prerequisites

- **Python**: 3.12 or higher
- **Git**: For cloning the repository
- **Virtual environment**: Recommended for isolation

### Check Python Version

```bash
python --version
# Should show: Python 3.12.x or higher
```

If you don't have Python 3.12+:

=== "macOS (Homebrew)"

    ```bash
    brew install python@3.12
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt update
    sudo apt install python3.12 python3.12-venv
    ```

=== "Windows"

    Download from [python.org](https://www.python.org/downloads/)

---

## Installation Methods

### Method 1: Development Install (Recommended)

For development or if you want to modify the code:

```bash
# 1. Clone repository
git clone https://github.com/aetherveil/obsidian-mm.git
cd obsidian-mm

# 2. Create virtual environment
python3.12 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# 4. Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Method 2: User Install

For end-user installation (when package is published):

```bash
pip install obsidian-mm
```

**Note**: Package not yet published to PyPI. Use Method 1 for now.

---

## Verify Installation

```bash
# Check CLI
python -m obsidian.cli version

# Expected output:
# OBSIDIAN MM v0.1.0
# Market-Maker Regime Engine
```

```bash
# Run tests
pytest tests/

# Expected: 313 tests passing
```

```python
# Check Python API
python -c "from obsidian.engine import Baseline; print('✓ Import successful')"
```

```bash
# Launch dashboard (optional)
streamlit run src/obsidian/dashboard/app.py

# Expected: Browser opens at http://localhost:8501
# Shows interactive 4-page dashboard with placeholder data
```

---

## Dependencies

OBSIDIAN MM requires the following packages:

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | ≥0.27.0 | Async HTTP for API calls |
| pandas | ≥2.2.0 | DataFrame operations |
| pydantic | ≥2.6.0 | Config validation |
| pydantic-settings | ≥2.1.0 | Settings management |
| pyarrow | ≥15.0.0 | Parquet I/O |
| streamlit | ≥1.31.0 | Dashboard (future) |
| plotly | ≥5.18.0 | Charts (future) |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ≥8.0.0 | Testing framework |
| pytest-asyncio | ≥0.23.0 | Async testing |
| pytest-mock | ≥3.12.0 | Mocking utilities |
| python-dotenv | ≥1.0.0 | Environment variables |

All dependencies are automatically installed when you run `pip install -e .`

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# .env
UNUSUAL_WHALES_API_KEY=your_key_here
POLYGON_API_KEY=your_key_here
FMP_API_KEY=your_key_here
```

**Note**: API integration is planned for future releases.

### Settings

OBSIDIAN MM uses Pydantic for configuration:

```python
from obsidian.config import Settings

settings = Settings()
print(settings.unusual_whales_api_key)
```

---

## Project Structure

After installation, your directory should look like:

```
obsidian-mm/
├── .venv/              # Virtual environment
├── src/
│   └── obsidian/
│       ├── engine/     # Core diagnostic engine
│       ├── features/   # Feature extraction
│       ├── cache/      # Parquet storage
│       ├── clients/    # API clients
│       └── cli.py      # CLI interface
├── tests/              # Test suite (313 tests)
├── docs/               # Documentation
├── examples/           # Usage examples
└── reference/          # Specifications
```

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'obsidian'`

**Cause**: Package not installed or wrong virtual environment active.

**Solution**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Reinstall
pip install -e .
```

### Issue: `Python version 3.12 required`

**Cause**: Older Python version installed.

**Solution**: Install Python 3.12+ using instructions above.

### Issue: `ImportError: cannot import name 'Baseline'`

**Cause**: Incomplete installation or source code changes.

**Solution**:
```bash
pip install --force-reinstall -e .
```

### Issue: Tests failing

**Cause**: Missing dev dependencies.

**Solution**:
```bash
pip install -e ".[dev]"
pytest tests/
```

---

## Uninstallation

```bash
# If installed in editable mode
pip uninstall obsidian-mm

# Remove virtual environment
deactivate
rm -rf .venv

# Remove cloned repository (if desired)
cd ..
rm -rf obsidian-mm
```

---

## Docker (Future)

Docker support is planned for future releases:

```bash
# Build image
docker build -t obsidian-mm .

# Run container
docker run -it obsidian-mm diagnose SPY
```

---

## Next Steps

- **[Quick Start](quickstart.md)** — Run your first diagnostic
- **[User Guide](user-guide/index.md)** — Learn how to use OBSIDIAN MM
- **[API Reference](api/index.md)** — Explore the Python API

---

## Support

Having installation issues?

- **Check**: [Troubleshooting](#troubleshooting) section above
- **Search**: [GitHub Issues](https://github.com/aetherveil/obsidian-mm/issues)
- **Report**: [Open a new issue](https://github.com/aetherveil/obsidian-mm/issues/new)
