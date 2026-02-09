"""Tests for Greeks features: GEX, DEX, Vanna, Charm."""

import numpy as np
import pandas as pd
import pytest

from obsidian.features.greeks import compute_gex, compute_dex, compute_vanna, compute_charm


class TestGEX:
    """Test Dealer Gamma Exposure (GEX)."""

    def test_basic_gex(self) -> None:
        """Basic GEX from direct column."""
        data = pd.DataFrame({
            "gex": [1500000, -800000, 2100000]
        })
        gex = compute_gex(data)

        assert len(gex) == 3
        assert gex[0] == 1500000  # Positive = stabilizing
        assert gex[1] == -800000  # Negative = destabilizing
        assert gex[2] == 2100000

    def test_gex_from_call_put_gamma(self) -> None:
        """GEX computed from call and put gamma."""
        data = pd.DataFrame({
            "call_gamma": [1000000, 500000, 1500000],
            "put_gamma": [500000, 800000, 600000]
        })
        gex = compute_gex(data)

        assert gex[0] == 500000   # 1M - 0.5M
        assert gex[1] == -300000  # 0.5M - 0.8M (negative!)
        assert gex[2] == 900000   # 1.5M - 0.6M

    def test_gex_sign_convention(self) -> None:
        """GEX sign convention is preserved."""
        data = pd.DataFrame({
            "gex": [1000000, -1000000, 0]
        })
        gex = compute_gex(data)

        # Positive = dealers long gamma = stabilizing
        assert gex[0] > 0
        # Negative = dealers short gamma = destabilizing
        assert gex[1] < 0
        # Zero = neutral
        assert gex[2] == 0

    def test_missing_column_raises(self) -> None:
        """Raises if GEX column missing."""
        data = pd.DataFrame({"volume": [1000000]})
        with pytest.raises(ValueError, match="Missing GEX column"):
            compute_gex(data)


class TestDEX:
    """Test Dealer Delta Exposure (DEX)."""

    def test_basic_dex(self) -> None:
        """Basic DEX from direct column."""
        data = pd.DataFrame({
            "dex": [-500000, 300000, -150000]
        })
        dex = compute_dex(data)

        assert len(dex) == 3
        assert dex[0] == -500000  # Sell pressure
        assert dex[1] == 300000   # Buy pressure
        assert dex[2] == -150000

    def test_dex_from_call_put_delta(self) -> None:
        """DEX computed from call and put delta."""
        data = pd.DataFrame({
            "call_delta": [400000, 600000, 500000],
            "put_delta": [500000, 400000, 500000]
        })
        dex = compute_dex(data)

        assert dex[0] == -100000  # 400K - 500K
        assert dex[1] == 200000   # 600K - 400K
        assert dex[2] == 0        # 500K - 500K

    def test_missing_column_raises(self) -> None:
        """Raises if DEX column missing."""
        data = pd.DataFrame({"volume": [1000000]})
        with pytest.raises(ValueError, match="Missing DEX column"):
            compute_dex(data)


class TestVanna:
    """Test Vanna exposure."""

    def test_basic_vanna(self) -> None:
        """Basic Vanna from direct column."""
        data = pd.DataFrame({
            "vanna": [15000, None, 18000]
        })
        vanna = compute_vanna(data)

        assert len(vanna) == 3
        assert vanna[0] == 15000
        assert pd.isna(vanna[1])  # NaN during cold start is acceptable
        assert vanna[2] == 18000

    def test_vanna_from_call_put(self) -> None:
        """Vanna computed from call and put vanna."""
        data = pd.DataFrame({
            "call_vanna": [10000, 12000, 11000],
            "put_vanna": [5000, 6000, 5500]
        })
        vanna = compute_vanna(data)

        assert vanna[0] == 5000  # 10K - 5K
        assert vanna[1] == 6000  # 12K - 6K
        assert vanna[2] == 5500  # 11K - 5.5K

    def test_returns_nan_when_missing(self) -> None:
        """Returns NaN series when Vanna not available."""
        data = pd.DataFrame({
            "gex": [1000000, 1200000, 1100000]  # No vanna column
        })
        vanna = compute_vanna(data)

        assert len(vanna) == 3
        assert all(pd.isna(vanna))


class TestCharm:
    """Test Charm exposure."""

    def test_basic_charm(self) -> None:
        """Basic Charm from direct column."""
        data = pd.DataFrame({
            "charm": [5000, None, 6500]
        })
        charm = compute_charm(data)

        assert len(charm) == 3
        assert charm[0] == 5000
        assert pd.isna(charm[1])  # NaN during cold start is acceptable
        assert charm[2] == 6500

    def test_charm_from_call_put(self) -> None:
        """Charm computed from call and put charm."""
        data = pd.DataFrame({
            "call_charm": [3000, 3500, 3200],
            "put_charm": [2000, 2200, 2100]
        })
        charm = compute_charm(data)

        assert charm[0] == 1000  # 3K - 2K
        assert charm[1] == 1300  # 3.5K - 2.2K
        assert charm[2] == 1100  # 3.2K - 2.1K

    def test_returns_nan_when_missing(self) -> None:
        """Returns NaN series when Charm not available."""
        data = pd.DataFrame({
            "gex": [1000000, 1200000, 1100000]  # No charm column
        })
        charm = compute_charm(data)

        assert len(charm) == 3
        assert all(pd.isna(charm))


class TestEdgeCases:
    """Test edge cases for Greeks features."""

    def test_zero_values(self) -> None:
        """All Greeks can be zero."""
        data = pd.DataFrame({
            "gex": [0],
            "dex": [0],
            "vanna": [0],
            "charm": [0]
        })

        assert compute_gex(data)[0] == 0
        assert compute_dex(data)[0] == 0
        assert compute_vanna(data)[0] == 0
        assert compute_charm(data)[0] == 0

    def test_very_large_values(self) -> None:
        """Handles very large exposure values."""
        data = pd.DataFrame({
            "gex": [1e9, -1e9],  # Billion-scale GEX
            "dex": [5e8, -5e8]
        })

        gex = compute_gex(data)
        dex = compute_dex(data)

        assert gex[0] == pytest.approx(1e9)
        assert gex[1] == pytest.approx(-1e9)
        assert dex[0] == pytest.approx(5e8)
        assert dex[1] == pytest.approx(-5e8)

    def test_preserves_nan(self) -> None:
        """NaN values in input are preserved."""
        data = pd.DataFrame({
            "gex": [1000000, None, 1200000],
            "dex": [None, 500000, None]
        })

        gex = compute_gex(data)
        dex = compute_dex(data)

        assert pd.isna(gex[1])
        assert pd.isna(dex[0])
        assert pd.isna(dex[2])
