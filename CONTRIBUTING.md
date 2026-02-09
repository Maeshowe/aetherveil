# Contributing to OBSIDIAN MM

Thank you for your interest in contributing to OBSIDIAN MM! This guide will help you understand our development workflow and standards.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Development Workflow](#development-workflow)
5. [Code Standards](#code-standards)
6. [Testing Requirements](#testing-requirements)
7. [Documentation Standards](#documentation-standards)
8. [Commit Messages](#commit-messages)
9. [Pull Request Process](#pull-request-process)
10. [Design Principles](#design-principles)

---

## Code of Conduct

### Our Standards

- **Respectful**: Treat everyone with respect and professionalism
- **Constructive**: Provide helpful feedback and suggestions
- **Collaborative**: Work together to improve the project
- **Transparent**: Communicate openly about changes and decisions

### Unacceptable Behavior

- Harassment or discriminatory language
- Trolling or intentionally disruptive behavior
- Publishing private information without permission
- Unprofessional conduct

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- Git
- Basic understanding of market microstructure (for feature development)
- Familiarity with pytest for testing

### First Contribution

Good first issues are tagged with `good-first-issue` in the issue tracker. These are ideal for:
- Bug fixes
- Documentation improvements
- Test coverage expansion
- Code quality improvements

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/obsidian-mm.git
cd obsidian-mm
```

### 2. Create Virtual Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 4. Verify Installation

```bash
# Run tests
pytest tests/

# Check CLI
python -m obsidian.cli version
```

### 5. Set Up Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install
```

---

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
# or
git checkout -b docs/your-documentation-update
```

**Branch naming conventions**:
- `feature/`: New features
- `fix/`: Bug fixes
- `docs/`: Documentation updates
- `test/`: Test improvements
- `refactor/`: Code refactoring

### 2. Make Changes

- Write code following our [Code Standards](#code-standards)
- Add tests for new functionality
- Update documentation as needed
- Run tests frequently: `pytest tests/`

### 3. Commit Changes

```bash
git add .
git commit -m "feat: add new feature description"
```

See [Commit Messages](#commit-messages) for formatting guidelines.

### 4. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 5. Create Pull Request

- Go to the original repository on GitHub
- Click "New Pull Request"
- Select your branch
- Fill out the PR template
- Request review

---

## Code Standards

### Python Style

We follow **PEP 8** with some modifications:

```python
# Good
def compute_z_score(value: float, mean: float, std: float) -> float:
    """Compute z-score for a value.

    Args:
        value: The value to normalize
        mean: Rolling mean
        std: Rolling standard deviation

    Returns:
        Z-score (float). NaN if std is zero.
    """
    if std == 0:
        return float('nan')
    return (value - mean) / std


# Bad
def compute_z_score(v,m,s):  # No type hints, unclear names
    return (v-m)/s  # No NaN handling
```

### Type Hints

**Required** for all function signatures:

```python
# Good
def compute_statistics(
    self,
    data: pd.Series,
    use_expanding: bool = True,
) -> pd.Series:
    pass


# Bad
def compute_statistics(self, data, use_expanding=True):  # No types
    pass
```

### Docstrings

Use **Google-style docstrings**:

```python
def classify(
    self,
    z_scores: dict[str, float],
    raw_features: dict[str, float],
    baseline_medians: dict[str, float],
    daily_return: float,
    baseline_sufficient: bool = True,
) -> RegimeResult:
    """Classify regime using priority-ordered rules.

    Rules are evaluated in strict priority order (1-7). First match wins.
    If baseline is insufficient, returns UND immediately.

    Args:
        z_scores: Z-scores for each feature (e.g., {"gex": 2.14})
        raw_features: Raw feature values (e.g., {"dark_share": 0.75})
        baseline_medians: Median values from baseline
        daily_return: Close-to-close return (ΔP_t / Close_{t-1})
        baseline_sufficient: Whether baseline state is COMPLETE or PARTIAL

    Returns:
        RegimeResult with assigned regime and triggering conditions

    Example:
        >>> classifier = Classifier()
        >>> result = classifier.classify(
        ...     z_scores={'gex': -2.31},
        ...     raw_features={'impact': 0.0087},
        ...     baseline_medians={'impact': 0.0052},
        ...     daily_return=-0.015,
        ... )
        >>> result.regime
        RegimeType.GAMMA_NEGATIVE
    """
    pass
```

### Imports

Organize imports in this order:

```python
# 1. Standard library
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# 2. Third-party
import numpy as np
import pandas as pd
from pydantic import BaseModel

# 3. Local
from obsidian.engine import Baseline, Scorer
```

### NaN Handling

**Critical**: OBSIDIAN MM's NaN philosophy is sacred.

```python
# Good - Explicit NaN handling
if np.isnan(value):
    return None  # Or appropriate NaN handling

# Good - Propagate NaN
result = value / divisor  # Will be NaN if either is NaN


# Bad - Implicit zero/default
value = value or 0.0  # NO! NaN should stay NaN

# Bad - Imputation
value = value if not np.isnan(value) else mean  # NO! Never impute
```

---

## Testing Requirements

### Test Coverage

**All new code must have tests**. Aim for:
- **Baseline coverage**: 80%
- **Critical paths**: 100%

### Test Structure

```python
"""Tests for Classifier.

Test Coverage:
    - Priority-ordered rule evaluation
    - Each regime's triggering conditions
    - NaN handling
    - Edge cases
"""

import pytest
from obsidian.engine import Classifier, RegimeType


class TestClassifier:
    """Test Classifier initialization."""

    def test_initialization(self):
        """Classifier initializes with fixed thresholds."""
        classifier = Classifier()
        assert classifier.Z_GEX_THRESHOLD == 1.5


class TestGammaPositiveRegime:
    """Test Γ⁺ regime classification."""

    def test_basic_classification(self):
        """Γ⁺ triggers when Z_GEX > 1.5 and Efficiency < median."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={'gex': 2.0},
            raw_features={'efficiency': 0.003},
            baseline_medians={'efficiency': 0.004},
            daily_return=0.01,
        )
        assert result.regime == RegimeType.GAMMA_POSITIVE

    def test_edge_case_at_threshold(self):
        """Γ⁺ does NOT trigger at exactly Z_GEX = 1.5."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={'gex': 1.5},  # Exactly at threshold
            raw_features={'efficiency': 0.003},
            baseline_medians={'efficiency': 0.004},
            daily_return=0.0,
        )
        assert result.regime != RegimeType.GAMMA_POSITIVE
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific module
pytest tests/test_engine/test_classifier.py

# Run specific test
pytest tests/test_engine/test_classifier.py::TestClassifier::test_initialization

# Run with coverage
pytest tests/ --cov=obsidian --cov-report=html

# Run with verbose output
pytest tests/ -v

# Run only failed tests
pytest tests/ --lf
```

### Test Requirements for PRs

- ✅ All tests pass
- ✅ New code has tests
- ✅ Edge cases covered
- ✅ NaN handling tested
- ✅ No test skips without justification

---

## Documentation Standards

### Inline Documentation

- **Docstrings**: Required for all public functions/classes
- **Type hints**: Required for all function signatures
- **Comments**: Only when logic is non-obvious

### README Updates

Update `README.md` if you:
- Add a new major feature
- Change installation process
- Modify API structure

### Changelog

**Always update `CHANGELOG.md`** under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New feature: Regime transition matrix computation

### Changed
- Updated z-score computation to handle edge case

### Fixed
- Fixed bug in percentile calculation for small windows
```

### Documentation Site

If you add new modules or major features, update:
- `docs/API.md` — Developer reference
- `docs/USER_GUIDE.md` — User documentation
- `mkdocs.yml` — Navigation structure

---

## Commit Messages

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding or updating tests
- `refactor`: Code refactoring (no functional change)
- `perf`: Performance improvement
- `style`: Formatting, missing semicolons, etc.
- `chore`: Maintenance tasks

### Examples

```bash
# Good
feat(classifier): add regime transition matrix computation

Implements empirical transition probability calculation as per
spec Section 8. Includes self-transition (persistence) and
entropy calculations.

Closes #42

# Good
fix(baseline): handle zero std in z-score computation

Previously crashed with division by zero. Now returns NaN
as per the NaN philosophy.

Fixes #38

# Good
docs(api): add examples for Scorer class

Added 3 usage examples showing basic, advanced, and custom
weight scenarios.

# Bad
update stuff  # Too vague, no type

# Bad
fix: fixed the bug  # Not descriptive
```

---

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] `CHANGELOG.md` updated
- [ ] Code follows style guidelines
- [ ] No `TODO` or `FIXME` comments left
- [ ] Commit messages follow format

### PR Template

Fill out the PR template completely:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] All tests pass
- [ ] New tests added
- [ ] Tested manually

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Review Process

1. **Automated checks** run (tests, linting)
2. **Code review** by maintainers
3. **Feedback** addressed in new commits
4. **Approval** from at least one maintainer
5. **Merge** to main branch

### Merge Requirements

- ✅ All CI checks pass
- ✅ At least 1 approval from maintainer
- ✅ No unresolved conversations
- ✅ Branch is up to date with main
- ✅ No merge conflicts

---

## Design Principles

### 1. NaN Philosophy

> "False negatives are acceptable. False confidence is not."

**Never**:
- Impute missing data
- Forward-fill values
- Approximate unavailable features

**Always**:
- Return NaN for missing data
- Exclude NaN features from scoring
- List excluded features in output

### 2. Instrument Isolation

**Never**:
- Pool statistics across instruments
- Average baselines across tickers
- Borrow data from similar instruments

**Always**:
- Compute separate baselines per instrument
- Keep baselines independent (B_i ≠ B_j)

### 3. Fixed Weights

**Never**:
- Optimize feature weights
- Fit weights to historical data
- Renormalize weights when features excluded

**Always**:
- Use fixed conceptual weights
- Keep weights constant across time
- Document weight rationale

### 4. No Predictions

**Never**:
- Generate price forecasts
- Produce buy/sell signals
- Calculate expected returns

**Always**:
- Provide diagnostic information only
- Explain current conditions
- Make limitations clear

### 5. Explainability First

**Never**:
- Output a classification without explanation
- Hide triggering conditions
- Omit excluded features

**Always**:
- Show why a regime was assigned
- List top contributors to scores
- Document what's missing

---

## Project-Specific Guidelines

### Adding a New Feature

**For feature extraction** (e.g., new microstructure metric):

1. Add computation function to appropriate module in `src/obsidian/features/`
2. Add docstring with formula and interpretation
3. Write tests with edge cases (NaN, zero values, etc.)
4. Update `FEATURE_WEIGHTS` if it's a scored feature
5. Document in `docs/API.md`

### Adding a New Regime

**For new regime type**:

1. Add to `RegimeType` enum in `src/obsidian/engine/classifier.py`
2. Implement rule in `Classifier.classify()` in priority order
3. Add description and interpretation methods
4. Write tests for triggering conditions
5. Update `docs/USER_GUIDE.md` with regime explanation

### Modifying the Baseline

**Baseline changes are critical**:

1. Discuss with maintainers first (GitHub issue)
2. Ensure spec compliance
3. Add extensive tests
4. Update all dependent tests
5. Document breaking changes

---

## Getting Help

### Questions?

- **General questions**: Open a GitHub Discussion
- **Bug reports**: Open a GitHub Issue
- **Feature requests**: Open a GitHub Issue with `enhancement` label
- **Security issues**: Email security@aetherveil.com

### Resources

- **Specification**: [OBSIDIAN_MM_SPEC.md](reference/OBSIDIAN_MM_SPEC.md)
- **User Guide**: [USER_GUIDE.md](docs/USER_GUIDE.md)
- **API Reference**: [API.md](docs/API.md)
- **Examples**: [examples/](examples/)

---

## Recognition

Contributors are recognized in:
- `CHANGELOG.md` (per release)
- GitHub contributors list
- Annual acknowledgments

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (Proprietary).

---

Thank you for contributing to OBSIDIAN MM! 🚀

*Questions? Open an issue or start a discussion.*
