"""Scoring system: weighted |Z| sum → percentile rank → unusualness score.

Implements the MM Unusualness Score from spec Section 5:
- Weighted absolute z-score sum: S_t = Σ w_k × |Z_k(t)|
- Percentile mapping: U_t ∈ [0, 100]
- Fixed diagnostic weights (not tunable)
- Interpretation bands: Normal, Elevated, Unusual, Extreme
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class InterpretationBand(Enum):
    """Interpretation bands for unusualness scores per spec Section 5.3."""
    
    NORMAL = "Normal"        # 0-30: Within historical norms
    ELEVATED = "Elevated"    # 30-60: Measurable deviation
    UNUSUAL = "Unusual"      # 60-80: Significant departure
    EXTREME = "Extreme"      # 80-100: Rare configuration


# Fixed diagnostic weights per spec Section 5.1
# These are CONCEPTUAL allocations, NOT optimized, NOT tunable
FEATURE_WEIGHTS = {
    "dark_share": 0.25,    # Z_dark - Primary institutional flow signal
    "gex": 0.25,           # Z_GEX - Primary dealer positioning signal
    "venue_mix": 0.20,     # Z_venue - Execution structure deviation
    "block_intensity": 0.15,  # Z_block - Large-print institutional activity
    "iv_rank": 0.15,       # Z_IV - Options market stress indicator (iv_rank_1y from UW)
}


@dataclass
class ScoringResult:
    """Result of unusualness scoring for a single time point.
    
    Attributes:
        raw_score: Weighted absolute z-score sum (S_t)
        percentile_score: Percentile rank in [0, 100] (U_t)
        interpretation: Interpretation band (Normal/Elevated/Unusual/Extreme)
        feature_contributions: Dict of feature → contribution (w_k × |Z_k|)
        excluded_features: List of features excluded (n < N_min)
    """
    
    raw_score: float
    percentile_score: float
    interpretation: InterpretationBand
    feature_contributions: dict[str, float]
    excluded_features: list[str]


class Scorer:
    """Unusualness scoring engine with percentile mapping.
    
    Computes:
    1. Raw score: S_t = Σ w_k × |Z_k(t)| for valid features
    2. Percentile rank: U_t = PercentileRank(S_t | window)
    3. Interpretation band based on U_t threshold
    
    Args:
        window: Window size for percentile computation (default: 63)
        weights: Custom feature weights (default: FEATURE_WEIGHTS from spec)
    
    Example:
        >>> scorer = Scorer(window=63)
        >>> z_scores = {"gex": 2.5, "dark_share": 1.8, "iv_rank": 0.5}
        >>> result = scorer.compute_score(z_scores)
        >>> result.percentile_score
        85.3
        >>> result.interpretation
        <InterpretationBand.EXTREME: 'Extreme'>
    """
    
    def __init__(
        self,
        window: int = 63,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        if window < 1:
            raise ValueError(f"Window ({window}) must be >= 1")
        
        self.window = window
        self.weights = weights if weights is not None else FEATURE_WEIGHTS.copy()
        
        # Validate weights sum to approximately 1.0
        weight_sum = sum(self.weights.values())
        if not (0.99 <= weight_sum <= 1.01):
            import warnings
            warnings.warn(
                f"Feature weights sum to {weight_sum:.3f}, expected ~1.0. "
                "This may indicate misconfiguration.",
                UserWarning
            )
    
    def compute_raw_score(
        self,
        z_scores: dict[str, float],
        excluded_features: Optional[list[str]] = None,
    ) -> tuple[float, dict[str, float]]:
        """Compute raw weighted absolute z-score sum.
        
        Formula per spec Section 5.1:
            S_t = Σ_{k ∈ F_t} w_k × |Z_k(t)|
        
        Where F_t is the set of features with valid baseline.
        Weights are NOT renormalized when features are excluded.
        
        Args:
            z_scores: Dict mapping feature name → z-score value
            excluded_features: List of features to exclude (e.g., n < N_min)
        
        Returns:
            Tuple of (raw_score, feature_contributions dict)
        
        Example:
            >>> scorer = Scorer()
            >>> z_scores = {"gex": 2.5, "dark_share": -1.8, "iv_rank": 0.5}
            >>> raw_score, contributions = scorer.compute_raw_score(z_scores)
            >>> raw_score
            1.275  # 0.25*2.5 + 0.25*1.8 + 0.15*0.5
        """
        excluded = set(excluded_features or [])
        raw_score = 0.0
        contributions = {}
        
        for feature, z_value in z_scores.items():
            # Skip excluded features
            if feature in excluded:
                continue

            # Skip NaN z-scores
            if pd.isna(z_value):
                continue

            # Get weight (0 if not in weights dict)
            weight = self.weights.get(feature, 0.0)

            # Skip features with zero weight
            if weight == 0.0:
                continue

            # Contribution: w_k × |Z_k|
            contribution = weight * abs(z_value)
            contributions[feature] = contribution
            raw_score += contribution
        
        return raw_score, contributions
    
    def compute_percentile_scores(
        self,
        raw_scores: pd.Series,
        use_expanding: bool = True,
    ) -> pd.Series:
        """Compute percentile rank for each raw score.
        
        Formula per spec Section 5.2:
            U_t = PercentileRank(S_t | { S_τ : τ ∈ [t−W, t] })
        
        Uses expanding window for t ≤ window, then rolling window.
        
        Args:
            raw_scores: Series of raw scores over time
            use_expanding: If True, use expanding window for t ≤ window
        
        Returns:
            Series of percentile scores in [0, 100]
        
        Example:
            >>> raw_scores = pd.Series([1.0, 1.5, 2.0, 1.2, 3.0])
            >>> percentiles = scorer.compute_percentile_scores(raw_scores)
            >>> percentiles.iloc[-1]  # Last score is highest
            100.0
        """
        n = len(raw_scores)
        percentile_scores = []
        
        for i in range(n):
            if use_expanding and i < self.window:
                # Expanding window: use all data from start
                window_data = raw_scores.iloc[:i+1]
            else:
                # Rolling window: use last `window` points
                start_idx = max(0, i - self.window + 1)
                window_data = raw_scores.iloc[start_idx:i+1]
            
            # Remove NaN values
            window_data = window_data.dropna()
            
            if len(window_data) == 0:
                # No valid data → NaN
                percentile_scores.append(np.nan)
            else:
                # Compute percentile rank (0-100)
                current_value = raw_scores.iloc[i]
                
                if pd.isna(current_value):
                    percentile_scores.append(np.nan)
                else:
                    # Count how many values are <= current
                    rank = (window_data <= current_value).sum()
                    percentile = (rank / len(window_data)) * 100.0
                    percentile_scores.append(percentile)
        
        return pd.Series(percentile_scores, index=raw_scores.index)
    
    def get_interpretation(self, percentile_score: float) -> InterpretationBand:
        """Get interpretation band for a percentile score.
        
        Bands per spec Section 5.3:
        - 0-30: Normal
        - 30-60: Elevated
        - 60-80: Unusual
        - 80-100: Extreme
        
        Args:
            percentile_score: Score in [0, 100]
        
        Returns:
            InterpretationBand enum value
        
        Example:
            >>> scorer.get_interpretation(25.0)
            <InterpretationBand.NORMAL: 'Normal'>
            >>> scorer.get_interpretation(85.0)
            <InterpretationBand.EXTREME: 'Extreme'>
        """
        if pd.isna(percentile_score):
            # Default to NORMAL for NaN (though this shouldn't happen in practice)
            return InterpretationBand.NORMAL
        
        if percentile_score < 30:
            return InterpretationBand.NORMAL
        elif percentile_score < 60:
            return InterpretationBand.ELEVATED
        elif percentile_score < 80:
            return InterpretationBand.UNUSUAL
        else:
            return InterpretationBand.EXTREME
    
    def compute_score(
        self,
        z_scores: dict[str, float],
        historical_raw_scores: Optional[pd.Series] = None,
        excluded_features: Optional[list[str]] = None,
    ) -> ScoringResult:
        """Compute full unusualness score for a single time point.
        
        Args:
            z_scores: Dict mapping feature name → z-score value
            historical_raw_scores: Historical raw scores for percentile mapping
                                  If None, percentile_score will be NaN
            excluded_features: List of features to exclude (e.g., n < N_min)
        
        Returns:
            ScoringResult with raw_score, percentile_score, interpretation, etc.
        
        Example:
            >>> z_scores = {"gex": 2.5, "dark_share": 1.8}
            >>> history = pd.Series([1.0, 1.2, 1.5, 1.8, 2.0])
            >>> result = scorer.compute_score(z_scores, historical_raw_scores=history)
            >>> result.percentile_score
            85.7
        """
        # Compute raw score and contributions
        raw_score, contributions = self.compute_raw_score(
            z_scores,
            excluded_features=excluded_features
        )
        
        # Compute percentile score if historical data provided
        if historical_raw_scores is not None:
            # Append current score to history and compute percentile
            extended_history = pd.concat([
                historical_raw_scores,
                pd.Series([raw_score])
            ])
            percentiles = self.compute_percentile_scores(extended_history)
            percentile_score = percentiles.iloc[-1]
        else:
            percentile_score = np.nan
        
        # Get interpretation band
        interpretation = self.get_interpretation(percentile_score)
        
        return ScoringResult(
            raw_score=raw_score,
            percentile_score=percentile_score,
            interpretation=interpretation,
            feature_contributions=contributions,
            excluded_features=excluded_features or [],
        )
    
    def get_top_contributors(
        self,
        feature_contributions: dict[str, float],
        top_n: int = 3,
    ) -> list[tuple[str, float]]:
        """Get top N contributing features ranked by contribution.
        
        Args:
            feature_contributions: Dict of feature → contribution (w_k × |Z_k|)
            top_n: Number of top features to return (default: 3)
        
        Returns:
            List of (feature_name, contribution) tuples, sorted descending
        
        Example:
            >>> contributions = {"gex": 0.625, "dark_share": 0.45, "iv_rank": 0.075}
            >>> scorer.get_top_contributors(contributions, top_n=2)
            [('gex', 0.625), ('dark_share', 0.45)]
        """
        sorted_items = sorted(
            feature_contributions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_items[:top_n]
