"""Tests for ParquetStore — immutable cache with instrument isolation."""

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from obsidian.cache import ParquetStore


@pytest.fixture
def temp_cache(tmp_path: Path) -> ParquetStore:
    """Create a temporary ParquetStore for testing."""
    return ParquetStore(base_path=tmp_path / "cache")


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Sample market data for testing."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-15 09:30", periods=5, freq="1h"),
        "price": [150.0, 151.5, 150.8, 152.0, 151.2],
        "volume": [1000, 1500, 1200, 1800, 1100],
    })


class TestParquetStoreBasics:
    """Test basic read/write operations."""

    @pytest.mark.asyncio
    async def test_cold_start_empty_cache(self, temp_cache: ParquetStore) -> None:
        """Empty cache returns None for non-existent files."""
        result = await temp_cache.read("AAPL", "polygon", date(2024, 1, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_write_and_read(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Write data and read it back."""
        dt = date(2024, 1, 15)
        file_path = await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Verify file was created
        assert file_path.exists()
        assert "AAPL" in str(file_path)
        assert "polygon_2024-01-15.parquet" in str(file_path)

        # Read back and verify
        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is not None
        pd.testing.assert_frame_equal(result, sample_data)

    @pytest.mark.asyncio
    async def test_ticker_uppercased(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Ticker symbols are automatically uppercased."""
        dt = date(2024, 1, 15)
        await temp_cache.write("aapl", "polygon", dt, sample_data)

        # Should be readable with uppercase
        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is not None

        # Should be readable with lowercase
        result = await temp_cache.read("aapl", "polygon", dt)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_on_empty_dataframe(self, temp_cache: ParquetStore) -> None:
        """Cannot write empty DataFrame."""
        empty_df = pd.DataFrame()
        with pytest.raises(ValueError, match="Cannot write empty DataFrame"):
            await temp_cache.write("AAPL", "polygon", date(2024, 1, 15), empty_df)

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_write(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Duplicate writes raise FileExistsError by default."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Second write should fail
        with pytest.raises(FileExistsError, match="Cache file already exists"):
            await temp_cache.write("AAPL", "polygon", dt, sample_data)

    @pytest.mark.asyncio
    async def test_overwrite_flag_allows_replacement(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """overwrite=True allows replacing existing files."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Modify data
        modified_data = sample_data.copy()
        modified_data["price"] = modified_data["price"] * 2

        # Overwrite
        await temp_cache.write("AAPL", "polygon", dt, modified_data, overwrite=True)

        # Verify overwritten data
        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is not None
        pd.testing.assert_frame_equal(result, modified_data)


class TestInstrumentIsolation:
    """Test that each instrument has isolated storage."""

    @pytest.mark.asyncio
    async def test_different_tickers_isolated(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Different tickers store data independently."""
        dt = date(2024, 1, 15)

        # Write to AAPL
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Write to MSFT
        modified_data = sample_data.copy()
        modified_data["price"] = modified_data["price"] * 2
        await temp_cache.write("MSFT", "polygon", dt, modified_data)

        # Verify AAPL data unchanged
        aapl_data = await temp_cache.read("AAPL", "polygon", dt)
        assert aapl_data is not None
        pd.testing.assert_frame_equal(aapl_data, sample_data)

        # Verify MSFT data correct
        msft_data = await temp_cache.read("MSFT", "polygon", dt)
        assert msft_data is not None
        pd.testing.assert_frame_equal(msft_data, modified_data)

    @pytest.mark.asyncio
    async def test_different_sources_isolated(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Different sources for same ticker are isolated."""
        dt = date(2024, 1, 15)

        # Write polygon data
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Write unusual_whales data
        uw_data = sample_data.copy()
        uw_data["dark_volume"] = [100, 150, 120, 180, 110]
        await temp_cache.write("AAPL", "unusual_whales", dt, uw_data)

        # Verify polygon data unchanged
        polygon_data = await temp_cache.read("AAPL", "polygon", dt)
        assert polygon_data is not None
        assert "dark_volume" not in polygon_data.columns

        # Verify unusual_whales data correct
        uw_result = await temp_cache.read("AAPL", "unusual_whales", dt)
        assert uw_result is not None
        pd.testing.assert_frame_equal(uw_result, uw_data)


class TestDateRangeQueries:
    """Test reading multiple dates at once."""

    @pytest.mark.asyncio
    async def test_read_range_single_day(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Read range with single day returns that day's data."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        result = await temp_cache.read_range("AAPL", "polygon", dt, dt)
        assert not result.empty
        pd.testing.assert_frame_equal(result, sample_data)

    @pytest.mark.asyncio
    async def test_read_range_multiple_days(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Read range concatenates multiple days."""
        dates = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]

        for dt in dates:
            data = sample_data.copy()
            data["date"] = dt
            await temp_cache.write("AAPL", "polygon", dt, data)

        result = await temp_cache.read_range(
            "AAPL", "polygon", dates[0], dates[-1]
        )
        assert len(result) == len(sample_data) * 3
        assert result["date"].nunique() == 3

    @pytest.mark.asyncio
    async def test_read_range_empty_when_no_files(
        self, temp_cache: ParquetStore
    ) -> None:
        """Read range returns empty DataFrame when no files exist."""
        result = await temp_cache.read_range(
            "AAPL", "polygon", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert result.empty

    @pytest.mark.asyncio
    async def test_read_range_filters_dates(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Read range only includes dates within the specified range."""
        dates = [
            date(2024, 1, 10),  # Before range
            date(2024, 1, 15),  # In range
            date(2024, 1, 20),  # In range
            date(2024, 1, 25),  # After range
        ]

        for dt in dates:
            data = sample_data.copy()
            data["date"] = dt
            await temp_cache.write("AAPL", "polygon", dt, data)

        # Query range: 2024-01-15 to 2024-01-20
        result = await temp_cache.read_range(
            "AAPL", "polygon", date(2024, 1, 15), date(2024, 1, 20)
        )

        assert len(result) == len(sample_data) * 2  # Only 2 days
        assert result["date"].nunique() == 2
        assert date(2024, 1, 10) not in result["date"].values
        assert date(2024, 1, 25) not in result["date"].values


class TestListingAndMetadata:
    """Test listing available dates and sources."""

    @pytest.mark.asyncio
    async def test_list_dates_empty(self, temp_cache: ParquetStore) -> None:
        """list_dates returns empty list for non-existent ticker."""
        dates = await temp_cache.list_dates("AAPL", "polygon")
        assert dates == []

    @pytest.mark.asyncio
    async def test_list_dates_single(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """list_dates returns single date."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        dates = await temp_cache.list_dates("AAPL", "polygon")
        assert dates == [dt]

    @pytest.mark.asyncio
    async def test_list_dates_sorted(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """list_dates returns dates in ascending order."""
        dates = [date(2024, 1, 20), date(2024, 1, 15), date(2024, 1, 18)]

        # Write in random order
        for dt in dates:
            await temp_cache.write("AAPL", "polygon", dt, sample_data)

        result = await temp_cache.list_dates("AAPL", "polygon")
        assert result == sorted(dates)

    @pytest.mark.asyncio
    async def test_list_dates_filters_by_source(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """list_dates only returns dates for specified source."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)
        await temp_cache.write("AAPL", "unusual_whales", dt, sample_data)

        polygon_dates = await temp_cache.list_dates("AAPL", "polygon")
        uw_dates = await temp_cache.list_dates("AAPL", "unusual_whales")

        assert polygon_dates == [dt]
        assert uw_dates == [dt]

    @pytest.mark.asyncio
    async def test_list_sources_empty(self, temp_cache: ParquetStore) -> None:
        """list_sources returns empty list for non-existent ticker."""
        sources = await temp_cache.list_sources("AAPL")
        assert sources == []

    @pytest.mark.asyncio
    async def test_list_sources_multiple(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """list_sources returns all unique sources."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)
        await temp_cache.write("AAPL", "unusual_whales", dt, sample_data)
        await temp_cache.write("AAPL", "fmp", dt, sample_data)

        sources = await temp_cache.list_sources("AAPL")
        assert sorted(sources) == ["fmp", "polygon", "unusual_whales"]

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """exists() returns True for existing files."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        assert await temp_cache.exists("AAPL", "polygon", dt) is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing(
        self, temp_cache: ParquetStore
    ) -> None:
        """exists() returns False for non-existent files."""
        assert await temp_cache.exists("AAPL", "polygon", date(2024, 1, 15)) is False


class TestCacheStats:
    """Test cache statistics aggregation."""

    @pytest.mark.asyncio
    async def test_stats_empty_cache(self, temp_cache: ParquetStore) -> None:
        """Stats for empty cache return zeros."""
        stats = await temp_cache.get_cache_stats("AAPL")
        assert stats["sources"] == 0
        assert stats["total_files"] == 0
        assert stats["size_bytes"] == 0
        assert stats["date_range"] is None

    @pytest.mark.asyncio
    async def test_stats_single_file(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Stats for single file."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        stats = await temp_cache.get_cache_stats("AAPL")
        assert stats["sources"] == 1
        assert stats["total_files"] == 1
        assert stats["size_bytes"] > 0
        assert stats["date_range"] == (dt, dt)

    @pytest.mark.asyncio
    async def test_stats_multiple_sources_and_dates(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Stats aggregates across sources and dates."""
        dates = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]
        sources = ["polygon", "unusual_whales"]

        for src in sources:
            for dt in dates:
                await temp_cache.write("AAPL", src, dt, sample_data)

        stats = await temp_cache.get_cache_stats("AAPL")
        assert stats["sources"] == 2
        assert stats["total_files"] == 6  # 2 sources × 3 dates
        assert stats["size_bytes"] > 0
        assert stats["date_range"] == (dates[0], dates[-1])


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_dataframe_with_nan_values(
        self, temp_cache: ParquetStore
    ) -> None:
        """DataFrames with NaN values are preserved."""
        data = pd.DataFrame({
            "price": [100.0, None, 102.0, None, 103.0],
            "volume": [1000, 1500, None, 1800, None],
        })

        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, data)

        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is not None
        pd.testing.assert_frame_equal(result, data)

    @pytest.mark.asyncio
    async def test_dataframe_with_datetime_index(
        self, temp_cache: ParquetStore
    ) -> None:
        """DataFrames with datetime index are preserved."""
        data = pd.DataFrame({
            "price": [100.0, 101.0, 102.0],
            "volume": [1000, 1500, 1200],
        }, index=pd.date_range("2024-01-15", periods=3, freq="D"))

        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, data)

        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is not None
        # Check values and index, but ignore frequency attribute
        # (Parquet may not preserve DatetimeIndex frequency)
        pd.testing.assert_frame_equal(result, data, check_freq=False)

    @pytest.mark.asyncio
    async def test_concurrent_reads(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Multiple concurrent reads work correctly."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Concurrent reads
        results = await asyncio.gather(*[
            temp_cache.read("AAPL", "polygon", dt) for _ in range(10)
        ])

        assert all(r is not None for r in results)
        for result in results:
            pd.testing.assert_frame_equal(result, sample_data)

    @pytest.mark.asyncio
    async def test_malformed_filenames_ignored(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Malformed filenames are ignored during listing."""
        dt = date(2024, 1, 15)
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Create malformed file manually
        raw_dir = temp_cache.base_path / "AAPL" / "raw"
        (raw_dir / "malformed.parquet").touch()
        (raw_dir / "no_date_separator.parquet").touch()

        # Should still work
        dates = await temp_cache.list_dates("AAPL", "polygon")
        assert dates == [dt]

        sources = await temp_cache.list_sources("AAPL")
        assert "polygon" in sources


class TestCorruptedFiles:
    """Test resilience to corrupted parquet files."""

    @pytest.mark.asyncio
    async def test_corrupted_file_returns_none(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """Reading a corrupted parquet file returns None instead of crashing."""
        dt = date(2024, 1, 15)
        # Write valid data first to create directory structure
        await temp_cache.write("AAPL", "polygon", dt, sample_data)

        # Corrupt the file by overwriting with garbage
        file_path = temp_cache._get_file_path("AAPL", "polygon", dt)
        file_path.write_bytes(b"THIS IS NOT A VALID PARQUET FILE")

        result = await temp_cache.read("AAPL", "polygon", dt)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_range_skips_corrupted(
        self, temp_cache: ParquetStore, sample_data: pd.DataFrame
    ) -> None:
        """read_range skips corrupted files and returns valid ones."""
        dates = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]

        for dt in dates:
            data = sample_data.copy()
            data["date_col"] = dt
            await temp_cache.write("AAPL", "polygon", dt, data)

        # Corrupt the middle file
        mid_path = temp_cache._get_file_path("AAPL", "polygon", dates[1])
        mid_path.write_bytes(b"CORRUPTED")

        result = await temp_cache.read_range(
            "AAPL", "polygon", dates[0], dates[-1]
        )
        # Should have data from 2 valid days, not 3
        assert len(result) == len(sample_data) * 2
