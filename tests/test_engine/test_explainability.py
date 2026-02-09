"""Tests for Explainability Protocol.

Test Coverage:
    - ExcludedFeature formatting
    - DiagnosticOutput formatting (regime, score, excluded, baseline, full)
    - DiagnosticOutput structured dictionary output
    - Explainer integration
    - Edge cases (missing data, no exclusions, no triggers)
"""

import pytest

from obsidian.engine.baseline import BaselineState
from obsidian.engine.classifier import Classifier, RegimeType, RegimeResult
from obsidian.engine.explainability import DiagnosticOutput, ExcludedFeature, Explainer
from obsidian.engine.scoring import InterpretationBand, Scorer, ScoringResult


class TestExcludedFeature:
    """Test ExcludedFeature dataclass."""

    def test_str_formatting(self):
        """ExcludedFeature formats as 'Name (reason)'."""
        ef = ExcludedFeature(feature_name="charm", reason="n = 9 < 21")
        assert str(ef) == "charm (n = 9 < 21)"

    def test_custom_reason(self):
        """ExcludedFeature accepts custom reason strings."""
        ef = ExcludedFeature(feature_name="vanna", reason="NaN value")
        assert str(ef) == "vanna (NaN value)"


class TestDiagnosticOutputFormatRegime:
    """Test DiagnosticOutput.format_regime()."""

    def test_regime_with_triggers(self):
        """Format regime with triggering conditions."""
        regime_result = RegimeResult(
            regime=RegimeType.GAMMA_NEGATIVE,
            triggering_conditions={
                "Z_GEX": (-2.31, -1.5, True),
                "Impact_vs_median": (0.0087, 0.0052, True),
            },
            interpretation="Test interpretation",
            baseline_sufficient=True,
        )
        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_regime()
        assert "Γ⁻" in formatted
        assert "Gamma-Negative" in formatted
        assert "Z_GEX = -2.3100" in formatted
        assert "✓" in formatted

    def test_regime_without_triggers_neutral(self):
        """Format NEU regime with no triggering conditions."""
        regime_result = RegimeResult(
            regime=RegimeType.NEUTRAL,
            triggering_conditions={},
            interpretation="No dominant pattern",
            baseline_sufficient=True,
        )
        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_regime()
        assert "NEU" in formatted
        assert "No dominant pattern" in formatted

    def test_regime_undetermined(self):
        """Format UND regime with no triggering conditions."""
        regime_result = RegimeResult(
            regime=RegimeType.UNDETERMINED,
            triggering_conditions={},
            interpretation="Insufficient data",
            baseline_sufficient=False,
        )
        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.EMPTY,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_regime()
        assert "UND" in formatted
        assert "Insufficient data" in formatted


class TestDiagnosticOutputFormatScore:
    """Test DiagnosticOutput.format_score()."""

    def test_score_with_contributors(self):
        """Format score with top contributors."""
        scoring_result = ScoringResult(
            raw_score=1.15,
            percentile_score=78.0,
            interpretation=InterpretationBand.UNUSUAL,
            feature_contributions={"gex": 0.5775, "dark_share": 0.46, "venue_mix": 0.1},
            excluded_features=[],
        )
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.NEUTRAL,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=True,
            ),
            scoring_result=scoring_result,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_score()
        assert "Unusualness: 78" in formatted
        assert "Unusual" in formatted.replace("Unusualness", "")  # Band name
        assert "Top drivers:" in formatted
        assert "GEX" in formatted
        assert "contrib=" in formatted

    def test_score_none_insufficient_data(self):
        """Format when scoring_result is None."""
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.UNDETERMINED,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=False,
            ),
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.EMPTY,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_score()
        assert "N/A" in formatted
        assert "insufficient data" in formatted


class TestDiagnosticOutputFormatExcluded:
    """Test DiagnosticOutput.format_excluded_features()."""

    def test_excluded_features_present(self):
        """Format with multiple excluded features."""
        excluded = [
            ExcludedFeature("charm", "n = 9 < 21"),
            ExcludedFeature("vanna", "NaN value"),
        ]
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.NEUTRAL,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=True,
            ),
            scoring_result=None,
            excluded_features=excluded,
            baseline_state=BaselineState.PARTIAL,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_excluded_features()
        assert "Excluded:" in formatted
        assert "charm (n = 9 < 21)" in formatted
        assert "vanna (NaN value)" in formatted

    def test_no_excluded_features(self):
        """Format when no features excluded."""
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.NEUTRAL,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=True,
            ),
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="SPY",
            date="2024-01-15",
        )

        formatted = output.format_excluded_features()
        assert formatted == "Excluded: none"


class TestDiagnosticOutputFormatBaselineState:
    """Test DiagnosticOutput.format_baseline_state()."""

    def test_baseline_complete(self):
        """Format COMPLETE baseline state."""
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.NEUTRAL,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=True,
            ),
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="SPY",
            date="2024-01-15",
        )
        assert output.format_baseline_state() == "Baseline: COMPLETE"

    def test_baseline_partial(self):
        """Format PARTIAL baseline state."""
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.NEUTRAL,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=True,
            ),
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.PARTIAL,
            ticker="SPY",
            date="2024-01-15",
        )
        assert output.format_baseline_state() == "Baseline: PARTIAL"

    def test_baseline_empty(self):
        """Format EMPTY baseline state."""
        output = DiagnosticOutput(
            regime_result=RegimeResult(
                regime=RegimeType.UNDETERMINED,
                triggering_conditions={},
                interpretation="",
                baseline_sufficient=False,
            ),
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.EMPTY,
            ticker="SPY",
            date="2024-01-15",
        )
        assert output.format_baseline_state() == "Baseline: EMPTY"


class TestDiagnosticOutputFormatFull:
    """Test DiagnosticOutput.format_full()."""

    def test_full_output_spec_example(self):
        """Format complete output matching spec example."""
        regime_result = RegimeResult(
            regime=RegimeType.GAMMA_NEGATIVE,
            triggering_conditions={
                "Z_GEX": (-2.31, -1.5, True),
                "Impact_vs_median": (0.0087, 0.0052, True),
            },
            interpretation="Liquidity vacuum",
            baseline_sufficient=True,
        )
        scoring_result = ScoringResult(
            raw_score=1.15,
            percentile_score=78.0,
            interpretation=InterpretationBand.UNUSUAL,
            feature_contributions={"gex": 0.5775, "dark_share": 0.46},
            excluded_features=["charm"],
        )
        excluded = [ExcludedFeature("charm", "n = 9 < 21")]

        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded,
            baseline_state=BaselineState.PARTIAL,
            ticker="SPY",
            date="2024-01-15",
        )

        full = output.format_full()

        # Check header
        assert "OBSIDIAN MM Diagnostic: SPY @ 2024-01-15" in full

        # Check regime section
        assert "Γ⁻" in full
        assert "Gamma-Negative" in full
        assert "Z_GEX = -2.3100" in full

        # Check score section
        assert "Unusualness: 78" in full
        assert "Unusual" in full
        assert "Top drivers:" in full

        # Check excluded section
        assert "Excluded: charm (n = 9 < 21)" in full

        # Check baseline section
        assert "Baseline: PARTIAL" in full

    def test_full_output_minimal_undetermined(self):
        """Format minimal output for UND regime."""
        regime_result = RegimeResult(
            regime=RegimeType.UNDETERMINED,
            triggering_conditions={},
            interpretation="Insufficient data",
            baseline_sufficient=False,
        )

        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.EMPTY,
            ticker="AAPL",
            date="2024-01-01",
        )

        full = output.format_full()
        assert "AAPL @ 2024-01-01" in full
        assert "UND" in full
        assert "N/A" in full  # Score is N/A
        assert "Excluded: none" in full
        assert "Baseline: EMPTY" in full


class TestDiagnosticOutputToDict:
    """Test DiagnosticOutput.to_dict()."""

    def test_to_dict_complete(self):
        """Convert complete diagnostic to structured dict."""
        regime_result = RegimeResult(
            regime=RegimeType.GAMMA_POSITIVE,
            triggering_conditions={
                "Z_GEX": (2.14, 1.5, True),
                "Efficiency_vs_median": (0.0032, 0.0041, True),
            },
            interpretation="Volatility suppression",
            baseline_sufficient=True,
        )
        scoring_result = ScoringResult(
            raw_score=0.95,
            percentile_score=85.0,
            interpretation=InterpretationBand.EXTREME,
            feature_contributions={"gex": 0.535, "dark_share": 0.3},
            excluded_features=[],
        )
        excluded = [ExcludedFeature("vanna", "NaN value")]

        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded,
            baseline_state=BaselineState.COMPLETE,
            ticker="QQQ",
            date="2024-02-01",
        )

        result = output.to_dict()

        # Check structure
        assert result["ticker"] == "QQQ"
        assert result["date"] == "2024-02-01"
        assert result["regime"]["type"] == "Γ⁺"
        assert result["regime"]["description"] == "Gamma-Positive Control"
        assert result["regime"]["baseline_sufficient"] is True
        assert "Z_GEX" in result["regime"]["triggering_conditions"]
        assert result["unusualness"]["score"] == 85.0
        assert result["unusualness"]["interpretation"] == "Extreme"
        assert len(result["unusualness"]["top_contributors"]) == 2
        assert result["unusualness"]["top_contributors"][0]["feature"] == "gex"
        assert result["excluded_features"][0]["feature"] == "vanna"
        assert result["excluded_features"][0]["reason"] == "NaN value"
        assert result["baseline_state"] == "COMPLETE"

    def test_to_dict_none_scoring_result(self):
        """Convert diagnostic with None scoring_result to dict."""
        regime_result = RegimeResult(
            regime=RegimeType.UNDETERMINED,
            triggering_conditions={},
            interpretation="",
            baseline_sufficient=False,
        )

        output = DiagnosticOutput(
            regime_result=regime_result,
            scoring_result=None,
            excluded_features=[],
            baseline_state=BaselineState.EMPTY,
            ticker="TEST",
            date="2024-01-01",
        )

        result = output.to_dict()
        assert result["unusualness"]["score"] is None
        assert result["unusualness"]["interpretation"] is None
        assert result["unusualness"]["raw_score"] is None
        assert result["unusualness"]["top_contributors"] == []


class TestExplainer:
    """Test Explainer class."""

    def test_explain_integration(self):
        """Explainer combines all components into DiagnosticOutput."""
        explainer = Explainer()

        regime_result = RegimeResult(
            regime=RegimeType.DARK_DOMINANT,
            triggering_conditions={
                "DarkShare": (0.75, 0.70, True),
                "Z_block": (1.5, 1.0, True),
            },
            interpretation="Institutional positioning",
            baseline_sufficient=True,
        )
        scoring_result = ScoringResult(
            raw_score=0.85,
            percentile_score=72.0,
            interpretation=InterpretationBand.UNUSUAL,
            feature_contributions={"dark_share": 0.5, "block_intensity": 0.225},
            excluded_features=[],
        )
        excluded = [ExcludedFeature("charm", "n = 12 < 21")]

        output = explainer.explain(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded,
            baseline_state=BaselineState.PARTIAL,
            ticker="NVDA",
            date="2024-03-15",
        )

        assert isinstance(output, DiagnosticOutput)
        assert output.ticker == "NVDA"
        assert output.date == "2024-03-15"
        assert output.regime_result.regime == RegimeType.DARK_DOMINANT
        assert output.scoring_result.percentile_score == 72.0
        assert len(output.excluded_features) == 1
        assert output.baseline_state == BaselineState.PARTIAL

    def test_create_exclusion_with_n_obs(self):
        """Create exclusion with observation count."""
        explainer = Explainer()
        excluded = explainer.create_exclusion("charm", n_obs=14, min_required=21)

        assert excluded.feature_name == "charm"
        assert excluded.reason == "n = 14 < 21"

    def test_create_exclusion_with_custom_reason(self):
        """Create exclusion with custom reason."""
        explainer = Explainer()
        excluded = explainer.create_exclusion("vanna", reason="API unavailable")

        assert excluded.feature_name == "vanna"
        assert excluded.reason == "API unavailable"

    def test_create_exclusion_default(self):
        """Create exclusion with default reason."""
        explainer = Explainer()
        excluded = explainer.create_exclusion("unknown_feature")

        assert excluded.feature_name == "unknown_feature"
        assert excluded.reason == "insufficient data"


class TestRealWorldScenarios:
    """Test realistic diagnostic scenarios."""

    def test_complete_diagnostic_pipeline(self):
        """End-to-end diagnostic from classifier + scorer."""
        # Simulate a Γ⁻ scenario
        classifier = Classifier()
        regime_result = classifier.classify(
            z_scores={"gex": -2.31, "dex": 0.5, "block_intensity": 0.8},
            raw_features={"dark_share": 0.65, "impact": 0.0087},
            baseline_medians={"impact": 0.0052},
            daily_return=-0.015,
            baseline_sufficient=True,
        )

        # Simulate scoring
        scorer = Scorer()
        raw_score, contributions = scorer.compute_raw_score(
            z_scores={"gex": -2.31, "dark_share": 1.84, "venue_mix": 0.5},
            excluded_features=["charm"],
        )
        scoring_result = ScoringResult(
            raw_score=raw_score,
            percentile_score=78.0,
            interpretation=InterpretationBand.UNUSUAL,
            feature_contributions=contributions,
            excluded_features=["charm"],
        )

        # Create explainer output
        explainer = Explainer()
        excluded = [explainer.create_exclusion("charm", n_obs=9, min_required=21)]

        output = explainer.explain(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=excluded,
            baseline_state=BaselineState.PARTIAL,
            ticker="SPY",
            date="2024-01-15",
        )

        # Verify complete output
        assert output.regime_result.regime == RegimeType.GAMMA_NEGATIVE
        assert output.scoring_result.percentile_score == 78.0
        assert len(output.excluded_features) == 1
        assert output.baseline_state == BaselineState.PARTIAL

        # Verify formatting
        full = output.format_full()
        assert "SPY" in full
        assert "Γ⁻" in full
        assert "78" in full
        assert "charm (n = 9 < 21)" in full
        assert "PARTIAL" in full

    def test_neutral_regime_no_exclusions(self):
        """Diagnostic for NEU regime with complete baseline."""
        classifier = Classifier()
        regime_result = classifier.classify(
            z_scores={"gex": 0.5, "dex": 0.3},
            raw_features={"dark_share": 0.45},
            baseline_medians={},
            daily_return=0.002,
            baseline_sufficient=True,
        )

        scoring_result = ScoringResult(
            raw_score=0.35,
            percentile_score=42.0,
            interpretation=InterpretationBand.ELEVATED,
            feature_contributions={"gex": 0.125, "dark_share": 0.15, "dex": 0.075},
            excluded_features=[],
        )

        explainer = Explainer()
        output = explainer.explain(
            regime_result=regime_result,
            scoring_result=scoring_result,
            excluded_features=[],
            baseline_state=BaselineState.COMPLETE,
            ticker="TSLA",
            date="2024-04-01",
        )

        assert output.regime_result.regime == RegimeType.NEUTRAL
        assert output.scoring_result.interpretation == InterpretationBand.ELEVATED
        assert output.excluded_features == []
        assert output.baseline_state == BaselineState.COMPLETE

        full = output.format_full()
        assert "NEU" in full
        assert "Elevated" in full
        assert "Excluded: none" in full
        assert "COMPLETE" in full
