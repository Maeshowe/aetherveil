"""FRED (Federal Reserve Economic Data) API client.

Provides async access to FRED endpoints for macro event detection:
- Release dates (CPI, NFP, etc.)

API Documentation: https://fred.stlouisfed.org/docs/api/fred/

Usage:
    from obsidian.clients.fred import FREDClient

    async with FREDClient(api_key="your_key") as client:
        dates = await client.get_release_dates(release_id=10, limit=20)
"""

from typing import Any

from obsidian.clients.base import BaseAsyncClient


class FREDClient(BaseAsyncClient):
    """Async client for FRED API.

    Args:
        api_key: FRED API key
        rate_limit: Max requests per second (default: 5)
    """

    def __init__(self, api_key: str, rate_limit: int = 5) -> None:
        super().__init__(
            base_url="https://api.stlouisfed.org/fred",
            headers={},
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
        """Override to inject api_key and file_type=json into params."""
        params = params or {}
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        return await super()._request(method, endpoint, params, json_data)

    async def get_release_dates(
        self,
        release_id: int,
        limit: int = 20,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Get release dates for a FRED data release.

        Returns historical publication dates for releases like CPI or NFP.
        Used to detect upcoming macro events within a +-1 day window.

        Key release IDs:
            - CPI: 10
            - NFP (Employment Situation): 50

        Args:
            release_id: FRED release ID (e.g. 10 for CPI)
            limit: Max dates to return (default: 20)
            sort_order: 'asc' or 'desc' (default: 'desc' = most recent first)

        Returns:
            List of release date records.
            Each has: release_id, date
        """
        params: dict[str, Any] = {
            "release_id": release_id,
            "limit": limit,
            "sort_order": sort_order,
        }
        result = await self.get("/release/dates", params=params)
        return result.get("release_dates", [])
