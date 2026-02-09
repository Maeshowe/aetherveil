"""Tests for volatility features: IV Skew and IV Rank."""

import numpy as np
import pandas as pd
import pytest

from obsidian.features.volatility import (
    compute_iv_skew,
    compute_iv_rank,
    compute_term_structure_slope
)


class TestIVSkew:
    """Test IV Skew computation."""

    def test_basic_skew(self) -> None:
        """Basic IV skew from put-call IV."""
        data = pd.DataFrame({
            "put_iv": [0.35, 0.42, 0.38],
            "call_iv": [0.30, 0.35, 0.32]
        })
        skew = compute_iv_skew(data)

        assert len(skew) == 3
        assert skew[0] == pytest.approx(0.05)  # Puts more expensive
        assert skew[1] == pytest.approx(0.07)
        assert skew[2] == pytest.approx(0.06)

    def test_precomputed_skew(self) -> None:
        """Uses pre-computed skew if available."""
        data = pd.DataFrame({
            "iv_skew": [0.05, 0.07, 0.06]
        })
        skew = compute_iv_skew(data)

        assert skew[0] == 0.05
        assert skew[1] == 0.07
        assert skew[2] == 0.06

    def test_negative_skew(self) -> None:
        """Skew can be negative (calls more expensive)."""
        data = pd.DataFrame({
            "put_iv": [0.30],
            "call_iv": [0.35]  # Calls more expensive (unusual)
        })
        skew = compute_iv_skew(data)
        assert skew[0] == pytest.approx(-0.05)

    def test_missing_column_raises(self) -> None:
        """Raises if required columns missing."""
        data = pd.DataFrame({"volume": [1000000]})
        with pytest.raises(ValueError, match="Missing IV skew data"):
            compute_iv_skew(data)


class TestIVRank:
    """Test IV Rank computation."""

    def test_basic_iv_rank(self) -> None:
        """Basic IV rank over window."""
        data = pd.DataFrame({
            "iv": [0.25, 0.30, 0.35, 0.28, 0.32]
        })
        iv_rank = compute_iv_rank(data, window=5)

        # Last value: (0.32 - 0.25) / (0.35 - 0.25) = 0.7
        assert iv_rank.iloc[-1] == pytest.approx(0.7)

    def test_iv_rank_domain(self) -> None:
        """IV rank is in [0, 1]."""
        data = pd.DataFrame({
            "iv": [0.20, 0.25, 0.30, 0.35, 0.40]
        })
        iv_rank = compute_iv_rank(data, window=5)

        # Min IV = 0.20, Max IV = 0.40
        # Last value: (0.40 - 0.20) / (0.40 - 0.20) = 1.0
        assert iv_rank.iloc[-1] == pytest.approx(1.0)

        # First value: (0.20 - 0.20) / (0.20 - 0.20) = NaN (min == max)
        assert pd.isna(iv_rank.iloc[0])

    def test_constant_iv_returns_nan(self) -> None:
        """Returns NaN when IV is constant (min == max)."""
        data = pd.DataFrame({
            "iv": [0.30, 0.30, 0.30]
        })
        iv_rank = compute_iv_rank(data, window=3)
        assert all(pd.isna(iv_rank))

    def test_missing_column_raises(self) -> None:
        """Raises if IV column missing."""
        data = pd.DataFrame({"volume": [1000000]})
        with pytest.raises(ValueError, match="Missing IV column"):
            compute_iv_rank(data)


class TestTermStructureSlope:
    """Test IV term structure slope."""

    def test_basic_slope(self) -> None:
        """Basic term structure slope."""
        data = pd.DataFrame({
            "iv_30d": [0.35, 0.42, 0.38],
            "iv_90d": [0.30, 0.35, 0.32]
        })
        slope = compute_term_structure_slope(data)

        assert len(slope) == 3
        assert slope[0] == pytest.approx(0.35 / 0.30)  # Backwardation
        assert slope[1] == pytest.approx(0.42 / 0.35)
        assert slope[2] == pytest.approx(0.38 / 0.32)

    def test_backwardation(self) -> None:
        """Slope > 1 indicates backwardation (near-term IV elevated)."""
        data = pd.DataFrame({
            "iv_30d": [0.40],  # High near-term IV
            "iv_90d": [0.30]   # Lower far-term IV
        })
        slope = compute_term_structure_slope(data)
        assert slope[0] > 1.0  # Backwardation

    def test_contango(self) -> None:
        """Slope < 1 indicates contango (far-term IV elevated)."""
        data = pd.DataFrame({
            "iv_30d": [0.30],  # Lower near-term IV
            "iv_90d": [0.40]   # High far-term IV
        })
        slope = compute_term_structure_slope(data)
        assert slope[0] < 1.0  # Contango

    def test_nan_on_zero_far_iv(self) -> None:
        """Returns NaN when far-term IV is zero."""
        data = pd.DataFrame({
            "iv_30d": [0.30],
            "iv_90d": [0]  # Division by zero
        })
        slope = compute_term_structure_slope(data)
        assert pd.isna(slope[0])

    def test_missing_column_raises(self) -> None:
        """Raises if term structure columns missing."""
        data = pd.DataFrame({"iv_30d": [0.30]})
        with pytest.raises(ValueError, match="Missing term structure data"):
            compute_term_structure_slope(data)


class TestEdgeCases:
    """Test edge cases for volatility features."""

    def test_nan_propagation(self) -> None:
        """NaN values in input propagate correctly."""
        data = pd.DataFrame({
            "put_iv": [0.35, None, 0.38],
            "call_iv": [0.30, 0.35, None]
        })
        skew = compute_iv_skew(data)

        assert pd.isna(skew[1])
        assert pd.isna(skew[2])

    def test_zero_iv_values(self) -> None:
        """Handles zero IV values."""
        data = pd.DataFrame({
            "put_iv": [0.0, 0.35],
            "call_iv": [0.0, 0.30]
        })
        skew = compute_iv_skew(data)

        assert skew[0] == 0.0
        assert skew[1] == pytest.approx(0.05)

    def test_very_small_iv_differences(self) -> None:
        """Handles very small IV differences."""
        data = pd.DataFrame({
            "put_iv": [0.30001],
            "call_iv": [0.30000]
        })
        skew = compute_iv_skew(data)
        assert skew[0] == pytest.approx(0.00001)
