"""Financial Modeling Prep API client for fundamentals and news.

Provides async access to FMP endpoints for:
- Company profiles
- Stock news
- Insider trading
- Analyst ratings
- Fundamentals (income statement, balance sheet)

API Documentation: https://site.financialmodelingprep.com/developer/docs

Usage:
    from obsidian.config import settings
    from obsidian.clients.fmp import FMPClient

    async with FMPClient(settings.fmp_api_key) as client:
        profile = await client.get_profile("AAPL")
        news = await client.get_stock_news("AAPL", limit=10)
"""

from datetime import date
from typing import Any

from obsidian.clients.base import BaseAsyncClient


class FMPClient(BaseAsyncClient):
    """Async client for Financial Modeling Prep API.

    Args:
        api_key: FMP API key (from settings.fmp_api_key)
        rate_limit: Max requests per second (default: 10)
    """

    def __init__(self, api_key: str, rate_limit: int = 10) -> None:
        super().__init__(
            base_url="https://financialmodelingprep.com/stable",
            headers={},  # FMP uses query param for auth, not header
            rate_limit=rate_limit,
        )
        self.api_key = api_key

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Override to inject API key into params."""
        params = params or {}
        params["apikey"] = self.api_key
        return await super()._request(method, endpoint, params, json_data)

    async def get_profile(self, ticker: str) -> list[dict[str, Any]]:
        """Get company profile.

        Returns company metadata, sector, industry, market cap, etc.
        Used for context and sector-level analysis.

        Args:
            ticker: Stock symbol

        Returns:
            List with single dict containing company profile.
            Has: symbol, companyName, sector, industry, marketCap, description,
            ceo, website, ipoDate, isEtf, etc.

        API Docs: https://site.financialmodelingprep.com/developer/docs#company-profile
        """
        endpoint = "/profile"
        params = {"symbol": ticker.upper()}
        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else [result]

    async def get_quote(self, ticker: str) -> list[dict[str, Any]]:
        """Get real-time quote.

        Returns current price, volume, change, market cap.
        Alternative to Polygon snapshot for price data.

        Args:
            ticker: Stock symbol

        Returns:
            List with single dict containing quote data.
            Has: symbol, price, change, changePercentage, volume, marketCap,
            dayLow, dayHigh, yearLow, yearHigh, priceAvg50, priceAvg200.

        API Docs: https://site.financialmodelingprep.com/developer/docs#stock-real-time-price
        """
        endpoint = "/quote"
        params = {"symbol": ticker.upper()}
        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else [result]

    async def get_stock_news(
        self,
        ticker: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get stock news articles.

        Returns recent news for a ticker or market-wide if no ticker specified.
        Used for event detection and narrative context.

        Args:
            ticker: Stock symbol (None = market-wide news)
            limit: Max articles to return (default: 50, max: 1000)

        Returns:
            List of news articles.
            Each has: publishedDate, title, text, symbol, url, site, image.

        API Docs: https://site.financialmodelingprep.com/developer/docs#stock-news
        """
        endpoint = "/news/stock-latest"
        params: dict[str, Any] = {"limit": limit, "page": 0}
        if ticker:
            params["symbol"] = ticker.upper()

        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_insider_trading(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get insider trading transactions.

        Returns recent insider buys/sells for a ticker.
        Used for insider accumulation/distribution detection.

        Args:
            ticker: Stock symbol
            limit: Max transactions to return (default: 100)

        Returns:
            List of insider transactions.
            Each has: filingDate, transactionDate, reportingName, typeOfOwner,
            transactionType, securitiesTransacted, price, securitiesOwned.

        API Docs: https://site.financialmodelingprep.com/developer/docs#insider-trading
        """
        endpoint = "/insider-trading"
        params: dict[str, Any] = {"symbol": ticker.upper(), "limit": limit}

        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_analyst_estimates(
        self,
        ticker: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Get analyst estimates.

        Returns consensus estimates for revenue, EPS, etc.
        Used for earnings expectations context.

        Args:
            ticker: Stock symbol
            limit: Number of quarters to return (default: 4)

        Returns:
            List of quarterly estimates.
            Each has: date, symbol, estimatedRevenue, estimatedEps,
            numberAnalysts, etc.

        API Docs: https://site.financialmodelingprep.com/developer/docs#analyst-estimates
        """
        endpoint = "/analyst-estimates"
        params: dict[str, Any] = {"symbol": ticker.upper(), "limit": limit}

        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_price_target_consensus(
        self,
        ticker: str,
    ) -> list[dict[str, Any]]:
        """Get analyst price target consensus.

        Returns consensus price targets from sell-side analysts.
        Used for sentiment and positioning context.

        Args:
            ticker: Stock symbol

        Returns:
            List with single dict containing consensus data.
            Has: targetHigh, targetLow, targetConsensus, targetMedian.

        API Docs: https://site.financialmodelingprep.com/developer/docs#price-target-consensus
        """
        endpoint = "/price-target-consensus"
        params: dict[str, Any] = {"symbol": ticker.upper()}

        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_etf_holdings(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """Get ETF holdings (constituents with weights).

        Returns holdings for an ETF sorted by weight. Used to determine
        structural focus tickers (top-N by weight for SPY, QQQ, DIA).

        Args:
            symbol: ETF symbol (e.g. SPY, QQQ, DIA)

        Returns:
            List of holdings.
            Each has: symbol, asset, name, sharesNumber, weightPercentage,
            marketValue, updatedAt.
        """
        endpoint = "/etf/holdings"
        params: dict[str, Any] = {"symbol": symbol.upper()}
        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_earnings_calendar(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get earnings calendar.

        Returns upcoming and recent earnings announcements.
        Used for event-based focus tier promotion.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of earnings entries.
            Each has: symbol, date, epsActual, epsEstimated,
            revenueActual, revenueEstimated.
        """
        endpoint = "/earnings-calendar"
        params: dict[str, Any] = {}
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["to"] = date_to.isoformat()
        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []

    async def get_sp500_constituents(self) -> list[dict[str, Any]]:
        """Get current S&P 500 constituents.

        Returns all ~500 companies in the S&P 500 index.
        Used for filtering earnings to only SP500 members.

        Returns:
            List of constituents.
            Each has: symbol, name, sector, subSector, headQuarter,
            dateFirstAdded, cik, founded.
        """
        endpoint = "/sp500-constituent"
        result = await self.get(endpoint, params={})
        return result if isinstance(result, list) else []

    async def get_income_statement(
        self,
        ticker: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Get income statement.

        Returns historical income statements (quarterly or annual).
        Used for fundamental context and growth analysis.

        Args:
            ticker: Stock symbol
            period: 'quarter' or 'annual' (default: 'quarter')
            limit: Number of periods to return (default: 4)

        Returns:
            List of income statements.
            Each has: date, symbol, revenue, netIncome, eps, operatingIncome,
            grossProfit, ebitda, etc.

        API Docs: https://site.financialmodelingprep.com/developer/docs#income-statement
        """
        endpoint = "/income-statement"
        params: dict[str, Any] = {"symbol": ticker.upper(), "period": period, "limit": limit}

        result = await self.get(endpoint, params=params)
        return result if isinstance(result, list) else []
