"""Focus Universe Manager — Dynamic ticker selection.

Two-tier system:
- CORE: SPY, QQQ, IWM, DIA (always active)
- FOCUS: Dynamic tickers that explain CORE behavior

FOCUS entry rules:
1. Index weight: Top 15 (SPY), Top 10 (QQQ/DIA)
2. Stress: U_t ≥ 70 OR |Z_GEX| ≥ 2.0 OR DarkShare ≥ 0.65
3. Events: Earnings ±1 day, index rebalancing, macro events

FOCUS exit: 3 consecutive days where no entry condition is met
"""

from obsidian.universe.manager import UniverseManager

__all__ = ["UniverseManager"]
