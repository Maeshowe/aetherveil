"""MM Regime Classification for OBSIDIAN MM.

Priority-ordered deterministic rules that classify daily market microstructure
into one of seven regimes. First match wins (short-circuit evaluation).

Regime Types (priority order):
    1. Γ⁺ (Gamma-Positive Control): Dealers long gamma, volatility suppression
    2. Γ⁻ (Gamma-Negative Liquidity Vacuum): Dealers short gamma, amplification
    3. DD (Dark-Dominant Accumulation): Institutional dark pool positioning
    4. ABS (Absorption-Like): Sell pressure absorbed
    5. DIST (Distribution-Like): Buy pressure distributed into strength
    6. NEU (Neutral / Mixed): No dominant pattern
    7. UND (Undetermined): Insufficient data

Design Principles:
    - Deterministic: Explicit conditional logic, no ML
    - Mutually exclusive: Exactly one regime per day
    - Priority-ordered: Rules evaluated top-to-bottom
    - Explainable: Triggering conditions returned with classification
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class RegimeType(Enum):
    """Market microstructure regime types in priority order."""

    GAMMA_POSITIVE = "Γ⁺"  # Gamma-Positive Control
    GAMMA_NEGATIVE = "Γ⁻"  # Gamma-Negative Liquidity Vacuum
    DARK_DOMINANT = "DD"  # Dark-Dominant Accumulation
    ABSORPTION = "ABS"  # Absorption-Like
    DISTRIBUTION = "DIST"  # Distribution-Like
    NEUTRAL = "NEU"  # Neutral / Mixed
    UNDETERMINED = "UND"  # Undetermined

    def get_description(self) -> str:
        """Get human-readable description of the regime."""
        descriptions = {
            RegimeType.GAMMA_POSITIVE: "Gamma-Positive Control",
            RegimeType.GAMMA_NEGATIVE: "Gamma-Negative Liquidity Vacuum",
            RegimeType.DARK_DOMINANT: "Dark-Dominant Accumulation",
            RegimeType.ABSORPTION: "Absorption-Like",
            RegimeType.DISTRIBUTION: "Distribution-Like",
            RegimeType.NEUTRAL: "Neutral / Mixed",
            RegimeType.UNDETERMINED: "Undetermined",
        }
        return descriptions[self]

    def get_interpretation(self) -> str:
        """Get microstructure interpretation of the regime."""
        interpretations = {
            RegimeType.GAMMA_POSITIVE: (
                "Dealers are significantly long gamma. Their hedging activity "
                "compresses the intraday range, resulting in below-normal price "
                "efficiency. Volatility suppression regime."
            ),
            RegimeType.GAMMA_NEGATIVE: (
                "Dealers are significantly short gamma. Their hedging amplifies "
                "directional moves. Above-normal price impact per unit volume "
                "signals a liquidity vacuum."
            ),
            RegimeType.DARK_DOMINANT: (
                "More than 70% of volume is executing off-exchange, with "
                "block-print intensity elevated above +1σ. Consistent with "
                "institutional positioning via dark liquidity."
            ),
            RegimeType.ABSORPTION: (
                "Net delta exposure is significantly negative (sell pressure), "
                "but the daily close-to-close move is no worse than −0.5%, and "
                "dark pool participation exceeds 50%. Passive buying is absorbing "
                "the sell flow."
            ),
            RegimeType.DISTRIBUTION: (
                "Net delta exposure is significantly positive (buy pressure), "
                "but the daily move is no better than +0.5%. Supply is being "
                "distributed into strength without upside follow-through."
            ),
            RegimeType.NEUTRAL: (
                "No single microstructure pattern dominates. The instrument is "
                "in a balanced or ambiguous state."
            ),
            RegimeType.UNDETERMINED: "System cannot classify. Diagnosis withheld.",
        }
        return interpretations[self]


@dataclass
class RegimeResult:
    """Result of regime classification with explainability.

    Attributes:
        regime: The assigned regime type
        triggering_conditions: Dict of condition name → (value, threshold, met)
            Example: {"Z_GEX": (2.14, 1.5, True), "Efficiency_vs_median": (0.0032, 0.0041, True)}
        interpretation: Human-readable interpretation
        baseline_sufficient: Whether baseline data was sufficient for classification
    """

    regime: RegimeType
    triggering_conditions: dict[str, tuple[float, float, bool]]
    interpretation: str
    baseline_sufficient: bool

    def format_conditions(self) -> str:
        """Format triggering conditions as human-readable string.

        Returns:
            Formatted string like "Z_GEX = 2.14 (threshold: > 1.5) ✓"
        """
        lines = []
        for name, (value, threshold, met) in self.triggering_conditions.items():
            symbol = "✓" if met else "✗"
            lines.append(f"{name} = {value:.4f} (threshold: {threshold:.4f}) {symbol}")
        return "\n".join(lines)


class Classifier:
    """MM Regime Classifier using priority-ordered deterministic rules.

    Evaluates rules in strict priority order. First match wins (short-circuit).
    All thresholds reference z-scores or percentiles computed against the
    instrument's own baseline (W = 63 trading days).

    Thresholds (from spec Section 6.3):
        - Z_GEX threshold (Γ⁺ / Γ⁻): ±1.5
        - DarkShare threshold (DD): 0.70 (absolute proportion)
        - Z_block threshold (DD): +1.0
        - Z_DEX threshold (ABS / DIST): ±1.0
        - Price move cap (ABS): ≥ −0.5% (−0.005)
        - Price move cap (DIST): ≤ +0.5% (+0.005)
        - DarkShare floor (ABS): 0.50 (absolute proportion)
        - Efficiency benchmark (Γ⁺): < median
        - Impact benchmark (Γ⁻): > median
    """

    # Fixed thresholds from spec
    Z_GEX_THRESHOLD = 1.5
    Z_BLOCK_THRESHOLD = 1.0
    Z_DEX_THRESHOLD = 1.0
    DARK_SHARE_DD_THRESHOLD = 0.70
    DARK_SHARE_ABS_THRESHOLD = 0.50
    PRICE_MOVE_ABS_CAP = -0.005  # ≥ −0.5%
    PRICE_MOVE_DIST_CAP = 0.005  # ≤ +0.5%

    def __init__(self) -> None:
        """Initialize classifier with fixed thresholds from spec."""
        pass

    def classify(
        self,
        z_scores: dict[str, float],
        raw_features: dict[str, float],
        baseline_medians: dict[str, float],
        daily_return: float,
        baseline_sufficient: bool = True,
    ) -> RegimeResult:
        """Classify regime using priority-ordered rules.

        Rules are evaluated in strict priority order (1-7). First match wins.
        If baseline is insufficient, returns UND immediately.

        Args:
            z_scores: Z-scores for each feature (e.g., {"gex": 2.14, "dex": -0.5})
            raw_features: Raw feature values (e.g., {"dark_share": 0.75, "efficiency": 0.0032})
            baseline_medians: Median values from baseline (e.g., {"efficiency": 0.0041, "impact": 0.0052})
            daily_return: Close-to-close return (ΔP_t / Close_{t-1})
            baseline_sufficient: Whether baseline state is COMPLETE or PARTIAL

        Returns:
            RegimeResult with assigned regime and triggering conditions

        Rule Priority:
            1. Γ⁺: Z_GEX > +1.5 AND Efficiency < median
            2. Γ⁻: Z_GEX < −1.5 AND Impact > median
            3. DD: DarkShare > 0.70 AND Z_block > +1.0
            4. ABS: Z_DEX < −1.0 AND return ≥ −0.005 AND DarkShare > 0.50
            5. DIST: Z_DEX > +1.0 AND return ≤ +0.005
            6. NEU: No prior rule matched
            7. UND: Baseline insufficient
        """
        # Priority 7 (immediate): Undetermined if baseline insufficient
        if not baseline_sufficient:
            return RegimeResult(
                regime=RegimeType.UNDETERMINED,
                triggering_conditions={},
                interpretation=RegimeType.UNDETERMINED.get_interpretation(),
                baseline_sufficient=False,
            )

        # Extract z-scores (use NaN if missing)
        z_gex = z_scores.get("gex", np.nan)
        z_dex = z_scores.get("dex", np.nan)
        z_block = z_scores.get("block_intensity", np.nan)

        # Extract raw features (use NaN if missing)
        dark_share = raw_features.get("dark_share", np.nan)
        efficiency = raw_features.get("efficiency", np.nan)
        impact = raw_features.get("impact", np.nan)

        # Extract baseline medians (use NaN if missing)
        efficiency_median = baseline_medians.get("efficiency", np.nan)
        impact_median = baseline_medians.get("impact", np.nan)

        # Priority 1: Γ⁺ (Gamma-Positive Control)
        # Z_GEX > +1.5 AND Efficiency < median
        if not np.isnan(z_gex) and not np.isnan(efficiency) and not np.isnan(efficiency_median):
            if z_gex > self.Z_GEX_THRESHOLD and efficiency < efficiency_median:
                return RegimeResult(
                    regime=RegimeType.GAMMA_POSITIVE,
                    triggering_conditions={
                        "Z_GEX": (z_gex, self.Z_GEX_THRESHOLD, True),
                        "Efficiency_vs_median": (efficiency, efficiency_median, True),
                    },
                    interpretation=RegimeType.GAMMA_POSITIVE.get_interpretation(),
                    baseline_sufficient=True,
                )

        # Priority 2: Γ⁻ (Gamma-Negative Liquidity Vacuum)
        # Z_GEX < −1.5 AND Impact > median
        if not np.isnan(z_gex) and not np.isnan(impact) and not np.isnan(impact_median):
            if z_gex < -self.Z_GEX_THRESHOLD and impact > impact_median:
                return RegimeResult(
                    regime=RegimeType.GAMMA_NEGATIVE,
                    triggering_conditions={
                        "Z_GEX": (z_gex, -self.Z_GEX_THRESHOLD, True),
                        "Impact_vs_median": (impact, impact_median, True),
                    },
                    interpretation=RegimeType.GAMMA_NEGATIVE.get_interpretation(),
                    baseline_sufficient=True,
                )

        # Priority 3: DD (Dark-Dominant Accumulation)
        # DarkShare > 0.70 AND Z_block > +1.0
        if not np.isnan(dark_share) and not np.isnan(z_block):
            if dark_share > self.DARK_SHARE_DD_THRESHOLD and z_block > self.Z_BLOCK_THRESHOLD:
                return RegimeResult(
                    regime=RegimeType.DARK_DOMINANT,
                    triggering_conditions={
                        "DarkShare": (dark_share, self.DARK_SHARE_DD_THRESHOLD, True),
                        "Z_block": (z_block, self.Z_BLOCK_THRESHOLD, True),
                    },
                    interpretation=RegimeType.DARK_DOMINANT.get_interpretation(),
                    baseline_sufficient=True,
                )

        # Priority 4: ABS (Absorption-Like)
        # Z_DEX < −1.0 AND return ≥ −0.005 AND DarkShare > 0.50
        if not np.isnan(z_dex) and not np.isnan(daily_return) and not np.isnan(dark_share):
            if (
                z_dex < -self.Z_DEX_THRESHOLD
                and daily_return >= self.PRICE_MOVE_ABS_CAP
                and dark_share > self.DARK_SHARE_ABS_THRESHOLD
            ):
                return RegimeResult(
                    regime=RegimeType.ABSORPTION,
                    triggering_conditions={
                        "Z_DEX": (z_dex, -self.Z_DEX_THRESHOLD, True),
                        "Daily_return": (daily_return, self.PRICE_MOVE_ABS_CAP, True),
                        "DarkShare": (dark_share, self.DARK_SHARE_ABS_THRESHOLD, True),
                    },
                    interpretation=RegimeType.ABSORPTION.get_interpretation(),
                    baseline_sufficient=True,
                )

        # Priority 5: DIST (Distribution-Like)
        # Z_DEX > +1.0 AND return ≤ +0.005
        if not np.isnan(z_dex) and not np.isnan(daily_return):
            if z_dex > self.Z_DEX_THRESHOLD and daily_return <= self.PRICE_MOVE_DIST_CAP:
                return RegimeResult(
                    regime=RegimeType.DISTRIBUTION,
                    triggering_conditions={
                        "Z_DEX": (z_dex, self.Z_DEX_THRESHOLD, True),
                        "Daily_return": (daily_return, self.PRICE_MOVE_DIST_CAP, True),
                    },
                    interpretation=RegimeType.DISTRIBUTION.get_interpretation(),
                    baseline_sufficient=True,
                )

        # Priority 6: NEU (Neutral / Mixed)
        # No prior rule matched
        return RegimeResult(
            regime=RegimeType.NEUTRAL,
            triggering_conditions={},
            interpretation=RegimeType.NEUTRAL.get_interpretation(),
            baseline_sufficient=True,
        )
