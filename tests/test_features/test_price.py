"""Tests for price-based features: Efficiency and Impact."""

import numpy as np
import pandas as pd
import pytest

from obsidian.features.price import compute_efficiency, compute_impact


class TestEfficiency:
    """Test Price Efficiency computation."""

    def test_basic_efficiency(self) -> None:
        """Basic efficiency calculation."""
        data = pd.DataFrame({
            "high": [152.0, 153.5, 151.8],
            "low": [150.0, 151.0, 150.2],
            "volume": [1000000, 1500000, 1200000]
        })
        efficiency = compute_efficiency(data)

        assert len(efficiency) == 3
        assert efficiency[0] == pytest.approx(2.0 / 1000000)  # (152-150) / 1M
        assert efficiency[1] == pytest.approx(2.5 / 1500000)  # (153.5-151) / 1.5M

    def test_nan_on_zero_volume(self) -> None:
        """Returns NaN when volume is zero."""
        data = pd.DataFrame({
            "high": [152.0],
            "low": [150.0],
            "volume": [0]
        })
        efficiency = compute_efficiency(data)
        assert pd.isna(efficiency[0])

    def test_nan_on_missing_data(self) -> None:
        """Returns NaN when input data has NaN."""
        data = pd.DataFrame({
            "high": [152.0, None, 151.8],
            "low": [150.0, 151.0, None],
            "volume": [1000000, 1500000, 1200000]
        })
        efficiency = compute_efficiency(data)
        assert pd.isna(efficiency[1])
        assert pd.isna(efficiency[2])

    def test_missing_column_raises(self) -> None:
        """Raises ValueError if required column missing."""
        data = pd.DataFrame({"high": [152.0], "low": [150.0]})
        with pytest.raises(ValueError, match="Missing required column: volume"):
            compute_efficiency(data)


class TestImpact:
    """Test Price Impact computation."""

    def test_basic_impact(self) -> None:
        """Basic impact calculation."""
        data = pd.DataFrame({
            "close": [151.5, 152.8, 150.2],
            "open": [150.0, 151.0, 151.5],
            "volume": [1000000, 1500000, 1200000]
        })
        impact = compute_impact(data)

        assert len(impact) == 3
        assert impact[0] == pytest.approx(1.5 / 1000000)  # |151.5-150| / 1M
        assert impact[1] == pytest.approx(1.8 / 1500000)  # |152.8-151| / 1.5M
        assert impact[2] == pytest.approx(1.3 / 1200000)  # |150.2-151.5| / 1.2M

    def test_absolute_value(self) -> None:
        """Impact uses absolute value of price move."""
        data = pd.DataFrame({
            "close": [148.0],  # Down move
            "open": [150.0],
            "volume": [1000000]
        })
        impact = compute_impact(data)
        assert impact[0] == pytest.approx(2.0 / 1000000)  # Absolute value

    def test_nan_on_zero_volume(self) -> None:
        """Returns NaN when volume is zero."""
        data = pd.DataFrame({
            "close": [151.5],
            "open": [150.0],
            "volume": [0]
        })
        impact = compute_impact(data)
        assert pd.isna(impact[0])

    def test_nan_on_missing_data(self) -> None:
        """Returns NaN when input data has NaN."""
        data = pd.DataFrame({
            "close": [151.5, None, 150.2],
            "open": [150.0, 151.0, None],
            "volume": [1000000, 1500000, 1200000]
        })
        impact = compute_impact(data)
        assert pd.isna(impact[1])
        assert pd.isna(impact[2])

    def test_missing_column_raises(self) -> None:
        """Raises ValueError if required column missing."""
        data = pd.DataFrame({"close": [151.5], "open": [150.0]})
        with pytest.raises(ValueError, match="Missing required column: volume"):
            compute_impact(data)


class TestEdgeCases:
    """Test edge cases for both features."""

    def test_zero_range_zero_efficiency(self) -> None:
        """Zero range (high == low) gives zero efficiency."""
        data = pd.DataFrame({
            "high": [150.0],
            "low": [150.0],  # No range
            "volume": [1000000]
        })
        efficiency = compute_efficiency(data)
        assert efficiency[0] == 0.0

    def test_zero_move_zero_impact(self) -> None:
        """Zero move (close == open) gives zero impact."""
        data = pd.DataFrame({
            "close": [150.0],
            "open": [150.0],  # No move
            "volume": [1000000]
        })
        impact = compute_impact(data)
        assert impact[0] == 0.0

    def test_very_large_volume(self) -> None:
        """Handles very large volume values."""
        data = pd.DataFrame({
            "high": [152.0],
            "low": [150.0],
            "close": [151.5],
            "open": [150.0],
            "volume": [1e9]  # 1 billion shares
        })
        efficiency = compute_efficiency(data)
        impact = compute_impact(data)

        assert efficiency[0] == pytest.approx(2.0 / 1e9)
        assert impact[0] == pytest.approx(1.5 / 1e9)

    def test_preserves_index(self) -> None:
        """Output preserves input DataFrame index."""
        data = pd.DataFrame({
            "high": [152.0, 153.5],
            "low": [150.0, 151.0],
            "close": [151.5, 152.8],
            "open": [150.0, 151.0],
            "volume": [1000000, 1500000]
        }, index=pd.date_range("2024-01-15", periods=2))

        efficiency = compute_efficiency(data)
        impact = compute_impact(data)

        assert efficiency.index.equals(data.index)
        assert impact.index.equals(data.index)
