"""Unusual Whales API client for dark pool, Greeks, and options data.

Provides async access to UW endpoints needed for OBSIDIAN MM features:
- Dark pool flow (recent prints, venue distribution)
- Greek exposure (GEX, DEX, Vanna, Charm)
- IV rank and skew
- Options contracts for microstructure analysis

API Documentation: https://docs.unusualwhales.com/api

Usage:
    from obsidian.config import settings
    from obsidian.clients.unusual_whales import UnusualWhalesClient

    async with UnusualWhalesClient(settings.uw_api_key) as client:
        greeks = await client.get_greek_exposure("AAPL")
        dark_pool = await client.get_dark_pool_recent("AAPL", limit=100)
"""

from datetime import date, datetime
from typing import Any

from obsidian.clients.base import BaseAsyncClient


class UnusualWhalesClient(BaseAsyncClient):
    """Async client for Unusual Whales API.

    Args:
        api_key: UW API key (from settings.uw_api_key)
        rate_limit: Max requests per second (default: 10)
    """

    def __init__(self, api_key: str, rate_limit: int = 10) -> None:
        super().__init__(
            base_url="https://api.unusualwhales.com/api",
            headers={"Authorization": api_key},
            rate_limit=rate_limit,
        )

    async def get_dark_pool_recent(
        self,
        ticker: str | None = None,
        limit: int = 100,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Get recent dark pool prints.

        Returns raw dark pool transaction data with venue, size, price, etc.
        Used to compute DarkShare, Block Intensity, and Venue Mix features.

        Args:
            ticker: Stock symbol (None = all tickers)
            limit: Max results to return (default: 100)
            date_from: Start date for historical data
            date_to: End date for historical data

        Returns:
            Dict with 'data' key containing list of dark pool prints.
            Each print has: ticker, volume, price, executed_at, market_center, etc.

        API Docs: https://docs.unusualwhales.com/api/stock/darkpool-recent
        """
        params: dict[str, Any] = {"limit": limit}
        if ticker:
            params["ticker"] = ticker.upper()
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()

        return await self.get("/darkpool/recent", params=params)

    async def get_greek_exposure(
        self,
        ticker: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Get Greek exposure (GEX, DEX, Vanna, Charm) for a ticker.

        Returns dealer Greek exposures aggregated across all options.
        Critical for Γ⁺/Γ⁻ regime classification.

        Args:
            ticker: Stock symbol
            date_from: Start date
            date_to: End date

        Returns:
            Dict with 'data' key containing list of daily Greek exposures.
            Each entry has: date, call_gamma, put_gamma, call_delta, put_delta,
            call_vanna, put_vanna, call_charm, put_charm.

        Notes:
            - GEX = net gamma exposure (call_gamma - put_gamma)
            - DEX = net delta exposure (call_delta - put_delta)
            - GEX > 0 → dealers long gamma (stabilizing)
            - GEX < 0 → dealers short gamma (destabilizing)

        API Docs: https://docs.unusualwhales.com/api/stock/greek-exposure
        """
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()

        return await self.get(f"/stock/{ticker.upper()}/greek-exposure", params=params)

    async def get_iv_rank(
        self,
        ticker: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Get IV Rank for a ticker.

        Returns 1-year IV rank (current IV percentile vs 1-year range).
        Used for IV Skew feature.

        Args:
            ticker: Stock symbol
            date_from: Start date
            date_to: End date

        Returns:
            Dict with 'data' key containing list of daily IV ranks.
            Each entry has: date, volatility, iv_rank_1y, close.

        API Docs: https://docs.unusualwhales.com/api/stock/iv-rank
        """
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()

        return await self.get(f"/stock/{ticker.upper()}/iv-rank", params=params)

    async def get_option_contracts(
        self,
        ticker: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Get option contracts for a ticker.

        Returns detailed options data for computing IV skew and venue analysis.

        Args:
            ticker: Stock symbol
            date_from: Start date
            date_to: End date

        Returns:
            Dict with 'data' key containing option contracts.
            Each has: option_symbol, strike, expiry, volume, premium,
            implied_volatility, delta, gamma, etc.

        API Docs: https://docs.unusualwhales.com/api/stock/option-contracts
        """
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()

        return await self.get(f"/stock/{ticker.upper()}/option-contracts", params=params)

    async def get_market_tide(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Get market-wide options flow (market tide).

        Returns aggregate net call/put premium across entire market.
        Used for macro context overlay.

        Args:
            date_from: Start date
            date_to: End date

        Returns:
            Dict with 'data' key containing daily market tide.
            Each has: date, net_volume, net_call_premium, net_put_premium.

        API Docs: https://docs.unusualwhales.com/api/market/market-tide
        """
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()

        return await self.get("/market/market-tide", params=params)
