"""Tests for Baseline system: rolling stats, z-scores, state tracking."""

import numpy as np
import pandas as pd
import pytest

from obsidian.engine.baseline import Baseline, BaselineState, BaselineStats


class TestBaselineInit:
    """Test Baseline initialization and validation."""
    
    def test_default_initialization(self) -> None:
        """Default params match spec."""
        baseline = Baseline()
        assert baseline.window == 63
        assert baseline.min_periods == 21
        assert baseline.drift_threshold == 0.10
    
    def test_custom_initialization(self) -> None:
        """Can customize parameters."""
        baseline = Baseline(window=100, min_periods=30, drift_threshold=0.15)
        assert baseline.window == 100
        assert baseline.min_periods == 30
        assert baseline.drift_threshold == 0.15
    
    def test_window_must_exceed_min_periods(self) -> None:
        """Window must be >= min_periods."""
        with pytest.raises(ValueError, match="Window.*must be >= min_periods"):
            Baseline(window=20, min_periods=30)
    
    def test_min_periods_must_be_at_least_two(self) -> None:
        """min_periods must be >= 2 for std."""
        with pytest.raises(ValueError, match="min_periods.*must be >= 2"):
            Baseline(window=10, min_periods=1)
    
    def test_drift_threshold_validation(self) -> None:
        """Drift threshold must be in (0, 1]."""
        with pytest.raises(ValueError, match="drift_threshold.*must be in"):
            Baseline(drift_threshold=0)
        
        with pytest.raises(ValueError, match="drift_threshold.*must be in"):
            Baseline(drift_threshold=1.5)


class TestBaselineStats:
    """Test BaselineStats dataclass."""
    
    def test_valid_stats(self) -> None:
        """Valid stats with all fields."""
        stats = BaselineStats(
            mean=1.5,
            std=0.2,
            median=1.4,
            n_valid=25,
            is_valid=True
        )
        assert stats.mean == 1.5
        assert stats.std == 0.2
        assert stats.median == 1.4
        assert stats.n_valid == 25
        assert stats.is_valid is True
    
    def test_nan_stats_force_invalid(self) -> None:
        """NaN mean/std automatically sets is_valid=False."""
        stats = BaselineStats(
            mean=np.nan,
            std=np.nan,
            median=np.nan,
            n_valid=10,
            is_valid=True  # Will be overridden
        )
        assert stats.is_valid is False


class TestRollingStatistics:
    """Test rolling statistics computation."""
    
    def test_basic_statistics(self) -> None:
        """Basic stats with sufficient data."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        
        stats = baseline.compute_statistics(data, use_expanding=False)
        
        # Last point: rolling window of [1,2,3,4,5]
        last_stats = stats.iloc[-1]
        assert last_stats.mean == pytest.approx(3.0)
        assert last_stats.std == pytest.approx(np.std([1,2,3,4,5], ddof=1))
        assert last_stats.median == pytest.approx(3.0)
        assert last_stats.n_valid == 5
        assert last_stats.is_valid is True
    
    def test_rolling_window_moves(self) -> None:
        """Rolling window excludes old data."""
        baseline = Baseline(window=3, min_periods=2)
        data = pd.Series([1.0, 2.0, 3.0, 10.0])  # Last point very different
        
        stats = baseline.compute_statistics(data, use_expanding=False)
        
        # At t=3 (last point), window is [3.0, 10.0] (only last 3: [2,3,10])
        last_stats = stats.iloc[-1]
        # Actually at i=3 (0-indexed), window is data[1:4] = [2.0, 3.0, 10.0]
        assert last_stats.mean == pytest.approx(5.0)  # (2+3+10)/3
        assert last_stats.n_valid == 3
    
    def test_insufficient_data_returns_nan(self) -> None:
        """Returns NaN when n_valid < min_periods."""
        baseline = Baseline(window=10, min_periods=5)
        data = pd.Series([1.0, 2.0, 3.0])  # Only 3 points
        
        stats = baseline.compute_statistics(data, use_expanding=False)
        
        # All stats should be invalid
        for s in stats:
            assert pd.isna(s.mean)
            assert pd.isna(s.std)
            assert s.is_valid is False


class TestExpandingWindow:
    """Test expanding window for cold start."""
    
    def test_expanding_window_grows(self) -> None:
        """Expanding window uses all data from start."""
        baseline = Baseline(window=5, min_periods=2)
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        
        stats = baseline.compute_statistics(data, use_expanding=True)
        
        # At t=2 (i=2), expanding window is [1, 2, 3]
        assert stats.iloc[2].n_valid == 3
        assert stats.iloc[2].mean == pytest.approx(2.0)
        
        # At t=4 (i=4), expanding window is [1, 2, 3, 4, 5]
        assert stats.iloc[4].n_valid == 5
        assert stats.iloc[4].mean == pytest.approx(3.0)
        
        # At t=5 (i=5), transition to rolling window [2,3,4,5,6]
        assert stats.iloc[5].n_valid == 5
        assert stats.iloc[5].mean == pytest.approx(4.0)
    
    def test_first_valid_at_min_periods(self) -> None:
        """First valid stats at t = min_periods."""
        baseline = Baseline(window=10, min_periods=5)
        data = pd.Series(range(1, 11))  # [1, 2, ..., 10]
        
        stats = baseline.compute_statistics(data, use_expanding=True)
        
        # Invalid before t=5
        assert stats.iloc[3].is_valid is False  # t=4, n=4 < 5
        
        # Valid at t=5
        assert stats.iloc[4].is_valid is True   # t=5, n=5 >= 5
        assert stats.iloc[4].n_valid == 5


class TestZScoreComputation:
    """Test z-score normalization."""
    
    def test_basic_z_scores(self) -> None:
        """Basic z-score calculation."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        
        z_scores = baseline.compute_z_scores(data, use_expanding=False)
        
        # Last z-score: (5 - mean([1,2,3,4,5])) / std([1,2,3,4,5])
        # = (5 - 3) / std = 2 / 1.58... ≈ 1.26
        assert z_scores.iloc[-1] == pytest.approx(
            (5 - 3) / np.std([1,2,3,4,5], ddof=1), abs=0.01
        )
    
    def test_z_scores_with_expanding_window(self) -> None:
        """Z-scores use expanding window for cold start."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        
        z_scores = baseline.compute_z_scores(data, use_expanding=True)
        
        # At t=3 (i=2), expanding window [1,2,3]
        # z = (3 - 2) / std([1,2,3]) = 1 / 1.0 = 1.0
        assert z_scores.iloc[2] == pytest.approx(1.0)
    
    def test_nan_input_produces_nan_output(self) -> None:
        """NaN input values produce NaN z-scores."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([1.0, 2.0, None, 4.0, 5.0])
        
        z_scores = baseline.compute_z_scores(data)
        
        assert pd.isna(z_scores.iloc[2])
    
    def test_constant_values_produce_nan(self) -> None:
        """Constant values (std=0) produce NaN z-scores."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0])
        
        z_scores = baseline.compute_z_scores(data)
        
        # All z-scores should be NaN (division by zero)
        assert all(pd.isna(z_scores))
    
    def test_insufficient_data_produces_nan(self) -> None:
        """Z-scores are NaN when n_valid < min_periods."""
        baseline = Baseline(window=10, min_periods=5)
        data = pd.Series([1.0, 2.0, 3.0])
        
        z_scores = baseline.compute_z_scores(data)
        
        assert all(pd.isna(z_scores))


class TestBaselineStates:
    """Test baseline state determination."""
    
    def test_complete_state(self) -> None:
        """COMPLETE when all features have n >= min_periods."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 25, "dark_share": 30, "iv_rank": 22}
        
        state = baseline.get_state(counts)
        assert state == BaselineState.COMPLETE
    
    def test_partial_state(self) -> None:
        """PARTIAL when some features valid, some invalid."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 25, "vanna": 15, "charm": 10}
        
        state = baseline.get_state(counts)
        assert state == BaselineState.PARTIAL
    
    def test_empty_state(self) -> None:
        """EMPTY when all features have n < min_periods."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 10, "vanna": 15, "charm": 5}
        
        state = baseline.get_state(counts)
        assert state == BaselineState.EMPTY
    
    def test_empty_dict(self) -> None:
        """Empty dict returns EMPTY state."""
        baseline = Baseline(min_periods=21)
        state = baseline.get_state({})
        assert state == BaselineState.EMPTY
    
    def test_single_valid_feature_is_partial(self) -> None:
        """Single valid feature with invalid ones is PARTIAL."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 25, "vanna": 10}
        
        state = baseline.get_state(counts)
        assert state == BaselineState.PARTIAL


class TestDriftDetection:
    """Test baseline drift detection."""
    
    def test_no_drift_under_threshold(self) -> None:
        """No drift when change < threshold."""
        baseline = Baseline(drift_threshold=0.10)
        
        # 5% change
        assert baseline.detect_drift(1.05, 1.0) is False
        
        # 9% change
        assert baseline.detect_drift(1.09, 1.0) is False
    
    def test_drift_over_threshold(self) -> None:
        """Drift detected when change > threshold."""
        baseline = Baseline(drift_threshold=0.10)
        
        # 10.1% change
        assert baseline.detect_drift(1.101, 1.0) is True
        
        # 20% change
        assert baseline.detect_drift(1.2, 1.0) is True
    
    def test_drift_works_both_directions(self) -> None:
        """Drift detected for both increases and decreases."""
        baseline = Baseline(drift_threshold=0.10)
        
        # Increase
        assert baseline.detect_drift(1.2, 1.0) is True
        
        # Decrease
        assert baseline.detect_drift(0.8, 1.0) is True
    
    def test_nan_means_no_drift(self) -> None:
        """NaN values return False (no drift)."""
        baseline = Baseline(drift_threshold=0.10)
        
        assert baseline.detect_drift(np.nan, 1.0) is False
        assert baseline.detect_drift(1.0, np.nan) is False
        assert baseline.detect_drift(np.nan, np.nan) is False
    
    def test_zero_previous_mean(self) -> None:
        """Zero previous mean: drift if current != 0."""
        baseline = Baseline(drift_threshold=0.10)
        
        assert baseline.detect_drift(0.0, 0.0) is False
        assert baseline.detect_drift(1.0, 0.0) is True
        assert baseline.detect_drift(-1.0, 0.0) is True


class TestExcludedFeatures:
    """Test excluded feature tracking."""
    
    def test_get_excluded_features(self) -> None:
        """Returns features below min_periods."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 25, "vanna": 15, "charm": 10, "dark_share": 30}
        
        excluded = baseline.get_excluded_features(counts)
        
        assert len(excluded) == 2
        assert ("charm", 10) in excluded
        assert ("vanna", 15) in excluded
    
    def test_excluded_sorted_by_count(self) -> None:
        """Excluded features sorted by count ascending."""
        baseline = Baseline(min_periods=21)
        counts = {"vanna": 15, "charm": 10}
        
        excluded = baseline.get_excluded_features(counts)
        
        assert excluded == [("charm", 10), ("vanna", 15)]
    
    def test_no_excluded_when_all_valid(self) -> None:
        """Empty list when all features valid."""
        baseline = Baseline(min_periods=21)
        counts = {"gex": 25, "dark_share": 30}
        
        excluded = baseline.get_excluded_features(counts)
        
        assert excluded == []


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_all_nan_input(self) -> None:
        """All NaN input produces all NaN output."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan])
        
        z_scores = baseline.compute_z_scores(data)
        
        assert all(pd.isna(z_scores))
    
    def test_partial_nan_handling(self) -> None:
        """Partial NaN values handled correctly."""
        baseline = Baseline(window=5, min_periods=3)
        data = pd.Series([1.0, np.nan, 3.0, np.nan, 5.0])
        
        stats = baseline.compute_statistics(data)
        
        # At t=4 (last point), window has [1, NaN, 3, NaN, 5]
        # n_valid = 3 (only non-NaN)
        last_stats = stats.iloc[-1]
        assert last_stats.n_valid == 3
        assert last_stats.mean == pytest.approx(3.0)  # (1+3+5)/3
    
    def test_single_value(self) -> None:
        """Single value with min_periods=1 works."""
        baseline = Baseline(window=5, min_periods=2)
        data = pd.Series([5.0])
        
        stats = baseline.compute_statistics(data)
        
        # Only 1 value, need 2 for valid stats
        assert stats.iloc[0].is_valid is False
    
    def test_very_large_window(self) -> None:
        """Handles very large window size."""
        baseline = Baseline(window=1000, min_periods=100)
        data = pd.Series(range(150))
        
        z_scores = baseline.compute_z_scores(data)
        
        # Should have valid z-scores after t=100
        assert not pd.isna(z_scores.iloc[100])
    
    def test_preserves_index(self) -> None:
        """Output preserves input Series index."""
        baseline = Baseline(window=5, min_periods=3)
        dates = pd.date_range("2024-01-01", periods=10)
        data = pd.Series(range(10), index=dates)
        
        z_scores = baseline.compute_z_scores(data)
        
        assert z_scores.index.equals(data.index)


class TestSpecCompliance:
    """Test compliance with spec requirements."""
    
    def test_window_63_min_21(self) -> None:
        """Default params match spec (W=63, N_min=21)."""
        baseline = Baseline()
        
        assert baseline.window == 63
        assert baseline.min_periods == 21
    
    def test_first_valid_z_score_at_21(self) -> None:
        """First valid z-score at t=21 per spec."""
        baseline = Baseline(window=63, min_periods=21)
        data = pd.Series(range(1, 101))  # 100 days
        
        z_scores = baseline.compute_z_scores(data, use_expanding=True)
        
        # Invalid before t=21
        assert all(pd.isna(z_scores.iloc[:20]))
        
        # Valid at t=21 (index 20)
        assert not pd.isna(z_scores.iloc[20])
    
    def test_expanding_window_until_63(self) -> None:
        """Expanding window for t ≤ 63, then rolling."""
        baseline = Baseline(window=63, min_periods=21)
        data = pd.Series(range(1, 101))
        
        stats = baseline.compute_statistics(data, use_expanding=True)
        
        # At t=50, n_valid should be 50 (expanding)
        assert stats.iloc[49].n_valid == 50
        
        # At t=65, n_valid should be 63 (rolling)
        assert stats.iloc[64].n_valid == 63
    
    def test_drift_threshold_10_percent(self) -> None:
        """Default drift threshold is 10% per spec."""
        baseline = Baseline()
        
        assert baseline.drift_threshold == 0.10
