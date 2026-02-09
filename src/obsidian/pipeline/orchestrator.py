"""Orchestrator — Main pipeline coordinator.

Two-pass pipeline:
  Pass 1: Structural + Event Focus Update → Fetch + Process CORE + FOCUS
  Pass 2: Stress check on results → promote/expire FOCUS → enforce cap

Usage:
    orchestrator = Orchestrator(cache_dir="data/")
    results = await orchestrator.run_diagnostics(target_date=date(2024, 1, 15))
"""

import asyncio
import logging
from datetime import date
from typing import Any

import numpy as np

from obsidian.config import settings
from obsidian.clients.fmp import FMPClient
from obsidian.clients.fred import FREDClient
from obsidian.universe import UniverseManager
from obsidian.universe.structural import (
    deduplicate_structural_tickers,
    fetch_all_structural_focus,
)
from obsidian.universe.events import fetch_all_events
from obsidian.pipeline.fetcher import Fetcher
from obsidian.pipeline.processor import Processor, DiagnosticResult

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main pipeline orchestrator for OBSIDIAN MM.

    Coordinates Universe, Fetcher, and Processor in a two-pass pipeline.

    Usage:
        orchestrator = Orchestrator(cache_dir="data/")
        results = await orchestrator.run_diagnostics(target_date=date(2024, 1, 15))
        for ticker, diagnostic in results.items():
            score_str = f"U={diagnostic.score_percentile:.1f}" if diagnostic.score_raw is not None else "U=N/A"
            print(f"{ticker}: {diagnostic.regime_label} ({score_str})")
    """

    def __init__(self, cache_dir: str = "data/") -> None:
        """Initialize orchestrator with all components.

        Args:
            cache_dir: Directory for Parquet cache
        """
        self.universe = UniverseManager()
        self.fetcher = Fetcher(cache_dir=cache_dir)
        self.processor = Processor(cache_dir=cache_dir)

    async def run_diagnostics(
        self,
        target_date: date,
        fetch_data: bool = True,
        update_focus: bool = True,
    ) -> dict[str, DiagnosticResult]:
        """Run full two-pass diagnostic pipeline.

        Pass 1 (if update_focus and fetch_data):
            - Fetch structural focus (ETF top-N holdings)
            - Fetch event focus (earnings, macro, FOMC)
            - Promote tickers to FOCUS tier

        Main pipeline:
            - Get active tickers (CORE + FOCUS)
            - Fetch raw data from APIs
            - Process through engine

        Pass 2 (if update_focus):
            - Stress-check results → promote/expire FOCUS
            - Enforce 30-ticker cap

        Args:
            target_date: Date to diagnose
            fetch_data: Whether to fetch new data from APIs (default: True)
            update_focus: Whether to update FOCUS based on results (default: True)

        Returns:
            Dictionary mapping ticker -> DiagnosticResult
        """
        # --- Pass 1: Structural + Event Focus ---
        if update_focus and fetch_data:
            await self._pass1_update_focus(target_date)
            # Pre-cap: limit FOCUS before fetching to avoid unnecessary API calls.
            # Uses simple structural-first priority (no scores available yet).
            pre_cap_count = len(self.universe.state.focus)
            if pre_cap_count > 30:
                self.universe.enforce_focus_cap(max_focus=30)
                logger.info(
                    "[Pass 1] Pre-cap: %d → %d FOCUS tickers",
                    pre_cap_count, len(self.universe.state.focus),
                )

        # --- Main: Fetch + Process ---
        active_tickers = self.universe.get_active_tickers()
        logger.info("Processing %d tickers: %s", len(active_tickers), sorted(active_tickers))

        if fetch_data:
            logger.info("Fetching data for %s...", target_date.strftime('%Y-%m-%d'))
            fetch_results = await self.fetcher.fetch_all(active_tickers, target_date)

            for ticker, sources in fetch_results.items():
                success_count = sum(sources.values())
                total_count = len(sources)
                logger.info("  %s: %d/%d sources fetched", ticker, success_count, total_count)

        logger.info("Running diagnostic engine...")
        results = await self.processor.process_all(active_tickers, target_date)

        for ticker, diagnostic in results.items():
            score_str = f"U={diagnostic.score_percentile:.1f}" if diagnostic.score_raw is not None else "U=N/A"
            logger.info("  %s: %s (%s)", ticker, diagnostic.regime_label, score_str)

        # --- Pass 2: Stress Check ---
        if update_focus:
            self._pass2_stress_update(results, target_date)
            self.universe.enforce_focus_cap(
                max_focus=30,
                scores={
                    t: d.score_percentile or 0.0
                    for t, d in results.items()
                    if self.universe.state.is_focus(t)
                },
                z_gex_values={
                    t: abs(d.z_scores.get("gex", 0.0))
                    for t, d in results.items()
                    if self.universe.state.is_focus(t)
                },
            )

        return results

    async def _pass1_update_focus(self, target_date: date) -> None:
        """Pass 1: Promote structural + event tickers to FOCUS.

        Uses ephemeral FMP and (optionally) FRED clients.
        FRED failure does not block the pipeline.
        """
        logger.info("[Pass 1] Updating structural + event focus...")

        # --- Structural Focus (ETF top-N) ---
        try:
            async with FMPClient(
                api_key=settings.fmp_api_key,
                rate_limit=settings.fmp_rate_limit,
            ) as fmp:
                # Structural: SPY top-15, QQQ top-10, DIA top-10
                by_etf = await fetch_all_structural_focus(fmp)
                deduped = deduplicate_structural_tickers(by_etf)

                structural_count = 0
                for ticker, constituent in deduped.items():
                    promoted = self.universe.promote_structural(
                        ticker=ticker,
                        index=constituent.etf,
                        rank=constituent.rank,
                        entry_date=target_date,
                    )
                    if promoted:
                        structural_count += 1

                logger.info(
                    "[Pass 1] Structural: %d new, %d total deduped",
                    structural_count, len(deduped),
                )

                # --- Event Focus (earnings) ---
                fred: FREDClient | None = None
                try:
                    if settings.fred_api_key:
                        fred = FREDClient(
                            api_key=settings.fred_api_key,
                            rate_limit=settings.fred_rate_limit,
                        )
                        await fred.__aenter__()
                except Exception as e:
                    logger.warning("[Pass 1] FRED client init failed: %s", e)
                    fred = None

                try:
                    events = await fetch_all_events(fmp, fred, target_date)

                    event_count = 0
                    for event in events:
                        if event.ticker:
                            promoted = self.universe.promote_event(
                                ticker=event.ticker,
                                event_type="earnings" if event.event_type == "earnings" else "macro",
                                event_date=event.event_date,
                                entry_date=target_date,
                            )
                            if promoted:
                                event_count += 1

                    logger.info(
                        "[Pass 1] Events: %d new promotions from %d events",
                        event_count, len(events),
                    )
                finally:
                    if fred is not None:
                        await fred.__aexit__(None, None, None)

        except Exception as e:
            logger.error("[Pass 1] Focus update failed: %s", e)

    def _pass2_stress_update(
        self,
        results: dict[str, DiagnosticResult],
        target_date: date,
    ) -> None:
        """Pass 2: Stress-check results and update FOCUS.

        Promotes tickers meeting stress thresholds.
        Increments inactive counter for non-stressed FOCUS tickers.
        Expires tickers inactive for 3+ days.
        """
        for ticker, diagnostic in results.items():
            if self.universe.state.is_core(ticker):
                continue

            unusualness = diagnostic.score_percentile if diagnostic.score_raw is not None else None
            z_gex = diagnostic.z_scores.get("gex")
            dark_share = diagnostic.raw_features.get("dark_share")
            z_block = diagnostic.z_scores.get("block_intensity")

            # NaN → None
            if dark_share is not None and np.isnan(dark_share):
                dark_share = None
            if z_block is not None and np.isnan(z_block):
                z_block = None

            promoted = self.universe.promote_if_stressed(
                ticker=ticker,
                unusualness=unusualness,
                z_gex=z_gex,
                dark_share=dark_share,
                z_block=z_block,
                entry_date=target_date,
            )

            if promoted:
                logger.info("  [FOCUS] Promoted %s (stress detected)", ticker)

            if self.universe.state.is_focus(ticker) and not promoted:
                self.universe.increment_inactive(ticker)

        expired = self.universe.expire_inactive(threshold=3)
        if expired:
            logger.info("  [FOCUS] Expired %d tickers: %s", len(expired), sorted(expired))

    async def run_single_ticker(
        self,
        ticker: str,
        target_date: date,
        fetch_data: bool = True,
    ) -> DiagnosticResult:
        """Run diagnostic pipeline for a single ticker.

        Ad-hoc analysis — does NOT update FOCUS universe.

        Args:
            ticker: Symbol to diagnose
            target_date: Date to diagnose
            fetch_data: Whether to fetch new data from API (default: True)

        Returns:
            DiagnosticResult for this ticker
        """
        ticker = ticker.upper()

        if fetch_data:
            logger.info("Fetching data for %s on %s...", ticker, target_date.strftime('%Y-%m-%d'))
            fetch_result = await self.fetcher.fetch_ticker(ticker, target_date)
            success_count = sum(fetch_result.values())
            total_count = len(fetch_result)
            logger.info("  %s: %d/%d sources fetched", ticker, success_count, total_count)

        logger.info("Running diagnostic engine for %s...", ticker)
        result = await self.processor.process_ticker(ticker, target_date)

        score_str = f"U={result.score_percentile:.1f}" if result.score_raw is not None else "U=N/A"
        logger.info("  %s: %s (%s)", ticker, result.regime_label, score_str)

        return result
