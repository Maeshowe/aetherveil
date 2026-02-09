"""Base async HTTP client with rate limiting and connection pooling.

All API clients inherit from this base to ensure consistent behavior:
- Async/await for non-blocking I/O
- Connection pooling for performance
- Rate limiting to respect API quotas
- Automatic retries with exponential backoff
- Proper error handling and logging

Usage:
    class MyAPIClient(BaseAsyncClient):
        def __init__(self, api_key: str, rate_limit: int = 10):
            super().__init__(
                base_url="https://api.example.com",
                headers={"Authorization": f"Bearer {api_key}"},
                rate_limit=rate_limit
            )

        async def get_data(self, symbol: str) -> dict:
            return await self._request("GET", f"/data/{symbol}")
"""

import asyncio
import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)

# Retry configuration
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds


class RateLimiter:
    """Token bucket rate limiter for async operations.

    Ensures we don't exceed API rate limits using a token bucket algorithm.
    Thread-safe for async operations.

    Args:
        rate: Maximum requests per second
    """

    def __init__(self, rate: int) -> None:
        self.rate = rate
        self.tokens = rate
        self.updated_at: float = 0.0
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            loop = asyncio.get_running_loop()

            if not self._initialized:
                self.updated_at = loop.time()
                self._initialized = True

            while self.tokens < 1:
                now = loop.time()
                elapsed = now - self.updated_at
                self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
                self.updated_at = now

                if self.tokens < 1:
                    wait_time = (1 - self.tokens) / self.rate
                    await asyncio.sleep(wait_time)

            self.tokens -= 1
            self.updated_at = loop.time()


class APIProviderError(Exception):
    """Base exception for API provider errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BaseAsyncClient:
    """Base async HTTP client with rate limiting and connection pooling.

    Provides a foundation for all API clients with consistent error handling,
    rate limiting, and logging.

    Args:
        base_url: Base URL for all API requests
        headers: Default headers for all requests
        rate_limit: Maximum requests per second (default: 10)
        timeout: Request timeout in seconds (default: 30)
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        rate_limit: int = 10,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._rate_limiter = RateLimiter(rate=rate_limit)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseAsyncClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with rate limiting, retries, and error handling.

        Retries on transient failures (429, 502, 503, 504, timeouts, network
        errors) with exponential backoff. Non-retryable errors raise immediately.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (relative to base_url)
            params: Query parameters
            json_data: JSON body for POST/PUT requests

        Returns:
            Parsed JSON response as dictionary

        Raises:
            APIProviderError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        last_error: APIProviderError | None = None

        for attempt in range(_MAX_RETRIES + 1):
            # Rate limit before each attempt
            await self._rate_limiter.acquire()

            logger.debug(
                "%s %s%s params=%s (attempt %d/%d)",
                method, self.base_url, endpoint, params, attempt + 1, _MAX_RETRIES + 1,
            )

            try:
                response = await self._client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json_data,
                )

                logger.debug("Response: %d for %s", response.status_code, endpoint)

                # Handle HTTP errors
                if response.status_code >= 400:
                    error_body = response.text[:500]

                    # Retry on transient status codes
                    if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                        backoff = _BASE_BACKOFF * (2 ** attempt)
                        logger.warning(
                            "Retryable %d for %s, retrying in %.1fs (attempt %d/%d)",
                            response.status_code, endpoint, backoff,
                            attempt + 1, _MAX_RETRIES + 1,
                        )
                        last_error = APIProviderError(
                            message=f"API request failed: {response.status_code}",
                            status_code=response.status_code,
                            response_body=error_body,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    logger.error(
                        "API error: %d %s - %s",
                        response.status_code, endpoint, error_body,
                    )
                    raise APIProviderError(
                        message=f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response_body=error_body,
                    )

                # Parse JSON response
                try:
                    return response.json()
                except Exception as e:
                    logger.error("Failed to parse JSON response: %s", e)
                    raise APIProviderError(
                        message=f"Invalid JSON response: {e}",
                        status_code=response.status_code,
                        response_body=response.text[:500],
                    )

            except httpx.TimeoutException as e:
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "Timeout for %s, retrying in %.1fs (attempt %d/%d)",
                        endpoint, backoff, attempt + 1, _MAX_RETRIES + 1,
                    )
                    last_error = APIProviderError(f"Request timeout: {e}")
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Request timeout for %s: %s", endpoint, e)
                raise APIProviderError(f"Request timeout: {e}")

            except httpx.NetworkError as e:
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "Network error for %s, retrying in %.1fs (attempt %d/%d)",
                        endpoint, backoff, attempt + 1, _MAX_RETRIES + 1,
                    )
                    last_error = APIProviderError(f"Network error: {e}")
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Network error for %s: %s", endpoint, e)
                raise APIProviderError(f"Network error: {e}")

            except APIProviderError:
                raise

            except Exception as e:
                logger.error("Unexpected error for %s: %s", endpoint, e)
                raise APIProviderError(f"Unexpected error: {e}")

        # Exhausted retries
        raise last_error or APIProviderError("Request failed after retries")

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convenience method for GET requests."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convenience method for POST requests."""
        return await self._request("POST", endpoint, params=params, json_data=json_data)
