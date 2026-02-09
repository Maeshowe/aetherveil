"""Parquet-based raw data cache for OBSIDIAN MM.

Immutable, instrument-isolated storage of daily market data snapshots.
"""

from obsidian.cache.parquet_store import ParquetStore

__all__ = ["ParquetStore"]
