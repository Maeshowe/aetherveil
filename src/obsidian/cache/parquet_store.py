"""Parquet-based raw data cache with instrument isolation.

Provides append-only, immutable storage of daily market data in columnar Parquet
format. Each instrument's data is stored separately to enforce baseline isolation.

Storage structure:
    data/{ticker}/raw/{source}_{date}.parquet

Example:
    data/AAPL/raw/polygon_2024-01-15.parquet
    data/AAPL/raw/unusual_whales_2024-01-15.parquet

All I/O operations are async-compatible using asyncio.to_thread for non-blocking
execution.
"""

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class ParquetStore:
    """Async Parquet cache for raw market data.

    Stores daily snapshots in instrument-isolated directories with immutable
    append-only semantics. Never overwrites existing files.

    Args:
        base_path: Root directory for cache. Defaults to 'data/'.
    """

    def __init__(self, base_path: str | Path = "data") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, ticker: str, source: str, dt: date) -> Path:
        """Generate file path for a given ticker/source/date.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            source: Data source identifier (e.g., "polygon", "unusual_whales")
            dt: Trading date

        Returns:
            Path object for the parquet file
        """
        ticker_upper = ticker.upper()
        date_str = dt.isoformat()  # YYYY-MM-DD
        filename = f"{source}_{date_str}.parquet"
        return self.base_path / ticker_upper / "raw" / filename

    async def write(
        self,
        ticker: str,
        source: str,
        dt: date,
        data: pd.DataFrame,
        overwrite: bool = False,
    ) -> Path:
        """Write DataFrame to Parquet cache.

        Args:
            ticker: Stock ticker symbol
            source: Data source identifier
            dt: Trading date
            data: DataFrame to store
            overwrite: If False (default), raises error if file exists.
                      If True, overwrites existing file (use with caution).

        Returns:
            Path to the written file

        Raises:
            FileExistsError: If file exists and overwrite=False
            ValueError: If data is empty
        """
        if data.empty:
            raise ValueError("Cannot write empty DataFrame to cache")

        file_path = self._get_file_path(ticker, source, dt)

        # Check for existing file
        if file_path.exists() and not overwrite:
            raise FileExistsError(
                f"Cache file already exists: {file_path}. "
                "Use overwrite=True to replace (not recommended)."
            )

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to Parquet (async via to_thread)
        def _write() -> None:
            table = pa.Table.from_pandas(data)
            pq.write_table(
                table,
                file_path,
                compression="snappy",  # Fast compression
                use_dictionary=True,  # Efficient for repeated values
                write_statistics=True,  # Enable column statistics
            )

        await asyncio.to_thread(_write)
        return file_path

    async def read(
        self,
        ticker: str,
        source: str,
        dt: date,
    ) -> pd.DataFrame | None:
        """Read a single day's data from cache.

        Args:
            ticker: Stock ticker symbol
            source: Data source identifier
            dt: Trading date

        Returns:
            DataFrame if file exists, None otherwise
        """
        file_path = self._get_file_path(ticker, source, dt)

        if not file_path.exists():
            return None

        def _read() -> pd.DataFrame | None:
            try:
                table = pq.read_table(file_path)
                return table.to_pandas()
            except Exception as e:
                logger.warning(
                    "Failed to read cache file %s: %s. "
                    "File may be corrupted — returning None.",
                    file_path, e,
                )
                return None

        return await asyncio.to_thread(_read)

    async def read_range(
        self,
        ticker: str,
        source: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Read a date range from cache and concatenate.

        Args:
            ticker: Stock ticker symbol
            source: Data source identifier
            start_date: First date (inclusive)
            end_date: Last date (inclusive)

        Returns:
            Concatenated DataFrame. Empty if no files found.
        """
        available_dates = await self.list_dates(ticker, source)

        # Filter dates within range
        dates_in_range = [
            d for d in available_dates if start_date <= d <= end_date
        ]

        if not dates_in_range:
            return pd.DataFrame()

        # Read all files in parallel
        tasks = [self.read(ticker, source, d) for d in dates_in_range]
        dataframes = await asyncio.gather(*tasks)

        # Filter out None and concatenate
        valid_dfs = [df for df in dataframes if df is not None]
        if not valid_dfs:
            return pd.DataFrame()

        return pd.concat(valid_dfs, ignore_index=True)

    async def exists(self, ticker: str, source: str, dt: date) -> bool:
        """Check if a cache file exists.

        Args:
            ticker: Stock ticker symbol
            source: Data source identifier
            dt: Trading date

        Returns:
            True if file exists, False otherwise
        """
        file_path = self._get_file_path(ticker, source, dt)
        return await asyncio.to_thread(file_path.exists)

    async def list_dates(self, ticker: str, source: str) -> list[date]:
        """List all available dates for a ticker/source combination.

        Args:
            ticker: Stock ticker symbol
            source: Data source identifier

        Returns:
            Sorted list of dates (ascending)
        """
        ticker_upper = ticker.upper()
        raw_dir = self.base_path / ticker_upper / "raw"

        if not raw_dir.exists():
            return []

        def _list() -> list[date]:
            dates = []
            pattern = f"{source}_*.parquet"
            for file_path in raw_dir.glob(pattern):
                # Extract date from filename: source_YYYY-MM-DD.parquet
                # Use rsplit to handle source names with underscores
                try:
                    date_str = file_path.stem.rsplit("_", 1)[1]  # Last part after _
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                    dates.append(dt)
                except (ValueError, IndexError):
                    # Skip malformed filenames
                    continue
            return sorted(dates)

        return await asyncio.to_thread(_list)

    async def list_sources(self, ticker: str) -> list[str]:
        """List all data sources available for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Sorted list of source identifiers
        """
        ticker_upper = ticker.upper()
        raw_dir = self.base_path / ticker_upper / "raw"

        if not raw_dir.exists():
            return []

        def _list() -> list[str]:
            sources = set()
            for file_path in raw_dir.glob("*.parquet"):
                # Extract source from filename: source_YYYY-MM-DD.parquet
                # Use rsplit to handle source names with underscores
                try:
                    source = file_path.stem.rsplit("_", 1)[0]  # Everything before last _
                    sources.add(source)
                except (ValueError, IndexError):
                    continue
            return sorted(sources)

        return await asyncio.to_thread(_list)

    async def get_cache_stats(self, ticker: str) -> dict[str, Any]:
        """Get cache statistics for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with cache statistics:
                - sources: Number of unique data sources
                - total_files: Total number of parquet files
                - size_bytes: Total size on disk
                - date_range: (earliest_date, latest_date) or None
        """
        ticker_upper = ticker.upper()
        raw_dir = self.base_path / ticker_upper / "raw"

        if not raw_dir.exists():
            return {
                "sources": 0,
                "total_files": 0,
                "size_bytes": 0,
                "date_range": None,
            }

        def _stats() -> dict[str, Any]:
            files = list(raw_dir.glob("*.parquet"))
            total_size = sum(f.stat().st_size for f in files)

            sources = set()
            dates = []
            for file_path in files:
                try:
                    # Use rsplit to handle source names with underscores
                    parts = file_path.stem.rsplit("_", 1)
                    source = parts[0]
                    date_str = parts[1]
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                    sources.add(source)
                    dates.append(dt)
                except (ValueError, IndexError):
                    continue

            date_range = None
            if dates:
                date_range = (min(dates), max(dates))

            return {
                "sources": len(sources),
                "total_files": len(files),
                "size_bytes": total_size,
                "date_range": date_range,
            }

        return await asyncio.to_thread(_stats)
