"""Feature extraction modules for OBSIDIAN MM.

Each module computes raw daily feature values from market data. The baseline
system (Phase 4) handles z-score normalization.

Modules:
    - price: Efficiency, Impact (price control/vacuum proxies)
    - dark_pool: DarkShare, Block Intensity
    - greeks: GEX, DEX, Vanna, Charm (dealer exposures)
    - volatility: IV Skew, IV Rank
    - venue: Venue Mix (execution venue distribution)
"""

from obsidian.features.dark_pool import compute_dark_share, compute_block_intensity
from obsidian.features.greeks import compute_gex, compute_dex, compute_vanna, compute_charm
from obsidian.features.price import compute_efficiency, compute_impact
from obsidian.features.venue import compute_venue_mix
from obsidian.features.volatility import compute_iv_skew, compute_iv_rank

__all__ = [
    "compute_dark_share",
    "compute_block_intensity",
    "compute_gex",
    "compute_dex",
    "compute_vanna",
    "compute_charm",
    "compute_efficiency",
    "compute_impact",
    "compute_venue_mix",
    "compute_iv_skew",
    "compute_iv_rank",
]
