"""Price-based features: Efficiency and Impact.

These features measure price control and liquidity vacuum conditions:
- Efficiency: intraday range per unit volume (control proxy)
- Impact: directional move per unit volume (vacuum proxy)

Both are evaluated relative to instrument's baseline, not in absolute terms.
"""

import pandas as pd
import numpy as np


def compute_efficiency(data: pd.DataFrame) -> pd.Series:
    """Compute Price Efficiency — intraday range per unit volume.

    Formula:
        Efficiency_t = (High_t - Low_t) / Volume_t

    Low Efficiency → price is being controlled/absorbed (small range per unit volume).

    Args:
        data: DataFrame with columns: high, low, volume

    Returns:
        Series with computed efficiency values. NaN where data is missing or volume is zero.

    Example:
        >>> data = pd.DataFrame({
        ...     "high": [152.0, 153.5, 151.8],
        ...     "low": [150.0, 151.0, 150.2],
        ...     "volume": [1000000, 1500000, 1200000]
        ... })
        >>> efficiency = compute_efficiency(data)
        >>> efficiency[0]  # (152 - 150) / 1000000 = 0.000002
        2e-06
    """
    required_cols = ["high", "low", "volume"]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Missing required column: {col}")

    # Calculate intraday range
    intraday_range = data["high"] - data["low"]

    # Efficiency = range / volume
    # Return NaN where volume is zero or missing
    with np.errstate(divide="ignore", invalid="ignore"):
        efficiency = intraday_range / data["volume"]

    # Replace inf with NaN (from division by zero)
    efficiency = efficiency.replace([np.inf, -np.inf], np.nan)

    return efficiency


def compute_impact(data: pd.DataFrame) -> pd.Series:
    """Compute Price Impact — directional move per unit volume.

    Formula:
        Impact_t = |Close_t - Open_t| / Volume_t

    High Impact → small flows causing large directional moves (liquidity vacuum).

    Args:
        data: DataFrame with columns: close, open, volume

    Returns:
        Series with computed impact values. NaN where data is missing or volume is zero.

    Example:
        >>> data = pd.DataFrame({
        ...     "close": [151.5, 152.8, 150.2],
        ...     "open": [150.0, 151.0, 151.5],
        ...     "volume": [1000000, 1500000, 1200000]
        ... })
        >>> impact = compute_impact(data)
        >>> impact[0]  # |151.5 - 150| / 1000000 = 0.0000015
        1.5e-06
    """
    required_cols = ["close", "open", "volume"]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Missing required column: {col}")

    # Calculate absolute open-to-close move
    directional_move = (data["close"] - data["open"]).abs()

    # Impact = move / volume
    # Return NaN where volume is zero or missing
    with np.errstate(divide="ignore", invalid="ignore"):
        impact = directional_move / data["volume"]

    # Replace inf with NaN (from division by zero)
    impact = impact.replace([np.inf, -np.inf], np.nan)

    return impact
