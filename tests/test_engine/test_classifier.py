"""Tests for MM Regime Classifier.

Test Coverage:
    - Priority-ordered rule evaluation (first match wins)
    - Each regime's triggering conditions
    - NaN handling and data insufficiency
    - Edge cases at exact thresholds
    - Baseline insufficiency → UND
    - NEU as fallback when no rule matches
"""

import numpy as np
import pytest

from obsidian.engine.classifier import Classifier, RegimeType, RegimeResult


class TestClassifierInitialization:
    """Test classifier initialization and thresholds."""

    def test_initialization(self):
        """Classifier initializes with fixed thresholds from spec."""
        classifier = Classifier()
        assert classifier.Z_GEX_THRESHOLD == 1.5
        assert classifier.Z_BLOCK_THRESHOLD == 1.0
        assert classifier.Z_DEX_THRESHOLD == 1.0
        assert classifier.DARK_SHARE_DD_THRESHOLD == 0.70
        assert classifier.DARK_SHARE_ABS_THRESHOLD == 0.50
        assert classifier.PRICE_MOVE_ABS_CAP == -0.005
        assert classifier.PRICE_MOVE_DIST_CAP == 0.005


class TestRegimeType:
    """Test RegimeType enum."""

    def test_regime_values(self):
        """Regime types have correct string values."""
        assert RegimeType.GAMMA_POSITIVE.value == "Γ⁺"
        assert RegimeType.GAMMA_NEGATIVE.value == "Γ⁻"
        assert RegimeType.DARK_DOMINANT.value == "DD"
        assert RegimeType.ABSORPTION.value == "ABS"
        assert RegimeType.DISTRIBUTION.value == "DIST"
        assert RegimeType.NEUTRAL.value == "NEU"
        assert RegimeType.UNDETERMINED.value == "UND"

    def test_get_description(self):
        """Each regime has a human-readable description."""
        assert "Gamma-Positive" in RegimeType.GAMMA_POSITIVE.get_description()
        assert "Gamma-Negative" in RegimeType.GAMMA_NEGATIVE.get_description()
        assert "Dark-Dominant" in RegimeType.DARK_DOMINANT.get_description()

    def test_get_interpretation(self):
        """Each regime has a microstructure interpretation."""
        assert "dealers" in RegimeType.GAMMA_POSITIVE.get_interpretation().lower()
        assert "liquidity vacuum" in RegimeType.GAMMA_NEGATIVE.get_interpretation().lower()
        assert "institutional" in RegimeType.DARK_DOMINANT.get_interpretation().lower()


class TestRegimeResult:
    """Test RegimeResult dataclass."""

    def test_format_conditions(self):
        """Triggering conditions format correctly."""
        result = RegimeResult(
            regime=RegimeType.GAMMA_POSITIVE,
            triggering_conditions={
                "Z_GEX": (2.14, 1.5, True),
                "Efficiency_vs_median": (0.0032, 0.0041, True),
            },
            interpretation="Test interpretation",
            baseline_sufficient=True,
        )
        formatted = result.format_conditions()
        assert "Z_GEX = 2.1400" in formatted
        assert "✓" in formatted
        assert "Efficiency_vs_median" in formatted


class TestPriority1GammaPositive:
    """Test Priority 1: Γ⁺ (Gamma-Positive Control)."""

    def test_gamma_positive_basic(self):
        """Γ⁺ triggers when Z_GEX > 1.5 and Efficiency < median."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.0, "dex": 0.5},
            raw_features={"dark_share": 0.5, "efficiency": 0.003, "impact": 0.005},
            baseline_medians={"efficiency": 0.004, "impact": 0.005},
            daily_return=0.01,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.GAMMA_POSITIVE
        assert result.baseline_sufficient is True
        assert "Z_GEX" in result.triggering_conditions
        assert result.triggering_conditions["Z_GEX"][0] == 2.0
        assert result.triggering_conditions["Z_GEX"][2] is True  # Met

    def test_gamma_positive_at_threshold(self):
        """Γ⁺ does NOT trigger at exactly Z_GEX = 1.5 (needs > not ≥)."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 1.5},  # Exactly at threshold
            raw_features={"efficiency": 0.003},
            baseline_medians={"efficiency": 0.004},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        # Should not match Γ⁺, should fall through to NEU
        assert result.regime == RegimeType.NEUTRAL

    def test_gamma_positive_efficiency_equal_median(self):
        """Γ⁺ does NOT trigger if Efficiency = median (needs < not ≤)."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.0},
            raw_features={"efficiency": 0.004},
            baseline_medians={"efficiency": 0.004},  # Equal
            daily_return=0.0,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.NEUTRAL

    def test_gamma_positive_missing_efficiency(self):
        """Γ⁺ skipped if Efficiency is NaN."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.0},
            raw_features={"efficiency": np.nan},
            baseline_medians={"efficiency": 0.004},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        # Should skip Γ⁺ and fall through
        assert result.regime != RegimeType.GAMMA_POSITIVE


class TestPriority2GammaNegative:
    """Test Priority 2: Γ⁻ (Gamma-Negative Liquidity Vacuum)."""

    def test_gamma_negative_basic(self):
        """Γ⁻ triggers when Z_GEX < -1.5 and Impact > median."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": -2.0},
            raw_features={"impact": 0.007},
            baseline_medians={"impact": 0.005},
            daily_return=-0.02,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.GAMMA_NEGATIVE
        assert "Z_GEX" in result.triggering_conditions
        assert result.triggering_conditions["Z_GEX"][0] == -2.0

    def test_gamma_negative_priority_over_others(self):
        """Γ⁻ takes priority over lower-priority regimes even if they match."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={
                "gex": -2.0,
                "dex": 1.5,  # Would match DIST
                "block_intensity": 1.2,
            },
            raw_features={"dark_share": 0.75, "impact": 0.007},
            baseline_medians={"impact": 0.005},
            daily_return=0.004,  # Would satisfy DIST condition
            baseline_sufficient=True,
        )
        # Should be Γ⁻ because it's higher priority
        assert result.regime == RegimeType.GAMMA_NEGATIVE


class TestPriority3DarkDominant:
    """Test Priority 3: DD (Dark-Dominant Accumulation)."""

    def test_dark_dominant_basic(self):
        """DD triggers when DarkShare > 0.70 and Z_block > 1.0."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 0.5, "block_intensity": 1.5},
            raw_features={"dark_share": 0.75},
            baseline_medians={},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.DARK_DOMINANT
        assert "DarkShare" in result.triggering_conditions
        assert result.triggering_conditions["DarkShare"][0] == 0.75

    def test_dark_dominant_at_thresholds(self):
        """DD does NOT trigger at exactly DarkShare = 0.70 or Z_block = 1.0."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"block_intensity": 1.0},  # Exactly at threshold
            raw_features={"dark_share": 0.70},  # Exactly at threshold
            baseline_medians={},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.NEUTRAL


class TestPriority4Absorption:
    """Test Priority 4: ABS (Absorption-Like)."""

    def test_absorption_basic(self):
        """ABS triggers when Z_DEX < -1.0, return ≥ -0.5%, DarkShare > 0.50."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 0.0, "dex": -1.5},
            raw_features={"dark_share": 0.60},
            baseline_medians={},
            daily_return=-0.003,  # -0.3%, better than -0.5%
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.ABSORPTION
        assert "Z_DEX" in result.triggering_conditions
        assert result.triggering_conditions["Z_DEX"][0] == -1.5

    def test_absorption_return_too_negative(self):
        """ABS does NOT trigger if return < -0.5%."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": -1.5},
            raw_features={"dark_share": 0.60},
            baseline_medians={},
            daily_return=-0.006,  # -0.6%, worse than -0.5%
            baseline_sufficient=True,
        )
        assert result.regime != RegimeType.ABSORPTION

    def test_absorption_dark_share_too_low(self):
        """ABS does NOT trigger if DarkShare ≤ 0.50."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": -1.5},
            raw_features={"dark_share": 0.50},  # Exactly at threshold
            baseline_medians={},
            daily_return=-0.003,
            baseline_sufficient=True,
        )
        assert result.regime != RegimeType.ABSORPTION


class TestPriority5Distribution:
    """Test Priority 5: DIST (Distribution-Like)."""

    def test_distribution_basic(self):
        """DIST triggers when Z_DEX > 1.0 and return ≤ +0.5%."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 0.0, "dex": 1.5},
            raw_features={},
            baseline_medians={},
            daily_return=0.003,  # +0.3%, less than +0.5%
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.DISTRIBUTION
        assert "Z_DEX" in result.triggering_conditions

    def test_distribution_return_too_positive(self):
        """DIST does NOT trigger if return > +0.5%."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": 1.5},
            raw_features={},
            baseline_medians={},
            daily_return=0.006,  # +0.6%, exceeds +0.5%
            baseline_sufficient=True,
        )
        assert result.regime != RegimeType.DISTRIBUTION


class TestPriority6Neutral:
    """Test Priority 6: NEU (Neutral / Mixed)."""

    def test_neutral_fallback(self):
        """NEU is assigned when no higher-priority rule matches."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 0.5, "dex": 0.3, "block_intensity": 0.2},
            raw_features={"dark_share": 0.40, "efficiency": 0.004, "impact": 0.005},
            baseline_medians={"efficiency": 0.004, "impact": 0.005},
            daily_return=0.002,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.NEUTRAL
        assert result.triggering_conditions == {}  # No specific triggers
        assert result.baseline_sufficient is True

    def test_neutral_with_nan_features(self):
        """NEU can be assigned even with some NaN features."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": np.nan, "dex": 0.5},
            raw_features={"dark_share": 0.40},
            baseline_medians={},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.NEUTRAL


class TestPriority7Undetermined:
    """Test Priority 7: UND (Undetermined)."""

    def test_undetermined_insufficient_baseline(self):
        """UND is assigned immediately if baseline_sufficient=False."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.0},  # Would match Γ⁺ if baseline sufficient
            raw_features={"efficiency": 0.003},
            baseline_medians={"efficiency": 0.004},
            daily_return=0.0,
            baseline_sufficient=False,  # Insufficient
        )
        assert result.regime == RegimeType.UNDETERMINED
        assert result.baseline_sufficient is False
        assert result.triggering_conditions == {}


class TestShortCircuitBehavior:
    """Test that rule evaluation short-circuits (first match wins)."""

    def test_gamma_positive_wins_over_dark_dominant(self):
        """If both Γ⁺ and DD match, Γ⁺ wins (higher priority)."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.0, "block_intensity": 1.5},
            raw_features={"dark_share": 0.75, "efficiency": 0.003},
            baseline_medians={"efficiency": 0.004},
            daily_return=0.0,
            baseline_sufficient=True,
        )
        # Both Γ⁺ and DD conditions met, but Γ⁺ is higher priority
        assert result.regime == RegimeType.GAMMA_POSITIVE

    def test_dark_dominant_wins_over_absorption(self):
        """If both DD and ABS match, DD wins (higher priority)."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": -1.5, "block_intensity": 1.5},
            raw_features={"dark_share": 0.75},
            baseline_medians={},
            daily_return=-0.003,
            baseline_sufficient=True,
        )
        # Both DD and ABS conditions met, but DD is higher priority
        assert result.regime == RegimeType.DARK_DOMINANT


class TestNaNHandling:
    """Test NaN handling in classification."""

    def test_all_features_nan(self):
        """All NaN features → NEU (baseline sufficient but no data)."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={},
            raw_features={},
            baseline_medians={},
            daily_return=np.nan,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.NEUTRAL

    def test_partial_nan_skips_rules(self):
        """NaN in required features causes rule to be skipped."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": np.nan, "dex": 1.5},
            raw_features={"efficiency": np.nan},
            baseline_medians={"efficiency": 0.004},
            daily_return=0.003,
            baseline_sufficient=True,
        )
        # Γ⁺ and Γ⁻ skipped (Z_GEX is NaN)
        # DD skipped (Z_block missing)
        # ABS skipped (Z_DEX present but checks earlier)
        # DIST should match (Z_DEX > 1.0, return ≤ 0.5%)
        assert result.regime == RegimeType.DISTRIBUTION


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_daily_return(self):
        """Zero return is handled correctly in ABS and DIST checks."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": 1.5},
            raw_features={},
            baseline_medians={},
            daily_return=0.0,  # Zero return satisfies DIST (≤ 0.5%)
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.DISTRIBUTION

    def test_negative_zero_vs_positive_zero(self):
        """Python handles -0.0 and +0.0 correctly in comparisons."""
        classifier = Classifier()
        result1 = classifier.classify(
            z_scores={"dex": 1.5},
            raw_features={},
            baseline_medians={},
            daily_return=-0.0,
            baseline_sufficient=True,
        )
        result2 = classifier.classify(
            z_scores={"dex": 1.5},
            raw_features={},
            baseline_medians={},
            daily_return=+0.0,
            baseline_sufficient=True,
        )
        assert result1.regime == result2.regime == RegimeType.DISTRIBUTION

    def test_missing_optional_features(self):
        """Missing features that aren't needed for matched rule don't break classification."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"dex": 1.5},  # Only DEX provided
            raw_features={},  # No raw features
            baseline_medians={},  # No baselines
            daily_return=0.003,
            baseline_sufficient=True,
        )
        # DIST should match (only needs Z_DEX and return)
        assert result.regime == RegimeType.DISTRIBUTION


class TestRealWorldScenarios:
    """Test realistic scenarios from spec examples."""

    def test_spec_example_gamma_negative(self):
        """Reproduce spec example: Γ⁻ with Z_GEX = -2.31, Impact > median."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": -2.31, "dex": 0.5},
            raw_features={"dark_share": 0.65, "impact": 0.0087},
            baseline_medians={"impact": 0.0052},
            daily_return=-0.015,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.GAMMA_NEGATIVE
        assert result.triggering_conditions["Z_GEX"][0] == pytest.approx(-2.31)
        assert result.triggering_conditions["Impact_vs_median"][0] == 0.0087

    def test_volatility_suppression_scenario(self):
        """High positive GEX with compressed efficiency → Γ⁺."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"gex": 2.5},
            raw_features={"efficiency": 0.002},
            baseline_medians={"efficiency": 0.005},
            daily_return=0.001,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.GAMMA_POSITIVE

    def test_institutional_dark_pool_scenario(self):
        """High dark share + elevated blocks → DD."""
        classifier = Classifier()
        result = classifier.classify(
            z_scores={"block_intensity": 2.0},
            raw_features={"dark_share": 0.82},
            baseline_medians={},
            daily_return=0.005,
            baseline_sufficient=True,
        )
        assert result.regime == RegimeType.DARK_DOMINANT
