"""Tests for Fetcher — API → Parquet Cache."""

import asyncio
from datetime import date, timedelta
from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from obsidian.pipeline.fetcher import Fetcher


# --- Mock API response data ---

MOCK_DARK_POOL = {
    "data": [
        {
            "size": 5000,
            "ticker": "SPY",
            "price": "600.50",
            "volume": 80000000,
            "executed_at": "2024-01-15T14:30:00Z",
            "premium": "3002500",
            "nbbo_ask": "600.55",
            "nbbo_bid": "600.45",
            "canceled": False,
            "market_center": "D",
            "nbbo_ask_quantity": 100,
            "nbbo_bid_quantity": 200,
            "sale_cond_codes": None,
            "tracking_id": 12345,
            "trade_code": None,
            "trade_settlement": "regular",
            "ext_hour_sold_codes": None,
        },
        {
            "size": 3000,
            "ticker": "SPY",
            "price": "600.60",
            "volume": 80000000,
            "executed_at": "2024-01-15T15:00:00Z",
            "premium": "1801800",
            "nbbo_ask": "600.65",
            "nbbo_bid": "600.55",
            "canceled": False,
            "market_center": "L",
            "nbbo_ask_quantity": 50,
            "nbbo_bid_quantity": 75,
            "sale_cond_codes": None,
            "tracking_id": 12346,
            "trade_code": None,
            "trade_settlement": "regular",
            "ext_hour_sold_codes": None,
        },
    ]
}

MOCK_GREEKS = {
    "data": [
        {
            "date": "2024-01-15",
            "call_gamma": "4500000.0",
            "put_gamma": "-5000000.0",
            "call_delta": "180000000.0",
            "put_delta": "-130000000.0",
            "call_vanna": "12000000.0",
            "put_vanna": "-8000000.0",
            "call_charm": "-3000000.0",
            "put_charm": "1000000.0",
        }
    ]
}

MOCK_IV_RANK = {
    "data": [
        {
            "date": "2024-01-15",
            "volatility": "0.18",
            "iv_rank_1y": "35.5",
            "close": "600.50",
            "updated_at": "2024-01-15T22:00:00Z",
        }
    ]
}

MOCK_BARS = {
    "results": [
        {
            "v": 85000000.0,
            "vw": 600.12,
            "o": 598.50,
            "c": 601.25,
            "h": 602.00,
            "l": 597.80,
            "t": 1705276800000,
            "n": 950000,
        }
    ],
    "resultsCount": 1,
    "adjusted": True,
}

MOCK_QUOTE = [
    {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "price": 601.25,
        "change": 2.75,
        "changePercentage": 0.46,
        "volume": 85000000,
        "dayLow": 597.80,
        "dayHigh": 602.00,
        "yearHigh": 610.00,
        "yearLow": 480.00,
        "marketCap": 600000000000,
        "priceAvg50": 595.00,
        "priceAvg200": 570.00,
        "exchange": "AMEX",
        "open": 598.50,
        "previousClose": 598.50,
        "timestamp": 1705276800,
    }
]


UW_BASE = "https://api.unusualwhales.com/api"
POLYGON_BASE = "https://api.polygon.io"
FMP_BASE = "https://financialmodelingprep.com/stable"


class TestFetcherInit:
    """Test Fetcher initialization."""

    def test_default_cache_dir(self, tmp_path):
        """Uses settings.cache_dir by default."""
        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.cache_dir = str(tmp_path)
            mock_settings.uw_concurrency = 3
            fetcher = Fetcher()
            assert fetcher.cache.base_path == tmp_path

    def test_custom_cache_dir(self, tmp_path):
        """Accepts custom cache directory."""
        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_concurrency = 3
            fetcher = Fetcher(cache_dir=str(tmp_path))
            assert fetcher.cache.base_path == tmp_path


class TestFetchTicker:
    """Test fetching data for a single ticker."""

    @pytest.mark.asyncio
    async def test_all_sources_success(self, tmp_path, respx_mock):
        """All 5 sources fetched and cached on success."""
        target = date(2024, 1, 15)

        # Mock all API endpoints
        respx_mock.get(f"{UW_BASE}/darkpool/recent").mock(
            return_value=httpx.Response(200, json=MOCK_DARK_POOL)
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/greek-exposure").mock(
            return_value=httpx.Response(200, json=MOCK_GREEKS)
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/iv-rank").mock(
            return_value=httpx.Response(200, json=MOCK_IV_RANK)
        )
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/v2/aggs/ticker/SPY").mock(
            return_value=httpx.Response(200, json=MOCK_BARS)
        )
        respx_mock.get(f"{FMP_BASE}/quote").mock(
            return_value=httpx.Response(200, json=MOCK_QUOTE)
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            result = await fetcher.fetch_ticker("SPY", target)

        assert result["dark_pool"] is True
        assert result["greeks"] is True
        assert result["iv_rank"] is True
        assert result["bars"] is True
        assert result["quote"] is True

        # Verify cache files were created
        spy_dir = tmp_path / "SPY" / "raw"
        assert spy_dir.exists()
        parquet_files = list(spy_dir.glob("*.parquet"))
        assert len(parquet_files) == 5

    @pytest.mark.asyncio
    async def test_partial_api_failure(self, tmp_path, respx_mock):
        """Graceful degradation: failed sources marked False, others succeed."""
        target = date(2024, 1, 15)

        # Dark pool fails with 500
        respx_mock.get(f"{UW_BASE}/darkpool/recent").mock(
            return_value=httpx.Response(500, json={"error": "server error"})
        )
        # Greeks succeed
        respx_mock.get(f"{UW_BASE}/stock/SPY/greek-exposure").mock(
            return_value=httpx.Response(200, json=MOCK_GREEKS)
        )
        # IV rank fails
        respx_mock.get(f"{UW_BASE}/stock/SPY/iv-rank").mock(
            return_value=httpx.Response(500, json={"error": "server error"})
        )
        # Bars succeed
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/v2/aggs/ticker/SPY").mock(
            return_value=httpx.Response(200, json=MOCK_BARS)
        )
        # Quote succeeds
        respx_mock.get(f"{FMP_BASE}/quote").mock(
            return_value=httpx.Response(200, json=MOCK_QUOTE)
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            result = await fetcher.fetch_ticker("SPY", target)

        assert result["dark_pool"] is False
        assert result["greeks"] is True
        assert result["iv_rank"] is False
        assert result["bars"] is True
        assert result["quote"] is True

    @pytest.mark.asyncio
    async def test_empty_api_response(self, tmp_path, respx_mock):
        """Empty data arrays → source marked False, no cache write."""
        target = date(2024, 1, 15)

        respx_mock.get(f"{UW_BASE}/darkpool/recent").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/greek-exposure").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/iv-rank").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/v2/aggs/ticker/SPY").mock(
            return_value=httpx.Response(200, json={"results": [], "resultsCount": 0})
        )
        respx_mock.get(f"{FMP_BASE}/quote").mock(
            return_value=httpx.Response(200, json=[])
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            result = await fetcher.fetch_ticker("SPY", target)

        # All sources should be False (no data)
        assert all(v is False for v in result.values())

        # No cache files created
        spy_dir = tmp_path / "SPY" / "raw"
        assert not spy_dir.exists() or len(list(spy_dir.glob("*.parquet"))) == 0

    @pytest.mark.asyncio
    async def test_ticker_uppercased(self, tmp_path, respx_mock):
        """Ticker should be uppercased before API calls."""
        target = date(2024, 1, 15)

        # Only match uppercase SPY in URL path
        respx_mock.get(f"{UW_BASE}/darkpool/recent").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/greek-exposure").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(f"{UW_BASE}/stock/SPY/iv-rank").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/v2/aggs/ticker/SPY").mock(
            return_value=httpx.Response(200, json={"results": [], "resultsCount": 0})
        )
        respx_mock.get(f"{FMP_BASE}/quote").mock(
            return_value=httpx.Response(200, json=[])
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            # Pass lowercase — should still work
            result = await fetcher.fetch_ticker("spy", target)

        # Should have made requests (even if data is empty)
        assert isinstance(result, dict)


class TestFetchAll:
    """Test fetching multiple tickers."""

    @pytest.mark.asyncio
    async def test_fetch_multiple_tickers(self, tmp_path, respx_mock):
        """Fetches data for each ticker sequentially."""
        target = date(2024, 1, 15)

        # Mock all endpoints for both tickers (use permissive matching)
        respx_mock.get(f"{UW_BASE}/darkpool/recent").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(url__startswith=f"{UW_BASE}/stock/").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/v2/aggs/ticker/").mock(
            return_value=httpx.Response(200, json={"results": [], "resultsCount": 0})
        )
        respx_mock.get(f"{FMP_BASE}/quote").mock(
            return_value=httpx.Response(200, json=[])
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            results = await fetcher.fetch_all({"SPY", "QQQ"}, target)

        assert "SPY" in results
        assert "QQQ" in results
        assert isinstance(results["SPY"], dict)
        assert isinstance(results["QQQ"], dict)

    @pytest.mark.asyncio
    async def test_partial_failure_isolation(self, tmp_path, respx_mock):
        """One ticker failing does not prevent others from succeeding."""
        target = date(2024, 1, 15)

        # Mock UW endpoint to raise for FAIL ticker, succeed for SPY
        def uw_side_effect(request):
            if "FAIL" in str(request.url).upper():
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"data": []})

        respx_mock.get(url__startswith=f"{UW_BASE}/").mock(side_effect=uw_side_effect)
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/").mock(
            return_value=httpx.Response(200, json={"results": [], "resultsCount": 0})
        )
        respx_mock.get(url__startswith=f"{FMP_BASE}/").mock(
            return_value=httpx.Response(200, json=[])
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 10
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            results = await fetcher.fetch_all({"SPY", "FAIL"}, target)

        # Both tickers should be in results (FAIL gets default False dict)
        assert "SPY" in results
        assert "FAIL" in results

    @pytest.mark.asyncio
    async def test_empty_tickers_returns_empty(self, tmp_path):
        """Empty ticker set returns empty dict."""
        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.cache_dir = str(tmp_path)
            mock_settings.uw_concurrency = 10
            fetcher = Fetcher(cache_dir=str(tmp_path))
            results = await fetcher.fetch_all(set(), date(2024, 1, 15))

        assert results == {}


class TestUWConcurrency:
    """Test UW semaphore-based concurrency limiting."""

    def test_semaphore_created_from_config(self, tmp_path):
        """Semaphore value matches uw_concurrency config."""
        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.cache_dir = str(tmp_path)
            mock_settings.uw_concurrency = 5
            fetcher = Fetcher(cache_dir=str(tmp_path))
            assert fetcher._uw_semaphore._value == 5

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_uw_access(self, tmp_path, respx_mock):
        """Semaphore=1 forces sequential UW access (max 1 concurrent)."""
        target = date(2024, 1, 15)
        peak_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def uw_side_effect(request):
            nonlocal peak_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
            # Small delay to allow overlap detection
            await asyncio.sleep(0.01)
            async with lock:
                current_concurrent -= 1
            return httpx.Response(200, json={"data": []})

        respx_mock.get(url__startswith=f"{UW_BASE}/").mock(side_effect=uw_side_effect)
        respx_mock.get(url__startswith=f"{POLYGON_BASE}/").mock(
            return_value=httpx.Response(200, json={"results": [], "resultsCount": 0})
        )
        respx_mock.get(url__startswith=f"{FMP_BASE}/").mock(
            return_value=httpx.Response(200, json=[])
        )

        with patch("obsidian.pipeline.fetcher.settings") as mock_settings:
            mock_settings.uw_api_key = "test_uw"
            mock_settings.uw_rate_limit = 100
            mock_settings.polygon_api_key = "test_polygon"
            mock_settings.polygon_rate_limit = 100
            mock_settings.fmp_api_key = "test_fmp"
            mock_settings.fmp_rate_limit = 100
            mock_settings.uw_concurrency = 1  # Only 1 concurrent UW stream
            mock_settings.cache_dir = str(tmp_path)

            fetcher = Fetcher(cache_dir=str(tmp_path))
            results = await fetcher.fetch_all({"SPY", "QQQ", "AAPL"}, target)

        # With concurrency=1, peak should be exactly 1
        assert peak_concurrent == 1
        assert len(results) == 3
