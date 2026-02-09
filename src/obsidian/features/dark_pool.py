"""Dark pool features: DarkShare and Block Intensity.

These features capture institutional positioning via off-exchange execution:
- DarkShare: proportion of volume executing in dark pools
- Block Intensity: frequency/volume of large block prints
"""

import pandas as pd
import numpy as np


def compute_dark_share(data: pd.DataFrame) -> pd.Series:
    """Compute Dark Pool Share — proportion of off-exchange volume.

    Formula:
        DarkShare_t = V_dark_t / V_total_t

    Domain: [0, 1]. Values outside this range indicate data error.

    Args:
        data: DataFrame with columns: dark_volume, total_volume
              OR dark_volume, volume (volume is treated as total_volume)

    Returns:
        Series with computed dark share values. NaN where data is missing or total volume is zero.

    Raises:
        ValueError: If required columns are missing.
        Warning: If dark_share > 1.0 (data error indication)

    Example:
        >>> data = pd.DataFrame({
        ...     "dark_volume": [500000, 750000, 600000],
        ...     "total_volume": [1000000, 1500000, 1200000]
        ... })
        >>> dark_share = compute_dark_share(data)
        >>> dark_share[0]  # 500000 / 1000000 = 0.5
        0.5
    """
    # Handle column name variations
    dark_col = None
    if "dark_volume" in data.columns:
        dark_col = "dark_volume"
    elif "dark_pool_volume" in data.columns:
        dark_col = "dark_pool_volume"
    else:
        raise ValueError("Missing dark volume column (expected 'dark_volume' or 'dark_pool_volume')")

    total_col = None
    if "total_volume" in data.columns:
        total_col = "total_volume"
    elif "volume" in data.columns:
        total_col = "volume"
    else:
        raise ValueError("Missing total volume column (expected 'total_volume' or 'volume')")

    # Compute dark share
    with np.errstate(divide="ignore", invalid="ignore"):
        dark_share = data[dark_col] / data[total_col]

    # Replace inf with NaN
    dark_share = dark_share.replace([np.inf, -np.inf], np.nan)

    # Warn if dark_share > 1.0 (data error)
    invalid_mask = (dark_share > 1.0) & ~dark_share.isna()
    if invalid_mask.any():
        import warnings
        warnings.warn(
            f"DarkShare > 1.0 detected in {invalid_mask.sum()} rows. "
            "This indicates data error (dark_volume > total_volume).",
            UserWarning
        )

    return dark_share


def compute_block_intensity(
    data: pd.DataFrame,
    method: str = "count",
    threshold_percentile: float = 90.0
) -> pd.Series:
    """Compute Block Trade Intensity — frequency of large block prints.

    Block trades are prints exceeding a size threshold. Intensity can be measured as:
    - 'count': raw count of block-classified prints per day
    - 'volume': aggregate volume of block-classified prints per day
    - 'proportion': proportion of volume above threshold percentile

    Args:
        data: DataFrame with either:
              - 'block_count' or 'block_volume' column (if pre-aggregated daily data)
              - 'print_size' or 'trade_size' column (if intraday print-level data)
        method: Measurement method - 'count', 'volume', or 'proportion'
        threshold_percentile: For 'proportion' method, percentile threshold (default: 90)

    Returns:
        Series with computed block intensity values. NaN where data is missing.

    Raises:
        ValueError: If required columns are missing or method is invalid.

    Example:
        >>> # Pre-aggregated daily data
        >>> data = pd.DataFrame({
        ...     "block_count": [15, 22, 18],
        ...     "block_volume": [500000, 750000, 600000]
        ... })
        >>> intensity = compute_block_intensity(data, method="count")
        >>> intensity[1]
        22
    """
    valid_methods = ["count", "volume", "proportion"]
    if method not in valid_methods:
        raise ValueError(f"Invalid method: {method}. Must be one of {valid_methods}")

    # Method 1: Pre-aggregated block count
    if method == "count":
        if "block_count" in data.columns:
            return data["block_count"]
        elif "block_trades" in data.columns:
            return data["block_trades"]
        else:
            raise ValueError("Missing block count column (expected 'block_count' or 'block_trades')")

    # Method 2: Pre-aggregated block volume
    elif method == "volume":
        if "block_volume" in data.columns:
            return data["block_volume"]
        else:
            raise ValueError("Missing block volume column (expected 'block_volume')")

    # Method 3: Proportion above threshold (requires print-level data)
    elif method == "proportion":
        size_col = None
        if "print_size" in data.columns:
            size_col = "print_size"
        elif "trade_size" in data.columns:
            size_col = "trade_size"
        else:
            raise ValueError(
                "Missing print size column for 'proportion' method "
                "(expected 'print_size' or 'trade_size')"
            )

        # Compute threshold
        threshold = data[size_col].quantile(threshold_percentile / 100.0)

        # Proportion of volume above threshold
        large_prints = data[size_col] > threshold
        if "volume" in data.columns:
            with np.errstate(divide="ignore", invalid="ignore"):
                proportion = data.loc[large_prints, "volume"].sum() / data["volume"].sum()
        else:
            # If no volume column, use count proportion
            proportion = large_prints.sum() / len(data)

        return pd.Series([proportion] * len(data), index=data.index)

    return pd.Series([np.nan] * len(data), index=data.index)
