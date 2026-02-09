"""Polygon.io API client for OHLCV, snapshots, and indices data.

Provides async access to Polygon endpoints for price and volume data:
- Daily OHLCV (aggregates)
- Real-time snapshots
- Index data (SPY, QQQ, IWM context)
- Technical indicators (optional)

API Documentation: https://polygon.io/docs/stocks

Usage:
    from obsidian.config import settings
    from obsidian.clients.polygon import PolygonClient

    async with PolygonClient(settings.polygon_api_key) as client:
        ohlcv = await client.get_daily_bars("AAPL", date_from="2024-01-01")
        snapshot = await client.get_snapshot("AAPL")
"""

from datetime import date, datetime
from typing import Any

from obsidian.clients.base import BaseAsyncClient


class PolygonClient(BaseAsyncClient):
    """Async client for Polygon.io API.

    Args:
        api_key: Polygon API key (from settings.polygon_api_key)
        rate_limit: Max requests per second (default: 5)
    """

    def __init__(self, api_key: str, rate_limit: int = 5) -> None:
        super().__init__(
            base_url="https://api.polygon.io",
            headers={},  # Polygon uses query param for auth, not header
            rate_limit=rate_limit,
        )
        self.api_key = api_key

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Override to inject API key into params."""
        params = params or {}
        params["apiKey"] = self.api_key
        return await super()._request(method, endpoint, params, json_data)

    async def get_daily_bars(
        self,
        ticker: str,
        date_from: str | date,
        date_to: str | date | None = None,
        multiplier: int = 1,
        sort: str = "asc",
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Get daily OHLCV bars for a ticker.

        Returns aggregated daily price/volume data.
        Used to compute Price Efficiency and Price Impact features.

        Args:
            ticker: Stock symbol
            date_from: Start date (YYYY-MM-DD or date object)
            date_to: End date (defaults to today)
            multiplier: Multiplier for timespan (1 = 1 day)
            sort: Sort order ('asc' or 'desc')
            limit: Max results (default: 5000)

        Returns:
            Dict with 'results' key containing list of daily bars.
            Each bar has: t (timestamp), o, h, l, c, v (volume), vw (VWAP), n (trades).

        Notes:
            - Uses /v2/aggs/ticker/{ticker}/range/{multiplier}/day/{from}/{to}
            - VWAP (vw) used for impact calculations
            - Trade count (n) available for liquidity metrics

        API Docs: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to
        """
        if isinstance(date_from, date):
            date_from = date_from.isoformat()
        if date_to is None:
            date_to = datetime.now().date().isoformat()
        elif isinstance(date_to, date):
            date_to = date_to.isoformat()

        endpoint = f"/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/day/{date_from}/{date_to}"
        params = {"sort": sort, "limit": limit, "adjusted": "true"}

        return await self.get(endpoint, params=params)

    async def get_snapshot(self, ticker: str) -> dict[str, Any]:
        """Get current snapshot for a ticker.

        Returns real-time price, volume, and intraday stats.
        Used for T+0 data when daily bar isn't closed yet.

        Args:
            ticker: Stock symbol

        Returns:
            Dict with 'ticker' key containing snapshot data.
            Has: day (today's OHLCV), prevDay (previous close), lastTrade, etc.

        API Docs: https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_tickers__stocksticker
        """
        endpoint = f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}"
        return await self.get(endpoint)

    async def get_indices_snapshot(
        self,
        tickers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get snapshots for indices (SPY, QQQ, IWM, etc.).

        Returns current state of major indices for macro context.

        Args:
            tickers: List of index tickers (default: ["I:SPX", "I:DJI", "I:NDX"])

        Returns:
            Dict with 'results' key containing list of index snapshots.
            Each has: ticker, value, session (OHLCV), change, change_percent.

        Notes:
            - Index tickers use "I:" prefix (e.g., "I:SPX" for S&P 500)
            - For ETFs (SPY, QQQ), use get_snapshot() instead

        API Docs: https://polygon.io/docs/indices/get_v3_snapshot_indices
        """
        if tickers is None:
            tickers = ["I:SPX", "I:DJI", "I:NDX"]

        ticker_list = ",".join(tickers)
        endpoint = "/v3/snapshot/indices"
        params = {"ticker.any_of": ticker_list}

        return await self.get(endpoint, params=params)

    async def get_open_close(
        self,
        ticker: str,
        target_date: str | date,
    ) -> dict[str, Any]:
        """Get open/close prices for a specific date.

        Returns official open and close prices for a given trading day.
        More reliable than using bars for end-of-day data.

        Args:
            ticker: Stock symbol
            target_date: Trading date (YYYY-MM-DD or date object)

        Returns:
            Dict with: symbol, open, high, low, close, volume, from (date).

        API Docs: https://polygon.io/docs/stocks/get_v1_open-close__stocksticker___date
        """
        if isinstance(target_date, date):
            target_date = target_date.isoformat()

        endpoint = f"/v1/open-close/{ticker.upper()}/{target_date}"
        return await self.get(endpoint)

    async def get_last_trade(self, ticker: str) -> dict[str, Any]:
        """Get the last trade for a ticker.

        Returns most recent trade execution.
        Used for real-time price updates.

        Args:
            ticker: Stock symbol

        Returns:
            Dict with 'results' key containing last trade data.
            Has: p (price), s (size), t (timestamp), x (exchange), etc.

        API Docs: https://polygon.io/docs/stocks/get_v2_last_trade__stocksticker
        """
        endpoint = f"/v2/last/trade/{ticker.upper()}"
        return await self.get(endpoint)

    async def get_market_status(self) -> dict[str, Any]:
        """Get current market status.

        Returns whether markets are open, closed, or in pre/post-market.

        Returns:
            Dict with: market, serverTime, exchanges (NYSE, NASDAQ status),
            earlyHours, afterHours.

        API Docs: https://polygon.io/docs/stocks/get_v1_marketstatus_now
        """
        endpoint = "/v1/marketstatus/now"
        return await self.get(endpoint)
