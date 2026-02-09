"""Tests for FRED API client."""

import httpx
import pytest

from obsidian.clients.fred import FREDClient

BASE = "https://api.stlouisfed.org/fred"


class TestFREDClient:
    """Tests for FRED API client."""

    @pytest.mark.asyncio
    async def test_get_cpi_release_dates(self, respx_mock):
        """Should fetch CPI release dates."""
        mock_response = {
            "release_dates": [
                {"release_id": 10, "date": "2024-01-11"},
                {"release_id": 10, "date": "2023-12-12"},
            ]
        }

        respx_mock.get(f"{BASE}/release/dates").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FREDClient(api_key="test_fred_key") as client:
            result = await client.get_release_dates(release_id=10, limit=2)

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["release_id"] == 10
            assert result[0]["date"] == "2024-01-11"

    @pytest.mark.asyncio
    async def test_get_nfp_release_dates(self, respx_mock):
        """Should fetch NFP release dates."""
        mock_response = {
            "release_dates": [
                {"release_id": 50, "date": "2024-02-02"},
                {"release_id": 50, "date": "2024-01-05"},
            ]
        }

        respx_mock.get(f"{BASE}/release/dates").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FREDClient(api_key="test_fred_key") as client:
            result = await client.get_release_dates(release_id=50, limit=2)

            assert len(result) == 2
            assert result[0]["release_id"] == 50

    @pytest.mark.asyncio
    async def test_api_key_injected(self, respx_mock):
        """API key and file_type=json should be sent as query params."""
        respx_mock.get(
            f"{BASE}/release/dates",
            params={
                "release_id": "10",
                "limit": "5",
                "sort_order": "desc",
                "api_key": "my_secret_key",
                "file_type": "json",
            },
        ).mock(
            return_value=httpx.Response(200, json={"release_dates": []})
        )

        async with FREDClient(api_key="my_secret_key") as client:
            result = await client.get_release_dates(release_id=10, limit=5)
            assert result == []

    @pytest.mark.asyncio
    async def test_empty_release_dates(self, respx_mock):
        """Should handle empty release_dates list."""
        respx_mock.get(f"{BASE}/release/dates").mock(
            return_value=httpx.Response(200, json={"release_dates": []})
        )

        async with FREDClient(api_key="test_fred_key") as client:
            result = await client.get_release_dates(release_id=10)

            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_missing_release_dates_key(self, respx_mock):
        """Should handle response without release_dates key gracefully."""
        respx_mock.get(f"{BASE}/release/dates").mock(
            return_value=httpx.Response(200, json={"error_message": "Bad Request"})
        )

        async with FREDClient(api_key="test_fred_key") as client:
            result = await client.get_release_dates(release_id=999)

            assert result == []

    @pytest.mark.asyncio
    async def test_sort_order_asc(self, respx_mock):
        """Should pass sort_order parameter."""
        mock_response = {
            "release_dates": [
                {"release_id": 10, "date": "2023-01-12"},
                {"release_id": 10, "date": "2023-02-14"},
            ]
        }

        respx_mock.get(
            f"{BASE}/release/dates",
            params__contains={"sort_order": "asc"},
        ).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        async with FREDClient(api_key="test_fred_key") as client:
            result = await client.get_release_dates(
                release_id=10, limit=2, sort_order="asc"
            )

            assert len(result) == 2
            assert result[0]["date"] == "2023-01-12"

    @pytest.mark.asyncio
    async def test_default_rate_limit(self):
        """Default rate limit should be 5 req/s."""
        client = FREDClient(api_key="test_key")
        assert client._rate_limiter.rate == 5
