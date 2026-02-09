"""Tests for structural focus module."""

import httpx
import pytest

from obsidian.clients.fmp import FMPClient
from obsidian.universe.structural import (
    STRUCTURAL_THRESHOLDS,
    IndexConstituent,
    deduplicate_structural_tickers,
    fetch_all_structural_focus,
    fetch_structural_focus,
)

BASE = "https://financialmodelingprep.com/stable"


def _make_holdings(n: int, etf: str = "SPY") -> list[dict]:
    """Generate n mock holdings with descending weights."""
    return [
        {
            "symbol": etf,
            "asset": f"STOCK{i}",
            "name": f"Stock {i} Inc.",
            "weightPercentage": round(10.0 - i * 0.3, 2),
            "sharesNumber": 1000000 * (n - i),
            "marketValue": 50000000 * (n - i),
        }
        for i in range(n)
    ]


class TestStructuralThresholds:
    """Test threshold constants."""

    def test_spy_threshold(self):
        assert STRUCTURAL_THRESHOLDS["SPY"] == 15

    def test_qqq_threshold(self):
        assert STRUCTURAL_THRESHOLDS["QQQ"] == 10

    def test_dia_threshold(self):
        assert STRUCTURAL_THRESHOLDS["DIA"] == 10

    def test_iwm_excluded(self):
        assert "IWM" not in STRUCTURAL_THRESHOLDS


class TestFetchStructuralFocus:
    """Tests for fetch_structural_focus."""

    @pytest.mark.asyncio
    async def test_spy_top_15(self, respx_mock):
        """Should return top 15 holdings for SPY."""
        holdings = _make_holdings(20, "SPY")
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "SPY")

        assert len(result) == 15
        assert all(isinstance(c, IndexConstituent) for c in result)
        # Sorted by weight desc, rank starts at 1
        assert result[0].rank == 1
        assert result[0].weight_pct > result[1].weight_pct

    @pytest.mark.asyncio
    async def test_qqq_top_10(self, respx_mock):
        """Should return top 10 holdings for QQQ."""
        holdings = _make_holdings(20, "QQQ")
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "QQQ")

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_dia_top_10(self, respx_mock):
        """Should return top 10 holdings for DIA."""
        holdings = _make_holdings(15, "DIA")
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "DIA")

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_iwm_skipped(self, respx_mock):
        """IWM should return empty list (skipped per spec)."""
        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "IWM")

        assert result == []

    @pytest.mark.asyncio
    async def test_unknown_etf_skipped(self, respx_mock):
        """Unknown ETF should return empty list."""
        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "XYZ")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_holdings(self, respx_mock):
        """Should handle empty holdings list."""
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "SPY")

        assert result == []

    @pytest.mark.asyncio
    async def test_fewer_holdings_than_threshold(self, respx_mock):
        """Should return all if fewer than threshold."""
        holdings = _make_holdings(5, "SPY")
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "SPY")

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_case_insensitive_etf(self, respx_mock):
        """Should uppercase the ETF symbol."""
        holdings = _make_holdings(12, "QQQ")
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "qqq")

        assert len(result) == 10
        assert all(c.etf == "QQQ" for c in result)

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty(self, respx_mock):
        """Should return empty on API error."""
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "SPY")

        assert result == []

    @pytest.mark.asyncio
    async def test_ticker_uppercased(self, respx_mock):
        """Constituent tickers should be uppercased."""
        holdings = [
            {"asset": "aapl", "weightPercentage": 7.0, "symbol": "SPY"},
        ]
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=holdings)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_structural_focus(fmp, "SPY")

        assert result[0].ticker == "AAPL"


class TestFetchAllStructuralFocus:
    """Tests for fetch_all_structural_focus."""

    @pytest.mark.asyncio
    async def test_fetches_all_etfs(self, respx_mock):
        """Should fetch for SPY, QQQ, and DIA."""
        for etf in ["SPY", "QQQ", "DIA"]:
            holdings = _make_holdings(20, etf)
            respx_mock.get(
                f"{BASE}/etf/holdings",
                params__contains={"symbol": etf},
            ).mock(return_value=httpx.Response(200, json=holdings))

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_all_structural_focus(fmp)

        assert set(result.keys()) == {"SPY", "QQQ", "DIA"}
        assert len(result["SPY"]) == 15
        assert len(result["QQQ"]) == 10
        assert len(result["DIA"]) == 10


class TestDeduplicateStructuralTickers:
    """Tests for deduplicate_structural_tickers."""

    def test_no_overlap(self):
        """Non-overlapping tickers should all be kept."""
        by_etf = {
            "SPY": [IndexConstituent("AAPL", "SPY", 1, 7.0)],
            "QQQ": [IndexConstituent("GOOGL", "QQQ", 1, 9.0)],
        }
        result = deduplicate_structural_tickers(by_etf)
        assert len(result) == 2
        assert "AAPL" in result
        assert "GOOGL" in result

    def test_overlap_keeps_higher_weight(self):
        """Overlapping ticker should keep the one with higher weight."""
        by_etf = {
            "SPY": [IndexConstituent("AAPL", "SPY", 1, 7.2)],
            "QQQ": [IndexConstituent("AAPL", "QQQ", 1, 11.5)],
        }
        result = deduplicate_structural_tickers(by_etf)
        assert len(result) == 1
        assert result["AAPL"].etf == "QQQ"
        assert result["AAPL"].weight_pct == 11.5

    def test_empty_input(self):
        """Empty input should return empty dict."""
        result = deduplicate_structural_tickers({})
        assert result == {}

    def test_single_etf(self):
        """Single ETF should pass through."""
        by_etf = {
            "SPY": [
                IndexConstituent("AAPL", "SPY", 1, 7.0),
                IndexConstituent("MSFT", "SPY", 2, 6.5),
            ]
        }
        result = deduplicate_structural_tickers(by_etf)
        assert len(result) == 2
