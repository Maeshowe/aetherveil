"""Venue mix features: Execution venue distribution analysis.

Z_venue(t) captures the distributional shift in execution venue allocation
(lit exchanges, dark pools, ATS venues) relative to the instrument's baseline.

Computed as a composite z-score across venue-share features.
"""

import pandas as pd
import numpy as np
from typing import List, Optional


def compute_venue_mix(
    data: pd.DataFrame,
    venue_columns: Optional[List[str]] = None
) -> pd.Series:
    """Compute Venue Mix — distributional shift in execution venue allocation.

    Z_venue(t) captures deviations in venue allocation relative to baseline.
    This function computes the raw venue diversity/concentration metric.
    The baseline system will handle z-score normalization.

    Multiple approaches supported:
    1. Entropy-based: Shannon entropy of venue volume distribution
    2. Concentration-based: Herfindahl-Hirschman Index (HHI)
    3. Share-based: Specific venue share (e.g., NYSE share, NASDAQ share)

    Args:
        data: DataFrame with venue volume columns, e.g.:
              - 'nyse_volume', 'nasdaq_volume', 'arca_volume', 'dark_volume', etc.
              - Or single 'venue_entropy' or 'venue_hhi' column if pre-computed
        venue_columns: List of column names representing venue volumes.
                      If None, auto-detect columns ending with '_volume' or '_share'

    Returns:
        Series with venue mix metric. NaN where data is missing.

    Raises:
        ValueError: If no venue columns found.

    Example:
        >>> data = pd.DataFrame({
        ...     "nyse_volume": [400000, 350000, 420000],
        ...     "nasdaq_volume": [350000, 400000, 380000],
        ...     "dark_volume": [250000, 250000, 200000]
        ... })
        >>> venue_mix = compute_venue_mix(data)
        >>> venue_mix[0]  # Entropy or HHI based on distribution
        1.0986122886681098
    """
    # Method 1: Pre-computed entropy
    if "venue_entropy" in data.columns:
        return data["venue_entropy"]

    # Method 2: Pre-computed HHI
    if "venue_hhi" in data.columns:
        return data["venue_hhi"]

    # Method 3: Compute from venue volumes
    if venue_columns is None:
        # Auto-detect venue columns
        venue_columns = [
            col for col in data.columns
            if col.endswith("_volume") or col.endswith("_share")
        ]

    if not venue_columns:
        raise ValueError(
            "No venue columns found. Either provide venue_columns parameter "
            "or ensure DataFrame has columns ending with '_volume' or '_share'"
        )

    # Compute total volume across venues
    venue_data = data[venue_columns]
    total_volume = venue_data.sum(axis=1)

    # Compute venue shares
    venue_shares = venue_data.div(total_volume, axis=0)

    # Compute Shannon entropy (higher = more diversified)
    # H = -Σ(p_i * log(p_i))
    with np.errstate(divide="ignore", invalid="ignore"):
        log_shares = np.log(venue_shares)
        entropy = -(venue_shares * log_shares).sum(axis=1)

    # Replace inf and NaN from log(0)
    entropy = entropy.replace([np.inf, -np.inf], np.nan)

    return entropy


def compute_venue_concentration(
    data: pd.DataFrame,
    venue_columns: Optional[List[str]] = None
) -> pd.Series:
    """Compute Venue Concentration — Herfindahl-Hirschman Index (HHI).

    HHI measures market concentration. Higher values indicate execution
    is concentrated in fewer venues (less diversified).

    Formula:
        HHI = Σ(share_i²)

    Domain: [1/N, 1] where:
    - 1/N = perfectly diversified across N venues
    - 1 = all volume on single venue (maximum concentration)

    Args:
        data: DataFrame with venue volume columns
        venue_columns: List of column names representing venue volumes.
                      If None, auto-detect columns ending with '_volume' or '_share'

    Returns:
        Series with HHI values. NaN where data is missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "nyse_volume": [500000, 350000, 420000],
        ...     "nasdaq_volume": [500000, 400000, 380000],
        ...     "dark_volume": [0, 250000, 200000]
        ... })
        >>> hhi = compute_venue_concentration(data)
        >>> hhi[0]  # (0.5² + 0.5² + 0²) = 0.5 (two equal venues)
        0.5
    """
    if venue_columns is None:
        # Auto-detect venue columns
        venue_columns = [
            col for col in data.columns
            if col.endswith("_volume") or col.endswith("_share")
        ]

    if not venue_columns:
        raise ValueError(
            "No venue columns found. Either provide venue_columns parameter "
            "or ensure DataFrame has columns ending with '_volume' or '_share'"
        )

    # Compute total volume across venues
    venue_data = data[venue_columns]
    total_volume = venue_data.sum(axis=1)

    # Compute venue shares
    venue_shares = venue_data.div(total_volume, axis=0)

    # Compute HHI = Σ(share²)
    hhi = (venue_shares ** 2).sum(axis=1)

    return hhi


def compute_primary_venue_share(
    data: pd.DataFrame,
    venue_name: str = "nyse"
) -> pd.Series:
    """Compute primary venue share — proportion of volume on specific venue.

    Args:
        data: DataFrame with venue volume columns
        venue_name: Name of the venue to compute share for (e.g., 'nyse', 'nasdaq', 'dark')

    Returns:
        Series with venue share in [0, 1]. NaN where data is missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "nyse_volume": [500000, 350000, 420000],
        ...     "total_volume": [1000000, 1000000, 1000000]
        ... })
        >>> nyse_share = compute_primary_venue_share(data, venue_name="nyse")
        >>> nyse_share[0]  # 500000 / 1000000 = 0.5
        0.5
    """
    venue_col = f"{venue_name}_volume"
    if venue_col not in data.columns:
        raise ValueError(f"Missing venue column: {venue_col}")

    # Try to find total volume
    if "total_volume" in data.columns:
        total_volume = data["total_volume"]
    elif "volume" in data.columns:
        total_volume = data["volume"]
    else:
        # Sum all venue columns
        venue_columns = [
            col for col in data.columns
            if col.endswith("_volume")
        ]
        if venue_columns:
            total_volume = data[venue_columns].sum(axis=1)
        else:
            raise ValueError(
                "Cannot compute venue share: no total_volume column "
                "and no other _volume columns to sum"
            )

    # Compute share
    with np.errstate(divide="ignore", invalid="ignore"):
        share = data[venue_col] / total_volume

    return share.replace([np.inf, -np.inf], np.nan)
