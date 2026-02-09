"""Tests for Orchestrator — pipeline coordination.

Tests the Orchestrator by mocking Fetcher and Processor to verify:
- Correct wiring of Universe → Fetcher → Processor
- Focus universe updates based on diagnostic stress signals
- Single-ticker and multi-ticker modes
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from obsidian.engine import RegimeType
from obsidian.pipeline.orchestrator import Orchestrator
from obsidian.pipeline.processor import DiagnosticResult


# --- Fixtures ---


def make_diagnostic(
    ticker: str,
    regime: RegimeType = RegimeType.NEUTRAL,
    score_raw: float | None = 0.5,
    score_percentile: float | None = 25.0,
    z_scores: dict | None = None,
    raw_features: dict | None = None,
) -> DiagnosticResult:
    """Helper to create a DiagnosticResult for testing."""
    return DiagnosticResult(
        ticker=ticker,
        date=date(2024, 1, 15),
        regime=regime,
        regime_label=f"{regime.value} — {regime.get_description()}",
        score_raw=score_raw,
        score_percentile=score_percentile,
        interpretation="Normal" if score_percentile and score_percentile < 30 else "Elevated",
        z_scores=z_scores or {"gex": 0.5, "dex": -0.2},
        raw_features=raw_features or {"dark_share": 0.35, "gex": 500000},
        baseline_state="COMPLETE",
        explanation="Test diagnostic output.",
    )


class TestOrchestratorInit:
    """Test Orchestrator initialization."""

    def test_creates_components(self, tmp_path) -> None:
        """Initializes Universe, Fetcher, and Processor."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        assert orch.universe is not None
        assert orch.fetcher is not None
        assert orch.processor is not None


class TestRunSingleTicker:
    """Test single-ticker diagnostic pipeline."""

    @pytest.mark.asyncio
    async def test_fetch_and_process(self, tmp_path) -> None:
        """Fetches data then processes through engine."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)
        spy_result = make_diagnostic("SPY")

        # Mock fetcher and processor
        orch.fetcher.fetch_ticker = AsyncMock(return_value={
            "dark_pool": True, "greeks": True, "iv_rank": True,
            "bars": True, "quote": True,
        })
        orch.processor.process_ticker = AsyncMock(return_value=spy_result)

        result = await orch.run_single_ticker("SPY", target)

        assert result.ticker == "SPY"
        assert result.regime == RegimeType.NEUTRAL
        orch.fetcher.fetch_ticker.assert_called_once_with("SPY", target)
        orch.processor.process_ticker.assert_called_once_with("SPY", target)

    @pytest.mark.asyncio
    async def test_skip_fetch(self, tmp_path) -> None:
        """fetch_data=False skips API calls, only processes."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        orch.fetcher.fetch_ticker = AsyncMock()
        orch.processor.process_ticker = AsyncMock(return_value=make_diagnostic("SPY"))

        await orch.run_single_ticker("SPY", target, fetch_data=False)

        orch.fetcher.fetch_ticker.assert_not_called()
        orch.processor.process_ticker.assert_called_once()

    @pytest.mark.asyncio
    async def test_uppercases_ticker(self, tmp_path) -> None:
        """Ticker is uppercased."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        orch.fetcher.fetch_ticker = AsyncMock(return_value={
            "dark_pool": True, "greeks": True, "iv_rank": True,
            "bars": True, "quote": True,
        })
        orch.processor.process_ticker = AsyncMock(return_value=make_diagnostic("SPY"))

        await orch.run_single_ticker("spy", target)

        # Fetcher should be called with uppercase
        orch.fetcher.fetch_ticker.assert_called_once_with("SPY", target)


class TestRunDiagnostics:
    """Test full multi-ticker diagnostic run."""

    @pytest.mark.asyncio
    async def test_processes_core_tickers(self, tmp_path) -> None:
        """Processes all CORE tickers (SPY, QQQ, IWM, DIA)."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        # Mock Pass 1 to avoid hitting real APIs
        orch._pass1_update_focus = AsyncMock()
        orch.fetcher.fetch_all = AsyncMock(return_value={
            t: {"dark_pool": True, "greeks": True, "bars": True, "iv_rank": True, "quote": True}
            for t in ["SPY", "QQQ", "IWM", "DIA"]
        })
        orch.processor.process_all = AsyncMock(return_value={
            t: make_diagnostic(t) for t in ["SPY", "QQQ", "IWM", "DIA"]
        })

        results = await orch.run_diagnostics(target)

        assert len(results) == 4
        assert "SPY" in results
        assert "QQQ" in results
        assert "IWM" in results
        assert "DIA" in results
        orch._pass1_update_focus.assert_called_once_with(target)

    @pytest.mark.asyncio
    async def test_skip_fetch_flag(self, tmp_path) -> None:
        """fetch_data=False skips API calls and Pass 1."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        orch._pass1_update_focus = AsyncMock()
        orch.fetcher.fetch_all = AsyncMock()
        orch.processor.process_all = AsyncMock(return_value={
            "SPY": make_diagnostic("SPY"),
        })

        await orch.run_diagnostics(target, fetch_data=False)

        orch.fetcher.fetch_all.assert_not_called()
        orch._pass1_update_focus.assert_not_called()
        orch.processor.process_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_pass2_enforces_cap(self, tmp_path) -> None:
        """Pass 2 calls enforce_focus_cap after stress update."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        orch._pass1_update_focus = AsyncMock()
        orch.fetcher.fetch_all = AsyncMock(return_value={
            "SPY": {"dark_pool": True, "greeks": True, "bars": True, "iv_rank": True, "quote": True},
        })
        orch.processor.process_all = AsyncMock(return_value={
            "SPY": make_diagnostic("SPY"),
        })

        # Spy on enforce_focus_cap
        original_cap = orch.universe.enforce_focus_cap
        orch.universe.enforce_focus_cap = MagicMock(wraps=original_cap)

        await orch.run_diagnostics(target, update_focus=True)

        orch.universe.enforce_focus_cap.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_focus_false_skips_both_passes(self, tmp_path) -> None:
        """update_focus=False skips Pass 1 and Pass 2."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        orch._pass1_update_focus = AsyncMock()
        orch.fetcher.fetch_all = AsyncMock(return_value={
            "SPY": {"dark_pool": True, "greeks": True, "bars": True, "iv_rank": True, "quote": True},
        })
        orch.processor.process_all = AsyncMock(return_value={
            "SPY": make_diagnostic("SPY"),
        })

        await orch.run_diagnostics(target, update_focus=False)

        orch._pass1_update_focus.assert_not_called()


class TestFocusUniverseUpdate:
    """Test FOCUS universe updates based on diagnostic stress signals."""

    @pytest.mark.asyncio
    async def test_stress_promotes_to_focus(self, tmp_path) -> None:
        """Ticker with high unusualness gets promoted to FOCUS."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        # Add AAPL as a non-CORE ticker with high stress
        stressed_result = make_diagnostic(
            "AAPL", score_percentile=85.0, z_scores={"gex": 2.5}
        )

        results = {
            "SPY": make_diagnostic("SPY"),
            "AAPL": stressed_result,
        }

        orch._pass2_stress_update(results, target)

        # AAPL should be in FOCUS (z_gex > 2.0)
        assert orch.universe.state.is_focus("AAPL")

    @pytest.mark.asyncio
    async def test_core_tickers_not_promoted(self, tmp_path) -> None:
        """CORE tickers are never promoted to FOCUS (already active)."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        results = {
            "SPY": make_diagnostic("SPY", score_percentile=95.0, z_scores={"gex": 3.0}),
        }

        orch._pass2_stress_update(results, target)

        # SPY is CORE, should NOT be in FOCUS
        assert not orch.universe.state.is_focus("SPY")

    @pytest.mark.asyncio
    async def test_no_stress_increments_inactive(self, tmp_path) -> None:
        """Non-stressed FOCUS ticker gets inactive counter incremented."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        # Manually add AAPL to FOCUS first
        orch.universe.promote_if_stressed(
            ticker="AAPL", unusualness=80.0, z_gex=2.5,
            dark_share=None, entry_date=date(2024, 1, 10),
        )
        assert orch.universe.state.is_focus("AAPL")

        # Now run update with normal (non-stressed) AAPL result
        results = {
            "AAPL": make_diagnostic(
                "AAPL", score_percentile=15.0, z_scores={"gex": 0.3}
            ),
        }

        orch._pass2_stress_update(results, target)

        # AAPL should still be in FOCUS but inactive counter should be > 0
        assert orch.universe.state.is_focus("AAPL")
        entry = orch.universe.state.focus.get("AAPL")
        assert entry is not None
        assert entry.days_inactive >= 1

    @pytest.mark.asyncio
    async def test_undetermined_does_not_crash(self, tmp_path) -> None:
        """UNDETERMINED results (no scores) handled gracefully."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        results = {
            "AAPL": make_diagnostic(
                "AAPL",
                regime=RegimeType.UNDETERMINED,
                score_raw=None,
                score_percentile=None,
                z_scores={},
            ),
        }

        # Should not raise
        orch._pass2_stress_update(results, target)

    def test_pass2_dark_share_from_raw_features(self, tmp_path) -> None:
        """Pass 2 reads dark_share from raw_features (not z_scores)."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        results = {
            "NVDA": make_diagnostic(
                "NVDA",
                score_percentile=30.0,
                z_scores={"gex": 0.5},
                raw_features={"dark_share": 0.70, "gex": 500000},
            ),
        }

        orch._pass2_stress_update(results, target)

        # NVDA should be promoted (dark_share >= 0.65)
        assert orch.universe.state.is_focus("NVDA")
        assert "DarkShare" in orch.universe.state.focus["NVDA"].details

    def test_pass2_z_block_promotes(self, tmp_path) -> None:
        """Pass 2 promotes on |z_block| >= 2.0."""
        orch = Orchestrator(cache_dir=str(tmp_path))
        target = date(2024, 1, 15)

        results = {
            "TSLA": make_diagnostic(
                "TSLA",
                score_percentile=30.0,
                z_scores={"gex": 0.5, "block_intensity": 2.5},
                raw_features={"dark_share": 0.30},
            ),
        }

        orch._pass2_stress_update(results, target)

        assert orch.universe.state.is_focus("TSLA")


class TestPass1:
    """Test Pass 1 — structural + event focus."""

    @pytest.mark.asyncio
    @patch("obsidian.pipeline.orchestrator.fetch_all_events", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.fetch_all_structural_focus", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.FMPClient")
    async def test_pass1_promotes_structural(
        self, MockFMP, mock_structural, mock_events, tmp_path
    ) -> None:
        """Pass 1 promotes structural tickers."""
        from obsidian.universe.structural import IndexConstituent

        # Setup FMP mock context manager
        fmp_instance = AsyncMock()
        MockFMP.return_value.__aenter__ = AsyncMock(return_value=fmp_instance)
        MockFMP.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_structural.return_value = {
            "SPY": [IndexConstituent("AAPL", "SPY", 1, 7.2)],
            "QQQ": [],
            "DIA": [],
        }
        mock_events.return_value = []

        orch = Orchestrator(cache_dir=str(tmp_path))
        await orch._pass1_update_focus(date(2024, 1, 15))

        assert orch.universe.state.is_focus("AAPL")
        entry = orch.universe.state.focus["AAPL"]
        assert entry.reason == "structural"

    @pytest.mark.asyncio
    @patch("obsidian.pipeline.orchestrator.fetch_all_events", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.fetch_all_structural_focus", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.FMPClient")
    async def test_pass1_promotes_earnings_events(
        self, MockFMP, mock_structural, mock_events, tmp_path
    ) -> None:
        """Pass 1 promotes tickers with earnings events."""
        from obsidian.universe.events import EventEntry

        fmp_instance = AsyncMock()
        MockFMP.return_value.__aenter__ = AsyncMock(return_value=fmp_instance)
        MockFMP.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_structural.return_value = {"SPY": [], "QQQ": [], "DIA": []}
        mock_events.return_value = [
            EventEntry(
                event_type="earnings",
                event_date=date(2024, 1, 25),
                ticker="MSFT",
                description="Earnings on 2024-01-25",
            ),
        ]

        orch = Orchestrator(cache_dir=str(tmp_path))
        await orch._pass1_update_focus(date(2024, 1, 24))

        assert orch.universe.state.is_focus("MSFT")
        assert orch.universe.state.focus["MSFT"].reason == "event"

    @pytest.mark.asyncio
    @patch("obsidian.pipeline.orchestrator.fetch_all_events", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.fetch_all_structural_focus", new_callable=AsyncMock)
    @patch("obsidian.pipeline.orchestrator.FMPClient")
    async def test_pass1_macro_events_no_ticker(
        self, MockFMP, mock_structural, mock_events, tmp_path
    ) -> None:
        """Macro events (ticker=None) should NOT promote anyone."""
        from obsidian.universe.events import EventEntry

        fmp_instance = AsyncMock()
        MockFMP.return_value.__aenter__ = AsyncMock(return_value=fmp_instance)
        MockFMP.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_structural.return_value = {"SPY": [], "QQQ": [], "DIA": []}
        mock_events.return_value = [
            EventEntry(
                event_type="macro",
                event_date=date(2024, 1, 11),
                ticker=None,
                description="CPI release",
            ),
        ]

        orch = Orchestrator(cache_dir=str(tmp_path))
        await orch._pass1_update_focus(date(2024, 1, 11))

        # No tickers promoted (macro events have ticker=None)
        assert len(orch.universe.state.focus) == 0

    @pytest.mark.asyncio
    @patch("obsidian.pipeline.orchestrator.FMPClient")
    async def test_pass1_fmp_failure_graceful(self, MockFMP, tmp_path) -> None:
        """Pass 1 handles FMP failure gracefully."""
        MockFMP.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("FMP down")
        )
        MockFMP.return_value.__aexit__ = AsyncMock(return_value=False)

        orch = Orchestrator(cache_dir=str(tmp_path))
        # Should not raise
        await orch._pass1_update_focus(date(2024, 1, 15))

        # No FOCUS promoted
        assert len(orch.universe.state.focus) == 0
