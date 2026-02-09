"""Tests for Scoring system: weighted |Z| sum → percentile rank."""

import numpy as np
import pandas as pd
import pytest

from obsidian.engine.scoring import (
    Scorer,
    ScoringResult,
    InterpretationBand,
    FEATURE_WEIGHTS,
)


class TestFeatureWeights:
    """Test fixed feature weights from spec."""
    
    def test_weights_sum_to_one(self) -> None:
        """Weights sum to 1.0 per spec."""
        weight_sum = sum(FEATURE_WEIGHTS.values())
        assert weight_sum == pytest.approx(1.0)
    
    def test_spec_compliant_weights(self) -> None:
        """Weights match spec Section 5.1."""
        assert FEATURE_WEIGHTS["dark_share"] == 0.25
        assert FEATURE_WEIGHTS["gex"] == 0.25
        assert FEATURE_WEIGHTS["venue_mix"] == 0.20
        assert FEATURE_WEIGHTS["block_intensity"] == 0.15
        assert FEATURE_WEIGHTS["iv_rank"] == 0.15


class TestScorerInit:
    """Test Scorer initialization."""
    
    def test_default_initialization(self) -> None:
        """Default params match spec."""
        scorer = Scorer()
        assert scorer.window == 63
        assert scorer.weights == FEATURE_WEIGHTS
    
    def test_custom_initialization(self) -> None:
        """Can customize parameters."""
        custom_weights = {"gex": 0.5, "dark_share": 0.5}
        scorer = Scorer(window=100, weights=custom_weights)
        assert scorer.window == 100
        assert scorer.weights == custom_weights
    
    def test_window_validation(self) -> None:
        """Window must be >= 1."""
        with pytest.raises(ValueError, match="Window.*must be >= 1"):
            Scorer(window=0)
    
    def test_warns_on_weight_sum_mismatch(self) -> None:
        """Warns if weights don't sum to ~1.0."""
        bad_weights = {"gex": 0.5, "dark_share": 0.3}  # Sum = 0.8
        with pytest.warns(UserWarning, match="weights sum to"):
            Scorer(weights=bad_weights)


class TestRawScoreComputation:
    """Test raw weighted absolute z-score sum."""
    
    def test_basic_raw_score(self) -> None:
        """Basic raw score calculation."""
        scorer = Scorer()
        z_scores = {
            "gex": 2.0,           # 0.25 * 2.0 = 0.50
            "dark_share": 1.5,    # 0.25 * 1.5 = 0.375
            "iv_rank": 0.5,       # 0.15 * 0.5 = 0.075
        }
        
        raw_score, contributions = scorer.compute_raw_score(z_scores)
        
        expected = 0.50 + 0.375 + 0.075  # = 0.95
        assert raw_score == pytest.approx(expected)
        assert contributions["gex"] == pytest.approx(0.50)
        assert contributions["dark_share"] == pytest.approx(0.375)
        assert contributions["iv_rank"] == pytest.approx(0.075)
    
    def test_uses_absolute_values(self) -> None:
        """Uses absolute values of z-scores."""
        scorer = Scorer()
        z_scores = {
            "gex": -2.0,          # |−2.0| * 0.25 = 0.50
            "dark_share": 1.5,    # |1.5| * 0.25 = 0.375
        }
        
        raw_score, _ = scorer.compute_raw_score(z_scores)
        
        expected = 0.50 + 0.375
        assert raw_score == pytest.approx(expected)
    
    def test_skips_nan_values(self) -> None:
        """NaN z-scores are excluded."""
        scorer = Scorer()
        z_scores = {
            "gex": 2.0,
            "dark_share": np.nan,  # Should be skipped
            "iv_rank": 0.5,
        }
        
        raw_score, contributions = scorer.compute_raw_score(z_scores)
        
        expected = 0.25 * 2.0 + 0.15 * 0.5  # Only gex and iv_skew
        assert raw_score == pytest.approx(expected)
        assert "dark_share" not in contributions
    
    def test_excludes_specified_features(self) -> None:
        """Excluded features not included in score."""
        scorer = Scorer()
        z_scores = {
            "gex": 2.0,
            "dark_share": 1.5,
            "iv_rank": 0.5,
        }
        
        raw_score, contributions = scorer.compute_raw_score(
            z_scores,
            excluded_features=["dark_share"]
        )
        
        # Only gex and iv_skew
        expected = 0.25 * 2.0 + 0.15 * 0.5
        assert raw_score == pytest.approx(expected)
        assert "dark_share" not in contributions
    
    def test_zero_weight_features_ignored(self) -> None:
        """Features not in weights dict are ignored."""
        scorer = Scorer()
        z_scores = {
            "gex": 2.0,
            "unknown_feature": 100.0,  # Not in weights
        }
        
        raw_score, contributions = scorer.compute_raw_score(z_scores)
        
        # Only gex
        assert raw_score == pytest.approx(0.50)
        assert "unknown_feature" not in contributions
    
    def test_weights_not_renormalized(self) -> None:
        """Weights NOT renormalized when features excluded (per spec)."""
        scorer = Scorer()
        
        # All features
        all_scores = {
            "gex": 1.0,
            "dark_share": 1.0,
            "venue_mix": 1.0,
            "block_intensity": 1.0,
            "iv_rank": 1.0,
        }
        raw_all, _ = scorer.compute_raw_score(all_scores)
        assert raw_all == pytest.approx(1.0)  # Sum of weights
        
        # Exclude some features - raw score should be lower
        partial_scores = {
            "gex": 1.0,
            "dark_share": 1.0,
        }
        raw_partial, _ = scorer.compute_raw_score(partial_scores)
        assert raw_partial == pytest.approx(0.50)  # Only 0.25 + 0.25


class TestPercentileMapping:
    """Test percentile rank computation."""
    
    def test_basic_percentile(self) -> None:
        """Basic percentile computation."""
        scorer = Scorer(window=5)
        raw_scores = pd.Series([1.0, 1.5, 2.0, 1.2, 3.0])
        
        percentiles = scorer.compute_percentile_scores(raw_scores)
        
        # Last value (3.0) is highest → 100th percentile
        assert percentiles.iloc[-1] == pytest.approx(100.0)
        
        # First value (1.0) is lowest → 20th percentile (1/5 = 20%)
        assert percentiles.iloc[0] == pytest.approx(100.0)  # At t=0, only 1 value
    
    def test_expanding_window(self) -> None:
        """Expanding window for t < window."""
        scorer = Scorer(window=5)
        raw_scores = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        
        percentiles = scorer.compute_percentile_scores(raw_scores, use_expanding=True)
        
        # At t=2 (value=3.0), window is [1.0, 2.0, 3.0]
        # 3.0 is highest → 100th percentile
        assert percentiles.iloc[2] == pytest.approx(100.0)
        
        # At t=5 (value=6.0), window is [2,3,4,5,6] (rolling window of 5)
        # 6.0 is highest → 100th percentile
        assert percentiles.iloc[5] == pytest.approx(100.0)
    
    def test_rolling_window(self) -> None:
        """Rolling window excludes old data."""
        scorer = Scorer(window=3)
        raw_scores = pd.Series([1.0, 2.0, 3.0, 1.5])  # Last value is not highest

        percentiles = scorer.compute_percentile_scores(raw_scores, use_expanding=False)

        # At t=3 (value=1.5), rolling window is [2.0, 3.0, 1.5]
        # 1.5 is smallest (1st out of 3) → 33.3rd percentile (1/3)
        assert percentiles.iloc[3] == pytest.approx(33.33, abs=0.1)
    
    def test_nan_handling(self) -> None:
        """NaN values handled correctly."""
        scorer = Scorer(window=5)
        raw_scores = pd.Series([1.0, np.nan, 3.0, 2.0])
        
        percentiles = scorer.compute_percentile_scores(raw_scores)
        
        # NaN input → NaN output
        assert pd.isna(percentiles.iloc[1])
        
        # Non-NaN values computed correctly
        assert not pd.isna(percentiles.iloc[2])
    
    def test_all_nan_returns_nan(self) -> None:
        """All NaN input returns all NaN output."""
        scorer = Scorer(window=5)
        raw_scores = pd.Series([np.nan, np.nan, np.nan])
        
        percentiles = scorer.compute_percentile_scores(raw_scores)
        
        assert all(pd.isna(percentiles))


class TestInterpretationBands:
    """Test interpretation band assignment."""
    
    def test_normal_band(self) -> None:
        """0-30 → Normal."""
        scorer = Scorer()
        assert scorer.get_interpretation(0.0) == InterpretationBand.NORMAL
        assert scorer.get_interpretation(15.0) == InterpretationBand.NORMAL
        assert scorer.get_interpretation(29.9) == InterpretationBand.NORMAL
    
    def test_elevated_band(self) -> None:
        """30-60 → Elevated."""
        scorer = Scorer()
        assert scorer.get_interpretation(30.0) == InterpretationBand.ELEVATED
        assert scorer.get_interpretation(45.0) == InterpretationBand.ELEVATED
        assert scorer.get_interpretation(59.9) == InterpretationBand.ELEVATED
    
    def test_unusual_band(self) -> None:
        """60-80 → Unusual."""
        scorer = Scorer()
        assert scorer.get_interpretation(60.0) == InterpretationBand.UNUSUAL
        assert scorer.get_interpretation(70.0) == InterpretationBand.UNUSUAL
        assert scorer.get_interpretation(79.9) == InterpretationBand.UNUSUAL
    
    def test_extreme_band(self) -> None:
        """80-100 → Extreme."""
        scorer = Scorer()
        assert scorer.get_interpretation(80.0) == InterpretationBand.EXTREME
        assert scorer.get_interpretation(90.0) == InterpretationBand.EXTREME
        assert scorer.get_interpretation(100.0) == InterpretationBand.EXTREME
    
    def test_nan_defaults_to_normal(self) -> None:
        """NaN percentile defaults to Normal."""
        scorer = Scorer()
        assert scorer.get_interpretation(np.nan) == InterpretationBand.NORMAL


class TestFullScoring:
    """Test complete scoring pipeline."""
    
    def test_compute_score_basic(self) -> None:
        """Basic full scoring."""
        scorer = Scorer(window=5)
        z_scores = {"gex": 2.0, "dark_share": 1.5}
        history = pd.Series([0.5, 0.6, 0.7, 0.8, 0.9])

        result = scorer.compute_score(z_scores, historical_raw_scores=history)

        # Raw score should be computed
        assert result.raw_score > 0

        # Percentile should be high (current score 0.875 > all history values)
        # Extended history has 6 values, current is highest → 80-100%
        assert result.percentile_score >= 80.0

        # Should be Extreme band (>80)
        assert result.interpretation == InterpretationBand.EXTREME

        # Should have contributions
        assert "gex" in result.feature_contributions
        assert "dark_share" in result.feature_contributions
    
    def test_compute_score_with_exclusions(self) -> None:
        """Score with excluded features."""
        scorer = Scorer()
        z_scores = {"gex": 2.0, "dark_share": 1.5, "vanna": 0.5}
        
        result = scorer.compute_score(
            z_scores,
            excluded_features=["vanna"]
        )
        
        # Vanna should be in excluded list
        assert "vanna" in result.excluded_features
        
        # Vanna should NOT be in contributions
        assert "vanna" not in result.feature_contributions
    
    def test_compute_score_without_history(self) -> None:
        """Score without historical data returns NaN percentile."""
        scorer = Scorer()
        z_scores = {"gex": 2.0}
        
        result = scorer.compute_score(z_scores)
        
        # Raw score computed
        assert result.raw_score > 0
        
        # Percentile is NaN
        assert pd.isna(result.percentile_score)


class TestTopContributors:
    """Test top contributor ranking."""
    
    def test_get_top_contributors(self) -> None:
        """Returns top N contributors sorted."""
        scorer = Scorer()
        contributions = {
            "gex": 0.625,
            "dark_share": 0.45,
            "iv_rank": 0.075,
            "block_intensity": 0.10,
        }
        
        top_2 = scorer.get_top_contributors(contributions, top_n=2)
        
        assert len(top_2) == 2
        assert top_2[0] == ("gex", 0.625)
        assert top_2[1] == ("dark_share", 0.45)
    
    def test_top_contributors_full_list(self) -> None:
        """Can request all contributors."""
        scorer = Scorer()
        contributions = {"gex": 0.5, "dark_share": 0.3}
        
        top_all = scorer.get_top_contributors(contributions, top_n=10)
        
        # Returns all 2 even though requested 10
        assert len(top_all) == 2


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_z_scores(self) -> None:
        """Empty z_scores dict returns zero score."""
        scorer = Scorer()
        raw_score, contributions = scorer.compute_raw_score({})
        
        assert raw_score == 0.0
        assert contributions == {}
    
    def test_all_features_excluded(self) -> None:
        """All features excluded returns zero score."""
        scorer = Scorer()
        z_scores = {"gex": 2.0, "dark_share": 1.5}
        
        raw_score, contributions = scorer.compute_raw_score(
            z_scores,
            excluded_features=["gex", "dark_share"]
        )
        
        assert raw_score == 0.0
        assert contributions == {}
    
    def test_preserves_index(self) -> None:
        """Percentile scores preserve input index."""
        scorer = Scorer(window=5)
        dates = pd.date_range("2024-01-01", periods=5)
        raw_scores = pd.Series([1.0, 1.5, 2.0, 1.2, 3.0], index=dates)
        
        percentiles = scorer.compute_percentile_scores(raw_scores)
        
        assert percentiles.index.equals(raw_scores.index)


class TestSpecCompliance:
    """Test compliance with spec requirements."""
    
    def test_window_63_default(self) -> None:
        """Default window is 63 per spec."""
        scorer = Scorer()
        assert scorer.window == 63
    
    def test_weights_not_renormalized_spec(self) -> None:
        """Weights NOT renormalized per spec Section 5.1."""
        scorer = Scorer()
        
        # With all features (z=1), score = sum of weights = 1.0
        all_features = {k: 1.0 for k in FEATURE_WEIGHTS.keys()}
        raw_all, _ = scorer.compute_raw_score(all_features)
        assert raw_all == pytest.approx(1.0)
        
        # With only one feature (z=1), score = that feature's weight
        one_feature = {"gex": 1.0}
        raw_one, _ = scorer.compute_raw_score(one_feature)
        assert raw_one == pytest.approx(0.25)  # GEX weight, NOT renormalized to 1.0
    
    def test_percentile_range_0_to_100(self) -> None:
        """Percentile scores are in [0, 100] per spec."""
        scorer = Scorer(window=5)
        raw_scores = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        
        percentiles = scorer.compute_percentile_scores(raw_scores)
        
        # Check all values in valid range
        assert all((percentiles >= 0) & (percentiles <= 100))
