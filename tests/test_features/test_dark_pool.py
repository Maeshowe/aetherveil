"""Tests for dark pool features: DarkShare and Block Intensity."""

import numpy as np
import pandas as pd
import pytest
import warnings

from obsidian.features.dark_pool import compute_dark_share, compute_block_intensity


class TestDarkShare:
    """Test DarkShare computation."""

    def test_basic_dark_share(self) -> None:
        """Basic dark share calculation."""
        data = pd.DataFrame({
            "dark_volume": [500000, 750000, 600000],
            "total_volume": [1000000, 1500000, 1200000]
        })
        dark_share = compute_dark_share(data)

        assert len(dark_share) == 3
        assert dark_share[0] == pytest.approx(0.5)
        assert dark_share[1] == pytest.approx(0.5)
        assert dark_share[2] == pytest.approx(0.5)

    def test_uses_volume_as_total(self) -> None:
        """Can use 'volume' column as total_volume."""
        data = pd.DataFrame({
            "dark_volume": [500000],
            "volume": [1000000]  # No total_volume column
        })
        dark_share = compute_dark_share(data)
        assert dark_share[0] == pytest.approx(0.5)

    def test_domain_valid(self) -> None:
        """Dark share should be in [0, 1]."""
        data = pd.DataFrame({
            "dark_volume": [0, 500000, 1000000],
            "total_volume": [1000000, 1000000, 1000000]
        })
        dark_share = compute_dark_share(data)

        assert dark_share[0] == pytest.approx(0.0)
        assert dark_share[1] == pytest.approx(0.5)
        assert dark_share[2] == pytest.approx(1.0)

    def test_warns_on_invalid_domain(self) -> None:
        """Warns when dark_share > 1.0 (data error)."""
        data = pd.DataFrame({
            "dark_volume": [1200000],  # More than total!
            "total_volume": [1000000]
        })
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dark_share = compute_dark_share(data)
            assert len(w) == 1
            assert "DarkShare > 1.0" in str(w[0].message)

    def test_nan_on_zero_volume(self) -> None:
        """Returns NaN when total volume is zero."""
        data = pd.DataFrame({
            "dark_volume": [500000],
            "total_volume": [0]
        })
        dark_share = compute_dark_share(data)
        assert pd.isna(dark_share[0])

    def test_nan_on_missing_data(self) -> None:
        """Returns NaN when input data has NaN."""
        data = pd.DataFrame({
            "dark_volume": [500000, None, 600000],
            "total_volume": [1000000, 1500000, None]
        })
        dark_share = compute_dark_share(data)
        assert pd.isna(dark_share[1])
        assert pd.isna(dark_share[2])

    def test_missing_column_raises(self) -> None:
        """Raises ValueError if required columns missing."""
        data = pd.DataFrame({"dark_volume": [500000]})
        with pytest.raises(ValueError, match="Missing total volume column"):
            compute_dark_share(data)

        data = pd.DataFrame({"total_volume": [1000000]})
        with pytest.raises(ValueError, match="Missing dark volume column"):
            compute_dark_share(data)


class TestBlockIntensity:
    """Test Block Intensity computation."""

    def test_count_method(self) -> None:
        """Block intensity using count method."""
        data = pd.DataFrame({
            "block_count": [15, 22, 18]
        })
        intensity = compute_block_intensity(data, method="count")

        assert len(intensity) == 3
        assert intensity[0] == 15
        assert intensity[1] == 22
        assert intensity[2] == 18

    def test_volume_method(self) -> None:
        """Block intensity using volume method."""
        data = pd.DataFrame({
            "block_volume": [500000, 750000, 600000]
        })
        intensity = compute_block_intensity(data, method="volume")

        assert len(intensity) == 3
        assert intensity[0] == 500000
        assert intensity[1] == 750000
        assert intensity[2] == 600000

    def test_invalid_method_raises(self) -> None:
        """Raises on invalid method."""
        data = pd.DataFrame({"block_count": [15]})
        with pytest.raises(ValueError, match="Invalid method"):
            compute_block_intensity(data, method="invalid")

    def test_missing_column_raises(self) -> None:
        """Raises if required column missing."""
        data = pd.DataFrame({"volume": [1000000]})
        with pytest.raises(ValueError, match="Missing block count column"):
            compute_block_intensity(data, method="count")

        with pytest.raises(ValueError, match="Missing block volume column"):
            compute_block_intensity(data, method="volume")


class TestEdgeCases:
    """Test edge cases for dark pool features."""

    def test_all_dark_volume(self) -> None:
        """Dark share = 1.0 when all volume is dark."""
        data = pd.DataFrame({
            "dark_volume": [1000000],
            "total_volume": [1000000]
        })
        dark_share = compute_dark_share(data)
        assert dark_share[0] == pytest.approx(1.0)

    def test_no_dark_volume(self) -> None:
        """Dark share = 0.0 when no dark volume."""
        data = pd.DataFrame({
            "dark_volume": [0],
            "total_volume": [1000000]
        })
        dark_share = compute_dark_share(data)
        assert dark_share[0] == pytest.approx(0.0)

    def test_zero_block_count(self) -> None:
        """Block count can be zero."""
        data = pd.DataFrame({
            "block_count": [0, 5, 0]
        })
        intensity = compute_block_intensity(data, method="count")
        assert intensity[0] == 0
        assert intensity[1] == 5
        assert intensity[2] == 0
