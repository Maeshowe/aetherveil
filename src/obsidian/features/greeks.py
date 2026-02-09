"""Options Greeks features: GEX, DEX, Vanna, Charm.

These features capture dealer positioning and hedging flow:
- GEX: Net dealer gamma exposure (stabilizing vs destabilizing)
- DEX: Net dealer delta exposure (absorption/distribution proxy)
- Vanna: Gamma sensitivity to volatility changes
- Charm: Gamma decay over time

All values sourced from Unusual Whales API.
"""

import pandas as pd
import numpy as np


def compute_gex(data: pd.DataFrame) -> pd.Series:
    """Compute Dealer Gamma Exposure (GEX).

    GEX_t = net dealer gamma exposure on day t, sourced from Unusual Whales.

    **Sign convention (FIXED, NON-NEGOTIABLE):**
    - GEX > 0 → dealers are long gamma → hedging dampens price moves (stabilizing)
    - GEX < 0 → dealers are short gamma → hedging amplifies price moves (destabilizing)

    Args:
        data: DataFrame with column 'gex' or 'gamma_exposure' or computed from call/put gamma

    Returns:
        Series with GEX values. NaN where data is missing.

    Raises:
        ValueError: If required columns are missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "gex": [1500000, -800000, 2100000]
        ... })
        >>> gex = compute_gex(data)
        >>> gex[0]  # Positive = dealers long gamma = stabilizing
        1500000
    """
    # Try different column name conventions
    if "gex" in data.columns:
        return data["gex"]
    elif "gamma_exposure" in data.columns:
        return data["gamma_exposure"]
    elif "net_gamma" in data.columns:
        return data["net_gamma"]
    elif "call_gamma" in data.columns and "put_gamma" in data.columns:
        # Compute net GEX from call and put gamma
        # Convention: GEX = call_gamma - put_gamma
        # (dealers typically short calls, long puts for hedging)
        return data["call_gamma"] - data["put_gamma"]
    else:
        raise ValueError(
            "Missing GEX column. Expected one of: 'gex', 'gamma_exposure', "
            "'net_gamma', or both 'call_gamma' and 'put_gamma'"
        )


def compute_dex(data: pd.DataFrame) -> pd.Series:
    """Compute Dealer Delta Exposure (DEX).

    DEX_t = net dealer delta exposure on day t.

    DEX is a contextual feature used exclusively for absorption/distribution
    classification. It is never used as a standalone diagnostic.

    Args:
        data: DataFrame with column 'dex' or 'delta_exposure' or computed from call/put delta

    Returns:
        Series with DEX values. NaN where data is missing.

    Raises:
        ValueError: If required columns are missing.

    Example:
        >>> data = pd.DataFrame({
        ...     "dex": [-500000, 300000, -150000]
        ... })
        >>> dex = compute_dex(data)
        >>> dex[0]  # Negative = sell pressure
        -500000
    """
    # Try different column name conventions
    if "dex" in data.columns:
        return data["dex"]
    elif "delta_exposure" in data.columns:
        return data["delta_exposure"]
    elif "net_delta" in data.columns:
        return data["net_delta"]
    elif "call_delta" in data.columns and "put_delta" in data.columns:
        # Compute net DEX from call and put delta
        return data["call_delta"] - data["put_delta"]
    else:
        raise ValueError(
            "Missing DEX column. Expected one of: 'dex', 'delta_exposure', "
            "'net_delta', or both 'call_delta' and 'put_delta'"
        )


def compute_vanna(data: pd.DataFrame) -> pd.Series:
    """Compute Vanna exposure — gamma sensitivity to volatility changes.

    Vanna and Charm exposures are sourced from Unusual Whales when available.
    Due to API lookback limitations (often ~7 days at onboarding), these features
    typically require ~3 weeks of daily pipeline runs before reaching N_min = 21.

    Until valid:
        n_Vanna < 21 → feature excluded, noted in explainability output

    Args:
        data: DataFrame with column 'vanna' or computed from call/put vanna

    Returns:
        Series with Vanna values. NaN where data is missing.

    Note:
        Missing data is expected during cold start. The baseline system will
        handle exclusion when n < N_min = 21.

    Example:
        >>> data = pd.DataFrame({
        ...     "vanna": [15000, None, 18000]  # None during cold start is normal
        ... })
        >>> vanna = compute_vanna(data)
        >>> pd.isna(vanna[1])  # NaN is acceptable
        True
    """
    # Try different column name conventions
    if "vanna" in data.columns:
        return data["vanna"]
    elif "vanna_exposure" in data.columns:
        return data["vanna_exposure"]
    elif "net_vanna" in data.columns:
        return data["net_vanna"]
    elif "call_vanna" in data.columns and "put_vanna" in data.columns:
        # Compute net vanna from call and put
        return data["call_vanna"] - data["put_vanna"]
    else:
        # Vanna is conditional - return NaN series if not available
        return pd.Series([np.nan] * len(data), index=data.index)


def compute_charm(data: pd.DataFrame) -> pd.Series:
    """Compute Charm exposure — gamma decay over time.

    Charm (also called DgammaDtime) measures how gamma changes as time passes.

    Like Vanna, Charm may not be available during cold start period.
    Until n >= N_min = 21, this feature will be excluded from scoring.

    Args:
        data: DataFrame with column 'charm' or computed from call/put charm

    Returns:
        Series with Charm values. NaN where data is missing.

    Note:
        Missing data is expected during cold start. The baseline system will
        handle exclusion when n < N_min = 21.

    Example:
        >>> data = pd.DataFrame({
        ...     "charm": [5000, None, 6500]  # None during cold start is normal
        ... })
        >>> charm = compute_charm(data)
        >>> pd.isna(charm[1])  # NaN is acceptable
        True
    """
    # Try different column name conventions
    if "charm" in data.columns:
        return data["charm"]
    elif "charm_exposure" in data.columns:
        return data["charm_exposure"]
    elif "net_charm" in data.columns:
        return data["net_charm"]
    elif "call_charm" in data.columns and "put_charm" in data.columns:
        # Compute net charm from call and put
        return data["call_charm"] - data["put_charm"]
    else:
        # Charm is conditional - return NaN series if not available
        return pd.Series([np.nan] * len(data), index=data.index)
