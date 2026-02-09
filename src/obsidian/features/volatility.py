"""Volatility features: IV Skew and IV Rank.

These features capture deviations in the implied volatility surface:
- IV Skew: Put-call skew deviation from rolling baseline
- IV Rank: Percentile rank of current IV relative to historical range
"""

import pandas as pd
import numpy as np


def compute_iv_skew(data: pd.DataFrame) -> pd.Series:
    """Compute IV Skew — put-call implied volatility skew.

    Z_IV(t) captures deviations in the implied volatility surface:
    - Put-call skew deviation from rolling baseline
    - Near-term vs. far-term IV ratio deviation

    This function computes the raw skew value. The baseline system will
    handle z-score normalization.

    Args:
        data: DataFrame with one of:
              - 'iv_skew' column (pre-computed skew)
              - 'put_iv' and 'call_iv' columns (ATM or specific strike)
              - 'iv_30d_put' and 'iv_30d_call' columns

    Returns:
        Series with IV skew values. NaN where data is missing.

    Raises:
        ValueError: If required columns are missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "put_iv": [0.35, 0.42, 0.38],
        ...     "call_iv": [0.30, 0.35, 0.32]
        ... })
        >>> skew = compute_iv_skew(data)
        >>> skew[0]  # 0.35 - 0.30 = 0.05 (puts more expensive)
        0.05
    """
    # Method 1: Pre-computed skew
    if "iv_skew" in data.columns:
        return data["iv_skew"]

    # Method 2: Compute from put/call IV
    elif "put_iv" in data.columns and "call_iv" in data.columns:
        # Skew = Put IV - Call IV (positive = puts more expensive)
        return data["put_iv"] - data["call_iv"]

    # Method 3: 30-day IV convention
    elif "iv_30d_put" in data.columns and "iv_30d_call" in data.columns:
        return data["iv_30d_put"] - data["iv_30d_call"]

    # Method 4: ATM put/call IV
    elif "atm_put_iv" in data.columns and "atm_call_iv" in data.columns:
        return data["atm_put_iv"] - data["atm_call_iv"]

    else:
        raise ValueError(
            "Missing IV skew data. Expected one of: 'iv_skew', "
            "'put_iv' and 'call_iv', 'iv_30d_put' and 'iv_30d_call', "
            "or 'atm_put_iv' and 'atm_call_iv'"
        )


def compute_iv_rank(
    data: pd.DataFrame,
    window: int = 252
) -> pd.Series:
    """Compute IV Rank — percentile rank of current IV.

    IV Rank measures where the current implied volatility sits relative to
    its historical range over a lookback window.

    Formula:
        IV_Rank = (Current_IV - Min_IV) / (Max_IV - Min_IV)

    Domain: [0, 1] where:
    - 0 = current IV at historical low
    - 1 = current IV at historical high
    - 0.5 = current IV at midpoint of range

    Args:
        data: DataFrame with 'iv' or 'implied_volatility' column
        window: Lookback window in days (default: 252 = 1 year)

    Returns:
        Series with IV rank values in [0, 1]. NaN during cold start or where data is missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "iv": [0.25, 0.30, 0.35, 0.28, 0.32]
        ... })
        >>> iv_rank = compute_iv_rank(data, window=5)
        >>> iv_rank.iloc[-1]  # (0.32 - 0.25) / (0.35 - 0.25) = 0.7
        0.7
    """
    # Find IV column
    iv_col = None
    if "iv" in data.columns:
        iv_col = "iv"
    elif "implied_volatility" in data.columns:
        iv_col = "implied_volatility"
    elif "iv_30d" in data.columns:
        iv_col = "iv_30d"
    else:
        raise ValueError(
            "Missing IV column. Expected one of: 'iv', 'implied_volatility', 'iv_30d'"
        )

    iv = data[iv_col]

    # Compute rolling min and max
    rolling_min = iv.rolling(window=window, min_periods=1).min()
    rolling_max = iv.rolling(window=window, min_periods=1).max()

    # Compute IV rank
    with np.errstate(divide="ignore", invalid="ignore"):
        iv_rank = (iv - rolling_min) / (rolling_max - rolling_min)

    # Replace inf with NaN
    iv_rank = iv_rank.replace([np.inf, -np.inf], np.nan)

    # If min == max (constant IV), rank is undefined → NaN
    iv_rank = iv_rank.where(rolling_max != rolling_min, np.nan)

    return iv_rank


def compute_term_structure_slope(data: pd.DataFrame) -> pd.Series:
    """Compute IV Term Structure Slope — near-term vs far-term IV ratio.

    Measures the slope of the volatility term structure. Useful for detecting
    event risk (earnings, FOMC) or volatility regime shifts.

    Formula:
        Term_Slope = IV_near / IV_far

    Where:
    - Term_Slope > 1 → near-term IV elevated (backwardation, event risk)
    - Term_Slope < 1 → far-term IV elevated (contango, normal structure)

    Args:
        data: DataFrame with near and far-term IV columns:
              - 'iv_30d' and 'iv_90d' (30-day vs 90-day)
              - 'iv_near' and 'iv_far'

    Returns:
        Series with term structure slope values. NaN where data is missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "iv_30d": [0.35, 0.42, 0.38],
        ...     "iv_90d": [0.30, 0.35, 0.32]
        ... })
        >>> slope = compute_term_structure_slope(data)
        >>> slope[0]  # 0.35 / 0.30 = 1.167 (backwardation)
        1.1666666666666667
    """
    # Method 1: 30d / 90d ratio
    if "iv_30d" in data.columns and "iv_90d" in data.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            slope = data["iv_30d"] / data["iv_90d"]
        return slope.replace([np.inf, -np.inf], np.nan)

    # Method 2: Generic near/far
    elif "iv_near" in data.columns and "iv_far" in data.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            slope = data["iv_near"] / data["iv_far"]
        return slope.replace([np.inf, -np.inf], np.nan)

    else:
        raise ValueError(
            "Missing term structure data. Expected: 'iv_30d' and 'iv_90d', "
            "or 'iv_near' and 'iv_far'"
        )
