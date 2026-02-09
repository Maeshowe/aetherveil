"""Explainability Protocol for OBSIDIAN MM.

Produces human-readable diagnostic output that explains:
1. The assigned regime and triggering conditions
2. The unusualness score and its top drivers
3. Excluded features with reasons
4. Baseline state (data sufficiency)

Design Principles:
    - Transparency: Every decision must be explainable
    - No silent failures: If data is missing, explicitly state it
    - Human-readable: Output designed for consumption by traders/quants
    - Traceable: All values traceable back to raw inputs

Per spec Section 7: "Every output tuple (U_t, R_t) must be accompanied by:
    1. The assigned regime label and its triggering condition values
    2. The top 2–3 features contributing to U_t
    3. A list of any excluded features with reason
    4. The baseline state"
"""

from dataclasses import dataclass
from typing import Optional

from obsidian.engine.baseline import BaselineState
from obsidian.engine.classifier import RegimeResult
from obsidian.engine.scoring import ScoringResult


@dataclass
class ExcludedFeature:
    """Record of a feature excluded from analysis.

    Attributes:
        feature_name: Name of the excluded feature
        reason: Why it was excluded (e.g., "n = 14 < 21", "NaN value", "API unavailable")
    """

    feature_name: str
    reason: str

    def __str__(self) -> str:
        """Format as 'FeatureName (reason)'."""
        return f"{self.feature_name} ({self.reason})"


@dataclass
class DiagnosticOutput:
    """Complete diagnostic output for a single day.

    Contains all information required by the explainability protocol:
    - Regime classification with triggering conditions
    - Unusualness score with top drivers
    - Excluded features with reasons
    - Baseline state

    This is the canonical output format for OBSIDIAN MM diagnostics.

    Attributes:
        regime_result: Regime classification with triggering conditions
        scoring_result: Unusualness score with contributions
        excluded_features: List of features excluded from analysis
        baseline_state: Data sufficiency state (EMPTY/PARTIAL/COMPLETE)
        ticker: Instrument ticker symbol
        date: Date of diagnosis (ISO format string)
    """

    regime_result: RegimeResult
    scoring_result: Optional[ScoringResult]
    excluded_features: list[ExcludedFeature]
    baseline_state: BaselineState
    ticker: str
    date: str

    def format_regime(self) -> str:
        """Format regime classification section.

        Returns:
            Multi-line string with regime label, description, and triggering conditions.
            Example:
                Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
                Z_GEX = -2.3100 (threshold: -1.5000) ✓
                Impact_vs_median = 0.0087 (threshold: 0.0052) ✓
        """
        lines = []
        lines.append(
            f"Regime: {self.regime_result.regime.value} "
            f"({self.regime_result.regime.get_description()})"
        )

        if self.regime_result.triggering_conditions:
            lines.append(self.regime_result.format_conditions())
        else:
            # NEU or UND with no specific triggers
            lines.append(f"  {self.regime_result.interpretation}")

        return "\n".join(lines)

    def format_score(self) -> str:
        """Format unusualness score section.

        Returns:
            Multi-line string with score, interpretation band, and top drivers.
            Example:
                Unusualness: 78 (Unusual)
                Top drivers: GEX contrib=0.58; Dark contrib=0.46
        """
        if self.scoring_result is None:
            return "Unusualness: N/A (insufficient data)"

        lines = []
        lines.append(
            f"Unusualness: {self.scoring_result.percentile_score:.0f} "
            f"({self.scoring_result.interpretation.value})"
        )

        # Top 2-3 contributors (sorted by contribution descending)
        if self.scoring_result.feature_contributions:
            sorted_contribs = sorted(
                self.scoring_result.feature_contributions.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            driver_parts = []
            for feature, contribution in sorted_contribs:
                # Format as: FEATURE contrib=X.XX
                driver_parts.append(f"{feature.upper()} contrib={contribution:.2f}")
            lines.append(f"Top drivers: {'; '.join(driver_parts)}")

        return "\n".join(lines)

    def format_excluded_features(self) -> str:
        """Format excluded features section.

        Returns:
            Single line listing all excluded features with reasons.
            Example:
                Excluded: Charm (n = 9 < 21), Vanna (NaN value)
        """
        if not self.excluded_features:
            return "Excluded: none"

        excluded_strs = [str(ef) for ef in self.excluded_features]
        return f"Excluded: {', '.join(excluded_strs)}"

    def format_baseline_state(self) -> str:
        """Format baseline state section.

        Returns:
            Single line with baseline state.
            Example:
                Baseline: PARTIAL
        """
        return f"Baseline: {self.baseline_state.value}"

    def format_full(self) -> str:
        """Format complete diagnostic output.

        Returns:
            Multi-line string with all sections formatted per spec.
            Example:
                === OBSIDIAN MM Diagnostic: SPY @ 2024-01-15 ===

                Regime: Γ⁻ (Gamma-Negative Liquidity Vacuum)
                Z_GEX = -2.3100 (threshold: -1.5000) ✓
                Impact_vs_median = 0.0087 (threshold: 0.0052) ✓

                Unusualness: 78 (Unusual)
                Top drivers: GEX |Z|=2.31 × w=0.25 = 0.58; Dark |Z|=1.84 × w=0.25 = 0.46

                Excluded: Charm (n = 9 < 21)
                Baseline: PARTIAL
        """
        lines = []
        lines.append(f"=== OBSIDIAN MM Diagnostic: {self.ticker} @ {self.date} ===")
        lines.append("")
        lines.append(self.format_regime())
        lines.append("")
        lines.append(self.format_score())
        lines.append("")
        lines.append(self.format_excluded_features())
        lines.append(self.format_baseline_state())

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert diagnostic output to structured dictionary.

        Useful for API responses or structured storage.

        Returns:
            Dictionary with all diagnostic components as structured data.
        """
        return {
            "ticker": self.ticker,
            "date": self.date,
            "regime": {
                "type": self.regime_result.regime.value,
                "description": self.regime_result.regime.get_description(),
                "interpretation": self.regime_result.interpretation,
                "triggering_conditions": {
                    name: {"value": val, "threshold": thresh, "met": met}
                    for name, (val, thresh, met) in self.regime_result.triggering_conditions.items()
                },
                "baseline_sufficient": self.regime_result.baseline_sufficient,
            },
            "unusualness": {
                "score": (
                    self.scoring_result.percentile_score
                    if self.scoring_result
                    else None
                ),
                "interpretation": (
                    self.scoring_result.interpretation.value
                    if self.scoring_result
                    else None
                ),
                "raw_score": (
                    self.scoring_result.raw_score if self.scoring_result else None
                ),
                "top_contributors": (
                    [
                        {"feature": feat, "contribution": contrib}
                        for feat, contrib in sorted(
                            self.scoring_result.feature_contributions.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )[:3]
                    ]
                    if self.scoring_result
                    else []
                ),
            },
            "excluded_features": [
                {"feature": ef.feature_name, "reason": ef.reason}
                for ef in self.excluded_features
            ],
            "baseline_state": self.baseline_state.value,
        }


class Explainer:
    """Generates human-readable diagnostic explanations.

    Combines outputs from Baseline, Scorer, and Classifier into a single
    coherent diagnostic output that satisfies the explainability protocol.

    The explainer is stateless — it simply formats pre-computed results.
    All diagnostic logic lives in the upstream components (Baseline, Scorer, Classifier).
    """

    def __init__(self) -> None:
        """Initialize explainer (stateless)."""
        pass

    def explain(
        self,
        regime_result: RegimeResult,
        scoring_result: Optional[ScoringResult],
        excluded_features: list[ExcludedFeature],
        baseline_state: BaselineState,
        ticker: str,
        date: str,
    ) -> DiagnosticOutput:
        """Generate complete diagnostic output.

        Args:
            regime_result: Regime classification from Classifier
            scoring_result: Unusualness score from Scorer (None if insufficient data)
            excluded_features: List of features excluded from analysis
            baseline_state: Data sufficiency state from Baseline
            ticker: Instrument ticker symbol
            date: Date of diagnosis (ISO format)

        Returns:
            DiagnosticOutput with all formatted sections

        Example:
            >>> explainer = Explainer()
            >>> output = explainer.explain(
            ...     regime_result=classifier.classify(...),
            ...     scoring_result=scorer.compute_score(...),
            ...     excluded_features=[
            ...         ExcludedFeature("charm", "n = 9 < 21"),
            ...         ExcludedFeature("vanna", "NaN value"),
            ...     ],
            ...     baseline_state=BaselineState.PARTIAL,
            ...     ticker="SPY",
            ...     date="2024-01-15",
            ... )
            >>> print(output.format_full())
        """
        return DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded_features,
            baseline_state=baseline_state,
            ticker=ticker,
            date=date,
        )

    def create_exclusion(
        self,
        feature_name: str,
        n_obs: Optional[int] = None,
        min_required: int = 21,
        reason: Optional[str] = None,
    ) -> ExcludedFeature:
        """Create an ExcludedFeature with standardized reason formatting.

        Args:
            feature_name: Name of the feature
            n_obs: Number of observations (if insufficient data)
            min_required: Minimum required observations (default 21 per spec)
            reason: Custom reason string (overrides n_obs formatting)

        Returns:
            ExcludedFeature with formatted reason

        Example:
            >>> explainer.create_exclusion("charm", n_obs=14, min_required=21)
            ExcludedFeature(feature_name='charm', reason='n = 14 < 21')

            >>> explainer.create_exclusion("vanna", reason="NaN value")
            ExcludedFeature(feature_name='vanna', reason='NaN value')
        """
        if reason is not None:
            formatted_reason = reason
        elif n_obs is not None:
            formatted_reason = f"n = {n_obs} < {min_required}"
        else:
            formatted_reason = "insufficient data"

        return ExcludedFeature(feature_name=feature_name, reason=formatted_reason)
