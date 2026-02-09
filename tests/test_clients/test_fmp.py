"""Tests for Financial Modeling Prep API client."""

import httpx
import pytest

from obsidian.clients.fmp import FMPClient

BASE = "https://financialmodelingprep.com/stable"


class TestFMPClient:
    """Tests for FMP API client."""

    @pytest.mark.asyncio
    async def test_get_profile(self, respx_mock):
        """Should fetch company profile."""
        mock_response = [
            {
                "symbol": "AAPL",
                "companyName": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "marketCap": 3000000000000,
                "description": "Apple Inc. designs and manufactures consumer electronics...",
                "ceo": "Tim Cook",
                "website": "https://www.apple.com",
            }
        ]

        respx_mock.get(f"{BASE}/profile").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_profile("AAPL")

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["sector"] == "Technology"

    @pytest.mark.asyncio
    async def test_get_quote(self, respx_mock):
        """Should fetch real-time quote."""
        mock_response = [
            {
                "symbol": "AAPL",
                "price": 151.25,
                "change": 2.50,
                "changePercentage": 1.68,
                "volume": 50000000,
                "marketCap": 3000000000000,
            }
        ]

        respx_mock.get(f"{BASE}/quote").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_quote("AAPL")

            assert isinstance(result, list)
            assert result[0]["price"] == 151.25

    @pytest.mark.asyncio
    async def test_get_stock_news(self, respx_mock):
        """Should fetch stock news."""
        mock_response = [
            {
                "publishedDate": "2024-01-15T10:30:00Z",
                "title": "Apple announces new product",
                "text": "Apple Inc. today announced...",
                "symbol": "AAPL",
                "url": "https://example.com/news/1",
                "site": "Example News",
            }
        ]

        respx_mock.get(f"{BASE}/news/stock-latest").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_stock_news(ticker="AAPL", limit=10)

            assert isinstance(result, list)
            assert result[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_stock_news_market_wide(self, respx_mock):
        """Should fetch market-wide news when no ticker specified."""
        respx_mock.get(f"{BASE}/news/stock-latest").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test_key_123") as client:
            await client.get_stock_news(ticker=None, limit=50)

    @pytest.mark.asyncio
    async def test_get_insider_trading(self, respx_mock):
        """Should fetch insider trading transactions."""
        mock_response = [
            {
                "filingDate": "2024-01-10",
                "transactionDate": "2024-01-08",
                "reportingName": "Tim Cook",
                "typeOfOwner": "director",
                "transactionType": "P-Purchase",
                "securitiesTransacted": 10000,
                "price": 150.0,
            }
        ]

        respx_mock.get(f"{BASE}/insider-trading").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_insider_trading("AAPL", limit=100)

            assert isinstance(result, list)
            assert result[0]["transactionType"] == "P-Purchase"

    @pytest.mark.asyncio
    async def test_get_analyst_estimates(self, respx_mock):
        """Should fetch analyst estimates."""
        mock_response = [
            {
                "date": "2024-03-31",
                "symbol": "AAPL",
                "estimatedRevenueLow": 90000000000,
                "estimatedRevenueHigh": 95000000000,
                "estimatedRevenueAvg": 92500000000,
                "numberAnalysts": 25,
            }
        ]

        respx_mock.get(f"{BASE}/analyst-estimates").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_analyst_estimates("AAPL", limit=4)

            assert isinstance(result, list)
            assert result[0]["numberAnalysts"] == 25

    @pytest.mark.asyncio
    async def test_get_price_target_consensus(self, respx_mock):
        """Should fetch price target consensus."""
        mock_response = [
            {
                "symbol": "AAPL",
                "targetHigh": 200.0,
                "targetLow": 140.0,
                "targetConsensus": 170.0,
                "targetMedian": 168.0,
            }
        ]

        respx_mock.get(f"{BASE}/price-target-consensus").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_price_target_consensus("AAPL")

            assert isinstance(result, list)
            assert result[0]["targetConsensus"] == 170.0

    @pytest.mark.asyncio
    async def test_get_income_statement(self, respx_mock):
        """Should fetch income statement."""
        mock_response = [
            {
                "date": "2023-12-31",
                "symbol": "AAPL",
                "revenue": 95000000000,
                "netIncome": 25000000000,
                "eps": 6.15,
                "fiscalYear": 2024,
            }
        ]

        respx_mock.get(f"{BASE}/income-statement").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_income_statement("AAPL", period="quarter", limit=4)

            assert isinstance(result, list)
            assert result[0]["revenue"] == 95000000000

    # --- ETF Holdings ---

    @pytest.mark.asyncio
    async def test_get_etf_holdings_spy(self, respx_mock):
        """Should fetch SPY ETF holdings."""
        mock_response = [
            {
                "symbol": "SPY",
                "asset": "AAPL",
                "name": "Apple Inc.",
                "sharesNumber": 180000000,
                "weightPercentage": 7.2,
                "marketValue": 27000000000,
                "updatedAt": "2024-01-15",
            },
            {
                "symbol": "SPY",
                "asset": "MSFT",
                "name": "Microsoft Corp.",
                "sharesNumber": 100000000,
                "weightPercentage": 6.8,
                "marketValue": 25000000000,
                "updatedAt": "2024-01-15",
            },
        ]

        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_etf_holdings("SPY")

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["asset"] == "AAPL"
            assert result[0]["weightPercentage"] == 7.2

    @pytest.mark.asyncio
    async def test_get_etf_holdings_empty(self, respx_mock):
        """Should handle empty ETF holdings."""
        respx_mock.get(f"{BASE}/etf/holdings").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_etf_holdings("UNKNOWN")
            assert result == []

    @pytest.mark.asyncio
    async def test_get_etf_holdings_uppercases_symbol(self, respx_mock):
        """Should uppercase the ETF symbol."""
        respx_mock.get(
            f"{BASE}/etf/holdings",
            params__contains={"symbol": "QQQ"},
        ).mock(
            return_value=httpx.Response(200, json=[{"asset": "AAPL"}])
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_etf_holdings("qqq")
            assert len(result) == 1

    # --- Earnings Calendar ---

    @pytest.mark.asyncio
    async def test_get_earnings_calendar(self, respx_mock):
        """Should fetch earnings calendar with date range."""
        mock_response = [
            {
                "symbol": "AAPL",
                "date": "2024-01-25",
                "epsActual": 2.18,
                "epsEstimated": 2.10,
                "revenueActual": 119580000000,
                "revenueEstimated": 117900000000,
            },
            {
                "symbol": "MSFT",
                "date": "2024-01-23",
                "epsActual": 2.93,
                "epsEstimated": 2.78,
                "revenueActual": 62020000000,
                "revenueEstimated": 61120000000,
            },
        ]

        respx_mock.get(f"{BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            from datetime import date
            result = await client.get_earnings_calendar(
                date_from=date(2024, 1, 14),
                date_to=date(2024, 1, 26),
            )

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_earnings_calendar_no_dates(self, respx_mock):
        """Should work without date parameters."""
        respx_mock.get(f"{BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_earnings_calendar()
            assert result == []

    @pytest.mark.asyncio
    async def test_get_earnings_calendar_date_params(self, respx_mock):
        """Should pass from/to date parameters correctly."""
        respx_mock.get(
            f"{BASE}/earnings-calendar",
            params__contains={"from": "2024-01-14", "to": "2024-01-16"},
        ).mock(
            return_value=httpx.Response(200, json=[{"symbol": "TSLA", "date": "2024-01-15"}])
        )

        async with FMPClient(api_key="test_key_123") as client:
            from datetime import date
            result = await client.get_earnings_calendar(
                date_from=date(2024, 1, 14), date_to=date(2024, 1, 16)
            )
            assert len(result) == 1

    # --- SP500 Constituents ---

    @pytest.mark.asyncio
    async def test_get_sp500_constituents(self, respx_mock):
        """Should fetch S&P 500 constituents."""
        mock_response = [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "sector": "Information Technology",
                "subSector": "Technology Hardware",
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft Corporation",
                "sector": "Information Technology",
                "subSector": "Systems Software",
            },
        ]

        respx_mock.get(f"{BASE}/sp500-constituent").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_sp500_constituents()

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["sector"] == "Information Technology"

    @pytest.mark.asyncio
    async def test_get_sp500_constituents_empty(self, respx_mock):
        """Should handle empty SP500 list."""
        respx_mock.get(f"{BASE}/sp500-constituent").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_sp500_constituents()
            assert result == []

    # --- General ---

    @pytest.mark.asyncio
    async def test_api_key_in_query_params(self, respx_mock):
        """API key should be sent as query parameter."""
        respx_mock.get(
            f"{BASE}/profile",
            params={"symbol": "AAPL", "apikey": "secret_fmp_key"},
        ).mock(return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]))

        async with FMPClient(api_key="secret_fmp_key") as client:
            await client.get_profile("AAPL")

    @pytest.mark.asyncio
    async def test_handles_empty_response_as_list(self, respx_mock):
        """Should handle empty responses gracefully."""
        respx_mock.get(f"{BASE}/news/stock-latest").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test_key_123") as client:
            result = await client.get_stock_news(limit=10)

            assert isinstance(result, list)
            assert len(result) == 0
