"""Fetcher — API → Parquet Cache.

Coordinates async API calls and stores raw data in Parquet cache.
Handles rate limiting, retries, and graceful degradation.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from obsidian.config import settings
from obsidian.clients import UnusualWhalesClient, PolygonClient, FMPClient
from obsidian.cache import ParquetStore

logger = logging.getLogger(__name__)


class Fetcher:
    """Fetches raw data from APIs and stores in Parquet cache.

    Uses settings for API keys and rate limits. Clients are created
    as async context managers per fetch operation.

    Usage:
        fetcher = Fetcher()

        # Fetch data for multiple tickers
        results = await fetcher.fetch_all(
            tickers={"SPY", "AAPL"},
            target_date=date(2024, 1, 15)
        )

        # Check what succeeded
        for ticker, status in results.items():
            print(f"{ticker}: {status}")
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        """Initialize fetcher with cache store.

        Args:
            cache_dir: Directory for Parquet cache (default: from settings)
        """
        self.cache = ParquetStore(base_path=cache_dir or settings.cache_dir)
        # Limit concurrent UW fetches to avoid 429 rate-limit errors.
        # Each ticker makes 3 sequential UW calls, so uw_concurrency=3
        # means max 3 concurrent UW request streams.
        self._uw_semaphore = asyncio.Semaphore(settings.uw_concurrency)

    async def fetch_ticker(
        self,
        ticker: str,
        target_date: date,
        lookback_days: int = 100
    ) -> dict[str, bool]:
        """Fetch all data sources for a single ticker.

        Fetches dark pool prints, Greek exposures, price bars, and quotes.
        Each source is stored independently in the Parquet cache.

        Args:
            ticker: Symbol to fetch
            target_date: Date to fetch data for
            lookback_days: How many days of history to fetch (default: 100)

        Returns:
            Dictionary mapping source → success status
        """
        ticker = ticker.upper()
        results: dict[str, bool] = {}
        start_date = target_date - timedelta(days=lookback_days)

        # --- Unusual Whales: Dark Pool + Greeks + IV ---
        # Semaphore limits concurrent UW fetches across all tickers
        async with self._uw_semaphore, UnusualWhalesClient(
            api_key=settings.uw_api_key,
            rate_limit=settings.uw_rate_limit
        ) as uw:
            # Dark pool recent prints
            # NOTE: UW /darkpool/recent only returns the latest day's prints
            # regardless of date_from/date_to. Historical dark pool data
            # accumulates over daily runs (21+ days for valid baseline).
            try:
                resp = await uw.get_dark_pool_recent(
                    ticker=ticker,
                    limit=200,
                    date_from=start_date,
                    date_to=target_date
                )
                data = resp.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    # Use actual data date (from executed_at) as cache key
                    # so daily runs accumulate history naturally
                    actual_date = target_date
                    if "executed_at" in df.columns:
                        try:
                            actual_date = pd.to_datetime(
                                df["executed_at"].iloc[0]
                            ).date()
                        except Exception:
                            pass
                    await self.cache.write(
                        ticker=ticker, source="dark_pool",
                        dt=actual_date, data=df, overwrite=True
                    )
                    results["dark_pool"] = True
                    logger.info(
                        "%s: dark_pool — %d records (actual date: %s)",
                        ticker, len(data), actual_date.isoformat(),
                    )
                else:
                    results["dark_pool"] = False
                    logger.warning(f"{ticker}: dark_pool — no data returned")
            except Exception as e:
                logger.warning(f"{ticker}: dark_pool FAILED — {e}")
                results["dark_pool"] = False

            # Greek exposure (GEX, DEX, Vanna, Charm)
            try:
                resp = await uw.get_greek_exposure(
                    ticker=ticker,
                    date_from=start_date,
                    date_to=target_date
                )
                data = resp.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    await self.cache.write(
                        ticker=ticker, source="greeks",
                        dt=target_date, data=df, overwrite=True
                    )
                    results["greeks"] = True
                    logger.info(f"{ticker}: greeks — {len(data)} records")
                else:
                    results["greeks"] = False
                    logger.warning(f"{ticker}: greeks — no data returned")
            except Exception as e:
                logger.warning(f"{ticker}: greeks FAILED — {e}")
                results["greeks"] = False

            # IV Rank
            try:
                resp = await uw.get_iv_rank(
                    ticker=ticker,
                    date_from=start_date,
                    date_to=target_date
                )
                data = resp.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    await self.cache.write(
                        ticker=ticker, source="iv_rank",
                        dt=target_date, data=df, overwrite=True
                    )
                    results["iv_rank"] = True
                    logger.info(f"{ticker}: iv_rank — {len(data)} records")
                else:
                    results["iv_rank"] = False
                    logger.warning(f"{ticker}: iv_rank — no data returned")
            except Exception as e:
                logger.warning(f"{ticker}: iv_rank FAILED — {e}")
                results["iv_rank"] = False

        # --- Polygon: Price Bars ---
        async with PolygonClient(
            api_key=settings.polygon_api_key,
            rate_limit=settings.polygon_rate_limit
        ) as polygon:
            try:
                resp = await polygon.get_daily_bars(
                    ticker=ticker,
                    date_from=start_date,
                    date_to=target_date
                )
                bars = resp.get("results", [])
                if bars:
                    df = pd.DataFrame(bars)
                    await self.cache.write(
                        ticker=ticker, source="bars",
                        dt=target_date, data=df, overwrite=True
                    )
                    results["bars"] = True
                    logger.info(f"{ticker}: bars — {len(bars)} records")
                else:
                    results["bars"] = False
                    logger.warning(f"{ticker}: bars — no data returned")
            except Exception as e:
                logger.warning(f"{ticker}: bars FAILED — {e}")
                results["bars"] = False

        # --- FMP: Quote ---
        async with FMPClient(
            api_key=settings.fmp_api_key,
            rate_limit=settings.fmp_rate_limit
        ) as fmp:
            try:
                resp = await fmp.get_quote(ticker)
                if resp and isinstance(resp, list) and len(resp) > 0:
                    df = pd.DataFrame(resp)
                    df["fetch_date"] = target_date.isoformat()
                    await self.cache.write(
                        ticker=ticker, source="quote",
                        dt=target_date, data=df, overwrite=True
                    )
                    results["quote"] = True
                    logger.info(f"{ticker}: quote — fetched")
                else:
                    results["quote"] = False
                    logger.warning(f"{ticker}: quote — no data returned")
            except Exception as e:
                logger.warning(f"{ticker}: quote FAILED — {e}")
                results["quote"] = False

        return results

    async def fetch_all(
        self,
        tickers: set[str],
        target_date: date,
        lookback_days: int = 100
    ) -> dict[str, dict[str, bool]]:
        """Fetch data for multiple tickers concurrently.

        Each ticker creates its own ephemeral API clients. UW requests
        are throttled by a shared semaphore (uw_concurrency) to avoid
        429 rate-limit errors. Polygon/FMP calls run freely in parallel.

        Args:
            tickers: Set of ticker symbols
            target_date: Date to fetch data for
            lookback_days: How many days of history (default: 100)

        Returns:
            Dictionary mapping ticker → source → success status
        """
        _fail = {
            "dark_pool": False, "greeks": False,
            "bars": False, "iv_rank": False, "quote": False
        }

        async def _fetch_one(ticker: str) -> tuple[str, dict[str, bool]]:
            try:
                return ticker, await self.fetch_ticker(ticker, target_date, lookback_days)
            except Exception as e:
                logger.error("Failed to fetch %s: %s", ticker, e)
                return ticker, dict(_fail)

        tasks = [_fetch_one(t) for t in sorted(tickers)]
        completed = await asyncio.gather(*tasks)
        return dict(completed)
