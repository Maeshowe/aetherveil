"""Baseline system: rolling statistics, z-score normalization, state tracking.

Implements the baseline framework from spec Section 3:
- Rolling 63-day window (W = 63)
- Expanding window for cold start (t ≤ 63)
- Minimum observations N_min = 21
- Baseline states: EMPTY, PARTIAL, COMPLETE
- Drift detection (δ = 0.10)
- Instrument isolation (B_i ≠ B_j)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class BaselineState(Enum):
    """Baseline validity states per spec Section 3.3."""
    
    EMPTY = "EMPTY"        # ∀X : n_X < 21 → No diagnosis
    PARTIAL = "PARTIAL"    # ∃X: n_X ≥ 21 ∧ n_X < 21 → Conditional diagnosis
    COMPLETE = "COMPLETE"  # ∀X: n_X ≥ 21 → Full confidence


@dataclass
class BaselineStats:
    """Rolling baseline statistics for a single feature.
    
    Attributes:
        mean: Rolling mean (μ_X)
        std: Rolling sample standard deviation (σ_X)
        median: Rolling median
        n_valid: Count of non-NaN observations in window
        is_valid: True if n_valid >= N_min
    """
    
    mean: float
    std: float
    median: float
    n_valid: int
    is_valid: bool
    
    def __post_init__(self) -> None:
        """Validate that NaN stats have is_valid=False."""
        if pd.isna(self.mean) or pd.isna(self.std):
            object.__setattr__(self, 'is_valid', False)


class Baseline:
    """Baseline computation engine with expanding window cold start.
    
    Implements rolling statistics computation with:
    - Expanding window for t ≤ 63 (cold start)
    - Fixed rolling window for t > 63 (steady state)
    - Minimum observation threshold N_min = 21
    - Drift detection threshold δ = 0.10
    
    Args:
        window: Rolling window size in days (default: 63)
        min_periods: Minimum valid observations (default: 21)
        drift_threshold: Relative drift detection threshold (default: 0.10)
    
    Example:
        >>> baseline = Baseline(window=63, min_periods=21)
        >>> z_scores = baseline.compute_z_scores(feature_data)
        >>> state = baseline.get_state({"gex": 25, "dark_share": 18})
        >>> state
        <BaselineState.PARTIAL: 'PARTIAL'>
    """
    
    def __init__(
        self,
        window: int = 63,
        min_periods: int = 21,
        drift_threshold: float = 0.10,
    ) -> None:
        if window < min_periods:
            raise ValueError(
                f"Window ({window}) must be >= min_periods ({min_periods})"
            )
        if min_periods < 2:
            raise ValueError(
                f"min_periods ({min_periods}) must be >= 2 for std calculation"
            )
        if not 0 < drift_threshold <= 1:
            raise ValueError(
                f"drift_threshold ({drift_threshold}) must be in (0, 1]"
            )
        
        self.window = window
        self.min_periods = min_periods
        self.drift_threshold = drift_threshold
    
    def compute_statistics(
        self,
        data: pd.Series,
        use_expanding: bool = True,
    ) -> pd.Series:
        """Compute rolling baseline statistics for a feature.
        
        Uses expanding window for first `window` observations (cold start),
        then transitions to fixed rolling window.
        
        Args:
            data: Time series of feature values
            use_expanding: If True, use expanding window for t ≤ window
        
        Returns:
            Series of BaselineStats objects, one per time point
        
        Example:
            >>> data = pd.Series([1.0, 1.2, 1.1, 1.3, ...])  # 100 days
            >>> stats = baseline.compute_statistics(data)
            >>> stats.iloc[25].mean  # Access mean at t=25
            1.15
            >>> stats.iloc[25].is_valid  # Valid if n_valid >= 21
            True
        """
        n = len(data)
        stats_list = []
        
        for i in range(n):
            if use_expanding and i < self.window:
                # Expanding window: use all data from start to current point
                window_data = data.iloc[:i+1]
            else:
                # Rolling window: use last `window` points
                start_idx = max(0, i - self.window + 1)
                window_data = data.iloc[start_idx:i+1]
            
            # Count non-NaN observations
            n_valid = window_data.notna().sum()
            
            # Compute statistics (NaN-safe)
            if n_valid >= self.min_periods:
                mean = window_data.mean()
                std = window_data.std(ddof=1)  # Sample std
                median = window_data.median()
                is_valid = True
            else:
                mean = np.nan
                std = np.nan
                median = np.nan
                is_valid = False
            
            stats_list.append(
                BaselineStats(
                    mean=mean,
                    std=std,
                    median=median,
                    n_valid=int(n_valid),
                    is_valid=is_valid,
                )
            )
        
        return pd.Series(stats_list, index=data.index)
    
    def compute_z_scores(
        self,
        data: pd.Series,
        use_expanding: bool = True,
    ) -> pd.Series:
        """Compute z-scores with expanding window cold start.
        
        Formula:
            Z_X(t) = (X_t - μ_X) / σ_X
        
        Where μ_X and σ_X are computed using:
        - Expanding window for t ≤ window
        - Rolling window for t > window
        
        Args:
            data: Time series of feature values
            use_expanding: If True, use expanding window for t ≤ window
        
        Returns:
            Series of z-scores. NaN where:
            - Input value is NaN
            - n_valid < min_periods
            - std = 0 (constant values)
        
        Example:
            >>> data = pd.Series([1.0, 1.2, 1.1, 1.3, ...])
            >>> z_scores = baseline.compute_z_scores(data)
            >>> z_scores.iloc[25]  # First valid z-score at t >= min_periods
            0.85
        """
        stats = self.compute_statistics(data, use_expanding=use_expanding)
        
        # Extract mean and std from stats
        means = pd.Series([s.mean for s in stats], index=data.index)
        stds = pd.Series([s.std for s in stats], index=data.index)
        
        # Compute z-scores
        with np.errstate(divide='ignore', invalid='ignore'):
            z_scores = (data - means) / stds
        
        # Replace inf with NaN (from division by zero)
        z_scores = z_scores.replace([np.inf, -np.inf], np.nan)
        
        return z_scores
    
    def get_state(
        self,
        feature_counts: dict[str, int],
    ) -> BaselineState:
        """Determine baseline state from feature observation counts.
        
        States per spec Section 3.3:
        - EMPTY: All features have n < min_periods
        - PARTIAL: Some features valid, some invalid
        - COMPLETE: All features have n >= min_periods
        
        Args:
            feature_counts: Dict mapping feature name → n_valid
        
        Returns:
            BaselineState enum value
        
        Example:
            >>> baseline.get_state({"gex": 25, "dark_share": 30})
            <BaselineState.COMPLETE: 'COMPLETE'>
            >>> baseline.get_state({"gex": 25, "vanna": 15})
            <BaselineState.PARTIAL: 'PARTIAL'>
            >>> baseline.get_state({"vanna": 10, "charm": 8})
            <BaselineState.EMPTY: 'EMPTY'>
        """
        if not feature_counts:
            return BaselineState.EMPTY
        
        valid_counts = [n >= self.min_periods for n in feature_counts.values()]
        
        if all(valid_counts):
            return BaselineState.COMPLETE
        elif any(valid_counts):
            return BaselineState.PARTIAL
        else:
            return BaselineState.EMPTY
    
    def detect_drift(
        self,
        current_mean: float,
        previous_mean: float,
    ) -> bool:
        """Detect baseline drift between consecutive periods.
        
        Formula per spec Section 3.6:
            |(μ_t - μ_{t-1}) / μ_{t-1}| > δ
        
        Args:
            current_mean: Mean at time t
            previous_mean: Mean at time t-1
        
        Returns:
            True if drift detected (change > drift_threshold)
        
        Example:
            >>> baseline.detect_drift(1.1, 1.0)  # 10% change
            True
            >>> baseline.detect_drift(1.05, 1.0)  # 5% change
            False
        """
        # Handle NaN or zero previous mean
        if pd.isna(current_mean) or pd.isna(previous_mean):
            return False
        if previous_mean == 0:
            # If previous was 0, any non-zero current is drift
            return current_mean != 0
        
        relative_change = abs((current_mean - previous_mean) / previous_mean)
        return relative_change > self.drift_threshold
    
    def get_excluded_features(
        self,
        feature_counts: dict[str, int],
    ) -> list[tuple[str, int]]:
        """Get list of excluded features with their observation counts.
        
        Args:
            feature_counts: Dict mapping feature name → n_valid
        
        Returns:
            List of (feature_name, n_valid) tuples for invalid features
        
        Example:
            >>> baseline.get_excluded_features({"gex": 25, "vanna": 15, "charm": 10})
            [('vanna', 15), ('charm', 10)]
        """
        excluded = [
            (name, count)
            for name, count in feature_counts.items()
            if count < self.min_periods
        ]
        return sorted(excluded, key=lambda x: x[1])  # Sort by count ascending
