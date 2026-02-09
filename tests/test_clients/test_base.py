"""Tests for base async client."""

import asyncio

import httpx
import pytest

from obsidian.clients.base import APIProviderError, BaseAsyncClient, RateLimiter


class TestRateLimiter:
    """Tests for token bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Rate limiter should allow requests under the limit."""
        limiter = RateLimiter(rate=10)  # 10 req/s

        # Should allow 5 requests immediately
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_blocks_when_over_limit(self):
        """Rate limiter should block when over limit."""
        limiter = RateLimiter(rate=2)  # 2 req/s

        # First 2 requests should be instant
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        await limiter.acquire()
        first_duration = asyncio.get_event_loop().time() - start

        # Third request should wait ~0.5s
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        third_duration = asyncio.get_event_loop().time() - start

        assert first_duration < 0.1  # Nearly instant
        assert third_duration > 0.3  # Had to wait


class TestBaseAsyncClient:
    """Tests for base async HTTP client."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, respx_mock):
        """Client should properly initialize and cleanup."""
        respx_mock.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        async with BaseAsyncClient(
            base_url="https://api.example.com",
            headers={"Authorization": "test_key"},
        ) as client:
            assert client._client is not None
            result = await client.get("/test")
            assert result == {"status": "ok"}

        # Client should be closed after exiting context
        assert client._client is None

    @pytest.mark.asyncio
    async def test_raises_if_used_without_context_manager(self):
        """Client should raise if used without async with."""
        client = BaseAsyncClient(base_url="https://api.example.com")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.get("/test")

    @pytest.mark.asyncio
    async def test_request_adds_leading_slash(self, respx_mock):
        """Requests should work with or without leading slash."""
        respx_mock.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            # Both should work
            result1 = await client.get("/test")
            result2 = await client.get("test")  # No leading slash

            assert result1 == {"data": "value"}
            assert result2 == {"data": "value"}

    @pytest.mark.asyncio
    async def test_handles_http_errors(self, respx_mock):
        """Client should raise APIProviderError on HTTP errors."""
        respx_mock.get("https://api.example.com/error").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            with pytest.raises(APIProviderError) as exc_info:
                await client.get("/error")

            assert exc_info.value.status_code == 404
            assert "Not Found" in exc_info.value.response_body

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, respx_mock):
        """Client should raise APIProviderError on invalid JSON."""
        respx_mock.get("https://api.example.com/invalid").mock(
            return_value=httpx.Response(200, text="not json")
        )

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            with pytest.raises(APIProviderError, match="Invalid JSON"):
                await client.get("/invalid")

    @pytest.mark.asyncio
    async def test_respects_rate_limit(self, respx_mock):
        """Client should respect rate limiting."""
        respx_mock.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        async with BaseAsyncClient(
            base_url="https://api.example.com",
            rate_limit=2,  # 2 req/s
        ) as client:
            start = asyncio.get_event_loop().time()

            # Make 3 requests
            await client.get("/test")
            await client.get("/test")
            await client.get("/test")

            duration = asyncio.get_event_loop().time() - start

            # Should take at least ~0.5s due to rate limiting
            assert duration > 0.3

    @pytest.mark.asyncio
    async def test_get_convenience_method(self, respx_mock):
        """get() should be shorthand for GET request."""
        respx_mock.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            result = await client.get("/data", params={"key": "value"})
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_post_convenience_method(self, respx_mock):
        """post() should be shorthand for POST request."""
        respx_mock.post("https://api.example.com/submit").mock(
            return_value=httpx.Response(200, json={"created": True})
        )

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            result = await client.post("/submit", json_data={"name": "test"})
            assert result == {"created": True}


class TestRateLimiterInit:
    """Test RateLimiter initialization outside an event loop."""

    def test_init_without_event_loop(self):
        """RateLimiter can be created in synchronous context."""
        limiter = RateLimiter(rate=10)
        assert limiter.rate == 10
        assert limiter.tokens == 10
        assert limiter._initialized is False


class TestRetryBehavior:
    """Test retry with exponential backoff in _request()."""

    @pytest.mark.asyncio
    async def test_retries_on_429(self, respx_mock):
        """Client retries on 429 Too Many Requests."""
        route = respx_mock.get("https://api.example.com/rate-limited")
        route.side_effect = [
            httpx.Response(429, text="Too Many Requests"),
            httpx.Response(429, text="Too Many Requests"),
            httpx.Response(200, json={"ok": True}),
        ]

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            result = await client.get("/rate-limited")
            assert result == {"ok": True}
            assert route.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_503(self, respx_mock):
        """Client retries on 503 Service Unavailable."""
        route = respx_mock.get("https://api.example.com/unavailable")
        route.side_effect = [
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(200, json={"recovered": True}),
        ]

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            result = await client.get("/unavailable")
            assert result == {"recovered": True}
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_404(self, respx_mock):
        """Client does NOT retry on 404 Not Found."""
        route = respx_mock.get("https://api.example.com/missing")
        route.mock(return_value=httpx.Response(404, text="Not Found"))

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            with pytest.raises(APIProviderError) as exc_info:
                await client.get("/missing")
            assert exc_info.value.status_code == 404
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries(self, respx_mock):
        """Client raises after exhausting all retries."""
        route = respx_mock.get("https://api.example.com/always-fail")
        route.mock(return_value=httpx.Response(503, text="Down"))

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            with pytest.raises(APIProviderError) as exc_info:
                await client.get("/always-fail")
            assert exc_info.value.status_code == 503
            # 1 initial + 3 retries = 4 total attempts
            assert route.call_count == 4

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, respx_mock):
        """Client retries on timeout exceptions."""
        route = respx_mock.get("https://api.example.com/slow")
        route.side_effect = [
            httpx.ReadTimeout("Connection timed out"),
            httpx.Response(200, json={"slow_but_ok": True}),
        ]

        async with BaseAsyncClient(base_url="https://api.example.com") as client:
            result = await client.get("/slow")
            assert result == {"slow_but_ok": True}
