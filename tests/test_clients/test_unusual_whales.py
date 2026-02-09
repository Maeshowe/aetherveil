"""Tests for Unusual Whales API client."""

from datetime import date

import httpx
import pytest

from obsidian.clients.unusual_whales import UnusualWhalesClient


class TestUnusualWhalesClient:
    """Tests for UW API client."""

    @pytest.mark.asyncio
    async def test_get_dark_pool_recent(self, respx_mock):
        """Should fetch recent dark pool prints."""
        mock_response = {
            "data": [
                {
                    "ticker": "AAPL",
                    "volume": 10000,
                    "price": 150.25,
                    "executed_at": "2024-01-15T10:30:00Z",
                    "market_center": "D",
                    "premium": 1502500.0,
                }
            ]
        }

        respx_mock.get(
            "https://api.unusualwhales.com/api/darkpool/recent"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            result = await client.get_dark_pool_recent(ticker="AAPL", limit=100)

            assert "data" in result
            assert len(result["data"]) == 1
            assert result["data"][0]["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_dark_pool_with_dates(self, respx_mock):
        """Should pass date parameters correctly."""
        # UW uses Authorization header, not query param for API key
        respx_mock.get(
            "https://api.unusualwhales.com/api/darkpool/recent"
        ).mock(return_value=httpx.Response(200, json={"data": []}))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            await client.get_dark_pool_recent(
                ticker="AAPL",
                limit=50,
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
            )

    @pytest.mark.asyncio
    async def test_get_greek_exposure(self, respx_mock):
        """Should fetch Greek exposure data."""
        mock_response = {
            "data": [
                {
                    "date": "2024-01-15",
                    "call_gamma": 1000000.0,
                    "put_gamma": 500000.0,
                    "call_delta": 2000000.0,
                    "put_delta": -1500000.0,
                    "call_vanna": 100000.0,
                    "put_vanna": -80000.0,
                    "call_charm": 50000.0,
                    "put_charm": -40000.0,
                }
            ]
        }

        respx_mock.get(
            "https://api.unusualwhales.com/api/stock/AAPL/greek-exposure"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            result = await client.get_greek_exposure("AAPL")

            assert "data" in result
            assert len(result["data"]) == 1
            greeks = result["data"][0]
            assert greeks["call_gamma"] == 1000000.0
            assert greeks["put_gamma"] == 500000.0

    @pytest.mark.asyncio
    async def test_ticker_is_uppercased(self, respx_mock):
        """Ticker symbols should be converted to uppercase."""
        respx_mock.get(
            "https://api.unusualwhales.com/api/stock/AAPL/greek-exposure"
        ).mock(return_value=httpx.Response(200, json={"data": []}))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            # Pass lowercase ticker
            await client.get_greek_exposure("aapl")

    @pytest.mark.asyncio
    async def test_get_iv_rank(self, respx_mock):
        """Should fetch IV rank data."""
        mock_response = {
            "data": [
                {
                    "date": "2024-01-15",
                    "volatility": 0.25,
                    "iv_rank_1y": 0.67,
                    "close": 150.25,
                }
            ]
        }

        respx_mock.get(
            "https://api.unusualwhales.com/api/stock/AAPL/iv-rank"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            result = await client.get_iv_rank("AAPL")

            assert "data" in result
            assert result["data"][0]["iv_rank_1y"] == 0.67

    @pytest.mark.asyncio
    async def test_get_option_contracts(self, respx_mock):
        """Should fetch option contracts."""
        mock_response = {
            "data": [
                {
                    "option_symbol": "AAPL240119C00150000",
                    "strike": 150.0,
                    "expiry": "2024-01-19",
                    "volume": 5000,
                    "implied_volatility": 0.28,
                }
            ]
        }

        respx_mock.get(
            "https://api.unusualwhales.com/api/stock/AAPL/option-contracts"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            result = await client.get_option_contracts("AAPL")

            assert "data" in result
            assert result["data"][0]["strike"] == 150.0

    @pytest.mark.asyncio
    async def test_get_market_tide(self, respx_mock):
        """Should fetch market tide data."""
        mock_response = {
            "data": [
                {
                    "date": "2024-01-15",
                    "net_volume": 1000000,
                    "net_call_premium": 50000000.0,
                    "net_put_premium": -30000000.0,
                }
            ]
        }

        respx_mock.get(
            "https://api.unusualwhales.com/api/market/market-tide"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        async with UnusualWhalesClient(api_key="test_key_123") as client:
            result = await client.get_market_tide()

            assert "data" in result
            assert result["data"][0]["net_call_premium"] == 50000000.0

    @pytest.mark.asyncio
    async def test_authorization_header_is_set(self, respx_mock):
        """API key should be sent in Authorization header."""
        respx_mock.get(
            "https://api.unusualwhales.com/api/market/market-tide",
            headers={"Authorization": "my_secret_key"},
        ).mock(return_value=httpx.Response(200, json={"data": []}))

        async with UnusualWhalesClient(api_key="my_secret_key") as client:
            await client.get_market_tide()
