"""Tests for Polygon.io API client."""

from datetime import date

import httpx
import pytest

from obsidian.clients.polygon import PolygonClient


class TestPolygonClient:
    """Tests for Polygon API client."""

    @pytest.mark.asyncio
    async def test_get_daily_bars(self, respx_mock):
        """Should fetch daily OHLCV bars."""
        mock_response = {
            "results": [
                {
                    "t": 1705276800000,  # timestamp
                    "o": 150.0,
                    "h": 152.5,
                    "l": 149.5,
                    "c": 151.25,
                    "v": 50000000,  # volume
                    "vw": 151.0,  # VWAP
                    "n": 100000,  # trades
                }
            ],
            "status": "OK",
            "resultsCount": 1,
        }

        respx_mock.get(
            "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_daily_bars(
                ticker="AAPL",
                date_from="2024-01-01",
                date_to="2024-01-31",
            )

            assert "results" in result
            assert len(result["results"]) == 1
            bar = result["results"][0]
            assert bar["c"] == 151.25
            assert bar["v"] == 50000000

    @pytest.mark.asyncio
    async def test_daily_bars_with_date_objects(self, respx_mock):
        """Should accept date objects and convert to ISO format."""
        respx_mock.get(
            "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-15/2024-01-20"
        ).mock(return_value=httpx.Response(200, json={"results": []}))

        async with PolygonClient(api_key="test_key_123") as client:
            await client.get_daily_bars(
                ticker="AAPL",
                date_from=date(2024, 1, 15),
                date_to=date(2024, 1, 20),
            )

    @pytest.mark.asyncio
    async def test_get_snapshot(self, respx_mock):
        """Should fetch current snapshot."""
        mock_response = {
            "ticker": {
                "ticker": "AAPL",
                "day": {"o": 150.0, "h": 152.0, "l": 149.0, "c": 151.0, "v": 1000000},
                "prevDay": {"c": 148.0},
                "todaysChange": 3.0,
                "todaysChangePerc": 2.027,
            }
        }

        respx_mock.get(
            "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/AAPL"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_snapshot("AAPL")

            assert "ticker" in result
            assert result["ticker"]["ticker"] == "AAPL"
            assert result["ticker"]["todaysChange"] == 3.0

    @pytest.mark.asyncio
    async def test_get_indices_snapshot(self, respx_mock):
        """Should fetch indices snapshots."""
        mock_response = {
            "results": [
                {
                    "ticker": "I:SPX",
                    "name": "S&P 500",
                    "value": 4800.0,
                    "session": {"change": 50.0, "change_percent": 1.05},
                }
            ]
        }

        respx_mock.get("https://api.polygon.io/v3/snapshot/indices").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_indices_snapshot()

            assert "results" in result
            assert result["results"][0]["ticker"] == "I:SPX"

    @pytest.mark.asyncio
    async def test_indices_with_custom_tickers(self, respx_mock):
        """Should accept custom index tickers."""
        respx_mock.get(
            "https://api.polygon.io/v3/snapshot/indices",
            params={"ticker.any_of": "I:SPX,I:VIX", "apiKey": "test_key_123"},
        ).mock(return_value=httpx.Response(200, json={"results": []}))

        async with PolygonClient(api_key="test_key_123") as client:
            await client.get_indices_snapshot(tickers=["I:SPX", "I:VIX"])

    @pytest.mark.asyncio
    async def test_get_open_close(self, respx_mock):
        """Should fetch open/close for specific date."""
        mock_response = {
            "symbol": "AAPL",
            "from": "2024-01-15",
            "open": 150.0,
            "high": 152.0,
            "low": 149.0,
            "close": 151.0,
            "volume": 50000000,
        }

        respx_mock.get("https://api.polygon.io/v1/open-close/AAPL/2024-01-15").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_open_close("AAPL", "2024-01-15")

            assert result["symbol"] == "AAPL"
            assert result["close"] == 151.0

    @pytest.mark.asyncio
    async def test_get_last_trade(self, respx_mock):
        """Should fetch last trade."""
        mock_response = {
            "results": {
                "p": 151.25,  # price
                "s": 100,  # size
                "t": 1705276800000,  # timestamp
                "x": 4,  # exchange
            }
        }

        respx_mock.get("https://api.polygon.io/v2/last/trade/AAPL").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_last_trade("AAPL")

            assert result["results"]["p"] == 151.25

    @pytest.mark.asyncio
    async def test_get_market_status(self, respx_mock):
        """Should fetch market status."""
        mock_response = {
            "market": "open",
            "serverTime": "2024-01-15T14:30:00Z",
            "exchanges": {"nyse": "open", "nasdaq": "open"},
        }

        respx_mock.get("https://api.polygon.io/v1/marketstatus/now").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with PolygonClient(api_key="test_key_123") as client:
            result = await client.get_market_status()

            assert result["market"] == "open"
            assert result["exchanges"]["nyse"] == "open"

    @pytest.mark.asyncio
    async def test_api_key_in_query_params(self, respx_mock):
        """API key should be sent as query parameter, not header."""
        respx_mock.get(
            "https://api.polygon.io/v1/marketstatus/now",
            params={"apiKey": "secret_key_456"},
        ).mock(return_value=httpx.Response(200, json={"market": "open"}))

        async with PolygonClient(api_key="secret_key_456") as client:
            await client.get_market_status()
