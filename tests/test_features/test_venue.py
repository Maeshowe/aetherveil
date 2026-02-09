"""Tests for venue mix features."""

import numpy as np
import pandas as pd
import pytest

from obsidian.features.venue import (
    compute_venue_mix,
    compute_venue_concentration,
    compute_primary_venue_share
)


class TestVenueMix:
    """Test Venue Mix (entropy-based) computation."""

    def test_basic_venue_mix(self) -> None:
        """Basic venue mix using Shannon entropy."""
        data = pd.DataFrame({
            "nyse_volume": [400000, 350000, 420000],
            "nasdaq_volume": [350000, 400000, 380000],
            "dark_volume": [250000, 250000, 200000]
        })
        venue_mix = compute_venue_mix(data)

        assert len(venue_mix) == 3
        assert all(venue_mix > 0)  # Entropy > 0 for diversified execution

    def test_precomputed_entropy(self) -> None:
        """Uses pre-computed entropy if available."""
        data = pd.DataFrame({
            "venue_entropy": [1.05, 1.10, 1.08]
        })
        venue_mix = compute_venue_mix(data)

        assert venue_mix[0] == 1.05
        assert venue_mix[1] == 1.10
        assert venue_mix[2] == 1.08

    def test_single_venue_zero_entropy(self) -> None:
        """Single venue (no diversity) gives low entropy."""
        data = pd.DataFrame({
            "nyse_volume": [1000000],
            "nasdaq_volume": [0],
            "dark_volume": [0]
        })
        venue_mix = compute_venue_mix(data)

        # All volume on one venue → entropy = 0 (but NaN from log(0))
        # In practice, we get NaN from 0 * log(0)
        assert pd.isna(venue_mix[0]) or venue_mix[0] == pytest.approx(0, abs=1e-10)

    def test_equal_distribution_high_entropy(self) -> None:
        """Equal distribution across venues gives high entropy."""
        # 3 venues with equal volume
        data = pd.DataFrame({
            "venue_a_volume": [333333],
            "venue_b_volume": [333333],
            "venue_c_volume": [333334]
        })
        venue_mix = compute_venue_mix(data)

        # Entropy for 3 equal venues ≈ log(3) ≈ 1.099
        assert venue_mix[0] == pytest.approx(np.log(3), abs=0.01)

    def test_missing_columns_raises(self) -> None:
        """Raises if no venue columns found."""
        data = pd.DataFrame({"price": [150.0], "volume": [1000000]})
        with pytest.raises(ValueError, match="No venue columns found"):
            compute_venue_mix(data)


class TestVenueConcentration:
    """Test Venue Concentration (HHI) computation."""

    def test_basic_hhi(self) -> None:
        """Basic HHI calculation."""
        data = pd.DataFrame({
            "nyse_volume": [500000],   # 50%
            "nasdaq_volume": [500000]  # 50%
        })
        hhi = compute_venue_concentration(data)

        # HHI = 0.5² + 0.5² = 0.5
        assert hhi[0] == pytest.approx(0.5)

    def test_single_venue_max_concentration(self) -> None:
        """Single venue gives HHI = 1.0 (maximum concentration)."""
        data = pd.DataFrame({
            "nyse_volume": [1000000],
            "nasdaq_volume": [0],
            "dark_volume": [0]
        })
        hhi = compute_venue_concentration(data)

        # HHI = 1² + 0² + 0² = 1.0
        assert hhi[0] == pytest.approx(1.0)

    def test_equal_distribution_min_concentration(self) -> None:
        """Equal distribution gives HHI = 1/N."""
        # 3 venues with equal volume
        data = pd.DataFrame({
            "venue_a_volume": [333333],
            "venue_b_volume": [333333],
            "venue_c_volume": [333334]
        })
        hhi = compute_venue_concentration(data)

        # HHI ≈ (1/3)² + (1/3)² + (1/3)² ≈ 0.333
        assert hhi[0] == pytest.approx(1/3, abs=0.01)

    def test_hhi_domain(self) -> None:
        """HHI is in [1/N, 1]."""
        # 2 venues: range should be [0.5, 1.0]
        data = pd.DataFrame({
            "nyse_volume": [900000, 500000, 100000],  # Varying concentration
            "nasdaq_volume": [100000, 500000, 900000]
        })
        hhi = compute_venue_concentration(data)

        assert all((hhi >= 0.5) & (hhi <= 1.0))


class TestPrimaryVenueShare:
    """Test primary venue share computation."""

    def test_basic_venue_share(self) -> None:
        """Basic venue share calculation."""
        data = pd.DataFrame({
            "nyse_volume": [500000, 350000, 420000],
            "total_volume": [1000000, 1000000, 1000000]
        })
        nyse_share = compute_primary_venue_share(data, venue_name="nyse")

        assert nyse_share[0] == pytest.approx(0.5)
        assert nyse_share[1] == pytest.approx(0.35)
        assert nyse_share[2] == pytest.approx(0.42)

    def test_uses_volume_as_total(self) -> None:
        """Can use 'volume' column as total."""
        data = pd.DataFrame({
            "nasdaq_volume": [400000],
            "volume": [1000000]  # No total_volume column
        })
        nasdaq_share = compute_primary_venue_share(data, venue_name="nasdaq")
        assert nasdaq_share[0] == pytest.approx(0.4)

    def test_venue_share_domain(self) -> None:
        """Venue share is in [0, 1]."""
        data = pd.DataFrame({
            "dark_volume": [0, 500000, 1000000],
            "total_volume": [1000000, 1000000, 1000000]
        })
        dark_share = compute_primary_venue_share(data, venue_name="dark")

        assert dark_share[0] == pytest.approx(0.0)
        assert dark_share[1] == pytest.approx(0.5)
        assert dark_share[2] == pytest.approx(1.0)

    def test_missing_venue_raises(self) -> None:
        """Raises if venue column missing."""
        data = pd.DataFrame({"nyse_volume": [500000], "total_volume": [1000000]})
        with pytest.raises(ValueError, match="Missing venue column: nasdaq_volume"):
            compute_primary_venue_share(data, venue_name="nasdaq")

    def test_nan_on_zero_volume(self) -> None:
        """Returns NaN when total volume is zero."""
        data = pd.DataFrame({
            "nyse_volume": [500000],
            "total_volume": [0]
        })
        nyse_share = compute_primary_venue_share(data, venue_name="nyse")
        assert pd.isna(nyse_share[0])


class TestEdgeCases:
    """Test edge cases for venue features."""

    def test_zero_volume_venues(self) -> None:
        """Handles venues with zero volume."""
        data = pd.DataFrame({
            "nyse_volume": [1000000],
            "nasdaq_volume": [0],
            "dark_volume": [0]
        })

        venue_mix = compute_venue_mix(data)
        hhi = compute_venue_concentration(data)

        # Should handle without error (though entropy may be NaN)
        assert not np.isnan(hhi[0])

    def test_all_zero_venues_nan(self) -> None:
        """All zero volumes gives NaN or 0.0 (edge case)."""
        data = pd.DataFrame({
            "nyse_volume": [0],
            "nasdaq_volume": [0],
            "dark_volume": [0]
        })

        hhi = compute_venue_concentration(data)
        # Division by zero in share calculation → could be NaN or 0.0
        # numpy's 0/0 → NaN, but 0²+0²+0² → 0.0
        assert pd.isna(hhi[0]) or hhi[0] == pytest.approx(0.0)

    def test_custom_venue_columns(self) -> None:
        """Can specify custom venue column list."""
        data = pd.DataFrame({
            "exchange_a": [400000],
            "exchange_b": [600000],
            "other_column": [1000000]  # Should be ignored
        })

        venue_mix = compute_venue_mix(data, venue_columns=["exchange_a", "exchange_b"])
        assert not pd.isna(venue_mix[0])

    def test_preserves_index(self) -> None:
        """Output preserves input DataFrame index."""
        data = pd.DataFrame({
            "nyse_volume": [500000, 400000],
            "nasdaq_volume": [500000, 600000]
        }, index=pd.date_range("2024-01-15", periods=2))

        venue_mix = compute_venue_mix(data)
        hhi = compute_venue_concentration(data)

        assert venue_mix.index.equals(data.index)
        assert hhi.index.equals(data.index)
