"""Structural Focus — Index-weight-based ticker selection.

Determines which tickers are structurally important by fetching
ETF holdings and selecting the top-N by weight.

Thresholds per spec §2.1:
    - SPY: Top 15
    - QQQ: Top 10
    - DIA: Top 10
    - IWM: Skipped (too fragmented)
"""

import logging
from dataclasses import dataclass
from typing import Any

from obsidian.clients.fmp import FMPClient

logger = logging.getLogger(__name__)

# Top-N thresholds per ETF (IWM intentionally excluded)
STRUCTURAL_THRESHOLDS: dict[str, int] = {
    "SPY": 15,
    "QQQ": 10,
    "DIA": 10,
}


@dataclass(frozen=True)
class IndexConstituent:
    """A single ETF constituent with weight metadata."""

    ticker: str
    etf: str
    rank: int            # 1-based by weight
    weight_pct: float    # e.g. 7.2


async def fetch_structural_focus(
    fmp: FMPClient,
    etf: str,
) -> list[IndexConstituent]:
    """Fetch top-N holdings for a single ETF.

    Args:
        fmp: Active FMP client (already in async context)
        etf: ETF symbol (SPY, QQQ, DIA)

    Returns:
        List of IndexConstituent for the top-N holdings,
        sorted by weight descending. Empty list if ETF is
        not in STRUCTURAL_THRESHOLDS or API returns no data.
    """
    etf = etf.upper()
    threshold = STRUCTURAL_THRESHOLDS.get(etf)
    if threshold is None:
        logger.debug("Skipping %s — not in STRUCTURAL_THRESHOLDS", etf)
        return []

    try:
        holdings = await fmp.get_etf_holdings(etf)
    except Exception as e:
        logger.warning("Failed to fetch holdings for %s: %s", etf, e)
        return []

    if not holdings:
        logger.warning("%s: no holdings returned", etf)
        return []

    # Sort by weight descending and take top N
    sorted_holdings = sorted(
        holdings,
        key=lambda h: float(h.get("weightPercentage", 0)),
        reverse=True,
    )

    result: list[IndexConstituent] = []
    for rank, holding in enumerate(sorted_holdings[:threshold], start=1):
        asset = holding.get("asset", "")
        weight = float(holding.get("weightPercentage", 0))
        if asset:
            result.append(IndexConstituent(
                ticker=asset.upper(),
                etf=etf,
                rank=rank,
                weight_pct=weight,
            ))

    logger.info("%s: %d structural tickers (top %d)", etf, len(result), threshold)
    return result


async def fetch_all_structural_focus(
    fmp: FMPClient,
) -> dict[str, list[IndexConstituent]]:
    """Fetch structural focus tickers for all tracked ETFs.

    Fetches holdings for SPY, QQQ, DIA (IWM skipped per spec).

    Args:
        fmp: Active FMP client

    Returns:
        Dictionary mapping ETF → list of IndexConstituent
    """
    result: dict[str, list[IndexConstituent]] = {}
    for etf in STRUCTURAL_THRESHOLDS:
        result[etf] = await fetch_structural_focus(fmp, etf)
    return result


def deduplicate_structural_tickers(
    by_etf: dict[str, list[IndexConstituent]],
) -> dict[str, IndexConstituent]:
    """Deduplicate tickers that appear in multiple ETFs.

    When a ticker appears in multiple ETFs (e.g. AAPL in SPY and QQQ),
    keep the entry with the higher weight percentage.

    Args:
        by_etf: Output of fetch_all_structural_focus()

    Returns:
        Dictionary mapping ticker → IndexConstituent (winner)
    """
    best: dict[str, IndexConstituent] = {}

    for constituents in by_etf.values():
        for c in constituents:
            existing = best.get(c.ticker)
            if existing is None or c.weight_pct > existing.weight_pct:
                best[c.ticker] = c

    return best
