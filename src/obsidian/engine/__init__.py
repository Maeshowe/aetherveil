"""Core diagnostic engine for OBSIDIAN MM.

Modules:
    - baseline: Rolling statistics, z-score normalization, state tracking
    - scoring: Weighted |Z| sum → percentile rank
    - classifier: Priority-ordered regime rules
    - explainability: Top drivers + excluded features
"""

from obsidian.engine.baseline import (
    Baseline,
    BaselineState,
    BaselineStats,
)
from obsidian.engine.scoring import (
    Scorer,
    ScoringResult,
    InterpretationBand,
    FEATURE_WEIGHTS,
)
from obsidian.engine.classifier import (
    Classifier,
    RegimeType,
    RegimeResult,
)
from obsidian.engine.explainability import (
    Explainer,
    DiagnosticOutput,
    ExcludedFeature,
)

__all__ = [
    "Baseline",
    "BaselineState",
    "BaselineStats",
    "Scorer",
    "ScoringResult",
    "InterpretationBand",
    "FEATURE_WEIGHTS",
    "Classifier",
    "RegimeType",
    "RegimeResult",
    "Explainer",
    "DiagnosticOutput",
    "ExcludedFeature",
]
