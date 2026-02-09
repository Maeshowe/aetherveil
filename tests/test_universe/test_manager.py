"""Tests for UniverseManager — CORE + FOCUS ticker management.

Covers the two-tier universe system:
- CORE: Always-active market structure nodes (SPY, QQQ, IWM, DIA)
- FOCUS: Dynamic tickers promoted by stress, structure, or events
"""

from datetime import date

import pytest

from obsidian.universe.manager import (
    CORE_TICKERS,
    FocusEntry,
    UniverseManager,
    UniverseState,
)


class TestCoreTickers:
    """Verify CORE_TICKERS constant."""

    def test_core_is_frozen(self) -> None:
        """CORE tickers are a frozenset (immutable)."""
        assert isinstance(CORE_TICKERS, frozenset)

    def test_core_contains_expected(self) -> None:
        """CORE has exactly SPY, QQQ, IWM, DIA."""
        assert CORE_TICKERS == frozenset(["SPY", "QQQ", "IWM", "DIA"])


class TestUniverseState:
    """Tests for UniverseState dataclass."""

    def test_all_tickers_core_only(self) -> None:
        """With no FOCUS, all_tickers returns CORE."""
        state = UniverseState()
        assert state.all_tickers() == set(CORE_TICKERS)

    def test_all_tickers_includes_focus(self) -> None:
        """all_tickers returns CORE + FOCUS."""
        state = UniverseState()
        state.focus["NVDA"] = FocusEntry(
            ticker="NVDA", entry_date=date(2024, 1, 15),
            reason="stress", details="test"
        )
        result = state.all_tickers()
        assert "NVDA" in result
        assert "SPY" in result
        assert len(result) == 5

    def test_is_core_true(self) -> None:
        """is_core returns True for SPY, QQQ, IWM, DIA."""
        state = UniverseState()
        for ticker in ["SPY", "QQQ", "IWM", "DIA"]:
            assert state.is_core(ticker) is True

    def test_is_core_false(self) -> None:
        """is_core returns False for non-CORE tickers."""
        state = UniverseState()
        assert state.is_core("AAPL") is False
        assert state.is_core("NVDA") is False

    def test_is_core_case_insensitive(self) -> None:
        """is_core handles lowercase input."""
        state = UniverseState()
        assert state.is_core("spy") is True

    def test_is_focus_true(self) -> None:
        """is_focus returns True for promoted tickers."""
        state = UniverseState()
        state.focus["NVDA"] = FocusEntry(
            ticker="NVDA", entry_date=date(2024, 1, 15),
            reason="stress", details="test"
        )
        assert state.is_focus("NVDA") is True

    def test_is_focus_false(self) -> None:
        """is_focus returns False for non-FOCUS tickers."""
        state = UniverseState()
        assert state.is_focus("AAPL") is False


class TestUniverseManagerInit:
    """Tests for UniverseManager initialization."""

    def test_fresh_manager_has_core(self) -> None:
        """New manager starts with CORE tickers."""
        mgr = UniverseManager()
        assert mgr.get_active_tickers() == set(CORE_TICKERS)

    def test_get_core_tickers(self) -> None:
        """get_core_tickers returns frozenset of SPY/QQQ/IWM/DIA."""
        mgr = UniverseManager()
        assert mgr.get_core_tickers() == CORE_TICKERS

    def test_get_focus_tickers_empty(self) -> None:
        """get_focus_tickers is empty initially."""
        mgr = UniverseManager()
        assert mgr.get_focus_tickers() == {}

    def test_get_focus_returns_copy(self) -> None:
        """get_focus_tickers returns a copy, not a reference."""
        mgr = UniverseManager()
        focus = mgr.get_focus_tickers()
        focus["FAKE"] = "should not appear"
        assert "FAKE" not in mgr.get_focus_tickers()


class TestPromoteStructural:
    """Tests for promote_structural() — index weight promotion."""

    def test_promotes_within_spy_threshold(self) -> None:
        """Rank <= 15 for SPY promotes to FOCUS."""
        mgr = UniverseManager()
        result = mgr.promote_structural("AAPL", "SPY", rank=5, entry_date=date(2024, 1, 15))
        assert result is True
        assert mgr.state.is_focus("AAPL")
        assert mgr.state.focus["AAPL"].reason == "structural"

    def test_rejects_above_spy_threshold(self) -> None:
        """Rank > 15 for SPY does not promote."""
        mgr = UniverseManager()
        result = mgr.promote_structural("AAPL", "SPY", rank=20, entry_date=date(2024, 1, 15))
        assert result is False
        assert not mgr.state.is_focus("AAPL")

    def test_qqq_threshold_is_10(self) -> None:
        """QQQ threshold is 10, not 15."""
        mgr = UniverseManager()
        assert mgr.promote_structural("NVDA", "QQQ", rank=10, entry_date=date(2024, 1, 15)) is True
        assert mgr.promote_structural("INTC", "QQQ", rank=11, entry_date=date(2024, 1, 15)) is False

    def test_iwm_threshold_is_10(self) -> None:
        """IWM threshold is 10."""
        mgr = UniverseManager()
        assert mgr.promote_structural("XYZ", "IWM", rank=10, entry_date=date(2024, 1, 15)) is True
        assert mgr.promote_structural("ABC", "IWM", rank=11, entry_date=date(2024, 1, 15)) is False

    def test_already_in_focus_resets_inactive(self) -> None:
        """Re-promoting an existing FOCUS ticker resets days_inactive."""
        mgr = UniverseManager()
        mgr.promote_structural("AAPL", "SPY", rank=5, entry_date=date(2024, 1, 15))
        mgr.state.focus["AAPL"].days_inactive = 2
        result = mgr.promote_structural("AAPL", "SPY", rank=5, entry_date=date(2024, 1, 16))
        assert result is False  # Already in FOCUS
        assert mgr.state.focus["AAPL"].days_inactive == 0  # Reset

    def test_details_includes_rank_and_index(self) -> None:
        """FocusEntry details include rank and index name."""
        mgr = UniverseManager()
        mgr.promote_structural("NVDA", "QQQ", rank=3, entry_date=date(2024, 1, 15))
        assert "Rank 3" in mgr.state.focus["NVDA"].details
        assert "QQQ" in mgr.state.focus["NVDA"].details


class TestPromoteIfStressed:
    """Tests for promote_if_stressed() — microstructure stress promotion."""

    def test_promotes_on_high_unusualness(self) -> None:
        """Unusualness >= 70 triggers promotion."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=75.0, z_gex=None, dark_share=None,
            entry_date=date(2024, 1, 15)
        )
        assert result is True
        assert mgr.state.focus["NVDA"].reason == "stress"

    def test_promotes_on_high_z_gex_positive(self) -> None:
        """|z_gex| >= 2.0 (positive) triggers promotion."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=2.5, dark_share=None,
            entry_date=date(2024, 1, 15)
        )
        assert result is True

    def test_promotes_on_high_z_gex_negative(self) -> None:
        """|z_gex| >= 2.0 (negative) triggers promotion."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=-2.1, dark_share=None,
            entry_date=date(2024, 1, 15)
        )
        assert result is True

    def test_promotes_on_high_dark_share(self) -> None:
        """dark_share >= 0.65 triggers promotion."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=None, dark_share=0.70,
            entry_date=date(2024, 1, 15)
        )
        assert result is True

    def test_no_promote_below_thresholds(self) -> None:
        """Values below all thresholds do not promote."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=50.0, z_gex=1.0, dark_share=0.30,
            entry_date=date(2024, 1, 15)
        )
        assert result is False

    def test_no_promote_all_none(self) -> None:
        """All None values do not promote."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=None, dark_share=None,
            entry_date=date(2024, 1, 15)
        )
        assert result is False

    def test_already_in_focus_resets_inactive(self) -> None:
        """Re-stress on existing FOCUS ticker resets days_inactive."""
        mgr = UniverseManager()
        mgr.promote_if_stressed(
            "NVDA", unusualness=80.0, z_gex=None, dark_share=None,
            entry_date=date(2024, 1, 15)
        )
        mgr.state.focus["NVDA"].days_inactive = 2
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=80.0, z_gex=None, dark_share=None,
            entry_date=date(2024, 1, 16)
        )
        assert result is False
        assert mgr.state.focus["NVDA"].days_inactive == 0

    def test_details_lists_stress_reasons(self) -> None:
        """FocusEntry details list all triggered conditions."""
        mgr = UniverseManager()
        mgr.promote_if_stressed(
            "NVDA", unusualness=80.0, z_gex=-2.5, dark_share=0.70,
            entry_date=date(2024, 1, 15)
        )
        details = mgr.state.focus["NVDA"].details
        assert "U=" in details
        assert "Z_GEX=" in details
        assert "DarkShare=" in details


class TestPromoteEvent:
    """Tests for promote_event() — calendar event promotion."""

    def test_promotes_on_earnings(self) -> None:
        """Earnings event promotes to FOCUS."""
        mgr = UniverseManager()
        result = mgr.promote_event(
            "NVDA", event_type="earnings",
            event_date=date(2024, 1, 20), entry_date=date(2024, 1, 15)
        )
        assert result is True
        assert mgr.state.focus["NVDA"].reason == "event"
        assert "earnings" in mgr.state.focus["NVDA"].details

    def test_already_in_focus_returns_false(self) -> None:
        """Re-event on existing FOCUS ticker returns False."""
        mgr = UniverseManager()
        mgr.promote_event("NVDA", "earnings", date(2024, 1, 20), date(2024, 1, 15))
        result = mgr.promote_event("NVDA", "rebalancing", date(2024, 1, 25), date(2024, 1, 16))
        assert result is False


class TestInactivityTracking:
    """Tests for mark_active() and increment_inactive()."""

    def test_mark_active_resets_counter(self) -> None:
        """mark_active sets days_inactive to 0."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.state.focus["NVDA"].days_inactive = 2
        mgr.mark_active("NVDA")
        assert mgr.state.focus["NVDA"].days_inactive == 0

    def test_increment_inactive(self) -> None:
        """increment_inactive adds 1 to counter."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.increment_inactive("NVDA")
        assert mgr.state.focus["NVDA"].days_inactive == 1
        mgr.increment_inactive("NVDA")
        assert mgr.state.focus["NVDA"].days_inactive == 2

    def test_mark_active_noop_for_non_focus(self) -> None:
        """mark_active is a no-op for tickers not in FOCUS."""
        mgr = UniverseManager()
        mgr.mark_active("AAPL")  # Should not raise

    def test_increment_inactive_noop_for_non_focus(self) -> None:
        """increment_inactive is a no-op for tickers not in FOCUS."""
        mgr = UniverseManager()
        mgr.increment_inactive("AAPL")  # Should not raise


class TestExpireInactive:
    """Tests for expire_inactive() — FOCUS cleanup."""

    def test_expires_at_threshold(self) -> None:
        """Tickers with days_inactive >= threshold are removed."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        for _ in range(3):
            mgr.increment_inactive("NVDA")
        expired = mgr.expire_inactive(threshold=3)
        assert "NVDA" in expired
        assert not mgr.state.is_focus("NVDA")

    def test_does_not_expire_below_threshold(self) -> None:
        """Tickers below threshold are kept."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.increment_inactive("NVDA")
        mgr.increment_inactive("NVDA")
        expired = mgr.expire_inactive(threshold=3)
        assert expired == set()
        assert mgr.state.is_focus("NVDA")

    def test_returns_removed_set(self) -> None:
        """Returns the set of removed tickers."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.promote_if_stressed("TSLA", unusualness=75.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        for _ in range(3):
            mgr.increment_inactive("NVDA")
        # TSLA stays active
        expired = mgr.expire_inactive(threshold=3)
        assert expired == {"NVDA"}
        assert mgr.state.is_focus("TSLA")


class TestResetFocus:
    """Tests for reset_focus()."""

    def test_clears_focus_keeps_core(self) -> None:
        """reset_focus removes all FOCUS, CORE unchanged."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.promote_if_stressed("TSLA", unusualness=75.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.reset_focus()
        assert mgr.get_focus_tickers() == {}
        assert mgr.get_active_tickers() == set(CORE_TICKERS)


class TestCaseSensitivity:
    """Test that ticker inputs are uppercased."""

    def test_promote_uppercases(self) -> None:
        """Lowercase ticker input is uppercased."""
        mgr = UniverseManager()
        mgr.promote_if_stressed("nvda", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        assert "NVDA" in mgr.state.focus
        assert mgr.state.is_focus("nvda")


class TestZBlockStress:
    """Test z_block stress promotion."""

    def test_z_block_high_promotes(self) -> None:
        """High |z_block| promotes to FOCUS."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=None,
            dark_share=None, z_block=2.5, entry_date=date(2024, 1, 15)
        )
        assert result is True
        assert "Z_block" in mgr.state.focus["NVDA"].details

    def test_z_block_negative_high_promotes(self) -> None:
        """Negative z_block with |value| >= 2.0 promotes."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "TSLA", unusualness=None, z_gex=None,
            dark_share=None, z_block=-2.1, entry_date=date(2024, 1, 15)
        )
        assert result is True

    def test_z_block_below_threshold(self) -> None:
        """z_block below threshold does NOT promote."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=None,
            dark_share=None, z_block=1.5, entry_date=date(2024, 1, 15)
        )
        assert result is False

    def test_z_block_none_ignored(self) -> None:
        """z_block=None is ignored (no promotion)."""
        mgr = UniverseManager()
        result = mgr.promote_if_stressed(
            "NVDA", unusualness=None, z_gex=None,
            dark_share=None, z_block=None, entry_date=date(2024, 1, 15)
        )
        assert result is False


class TestEnforceFocusCap:
    """Test enforce_focus_cap()."""

    def test_under_cap_no_removal(self) -> None:
        """No removal when under cap."""
        mgr = UniverseManager()
        mgr.promote_if_stressed(
            "NVDA", unusualness=80.0, z_gex=None,
            dark_share=None, entry_date=date(2024, 1, 15)
        )
        removed = mgr.enforce_focus_cap(max_focus=30)
        assert removed == set()
        assert mgr.state.is_focus("NVDA")

    def test_over_cap_removes_lowest(self) -> None:
        """Exceeding cap removes lowest-score tickers."""
        mgr = UniverseManager()
        for i in range(5):
            mgr.promote_if_stressed(
                f"STOCK{i}", unusualness=80.0, z_gex=None,
                dark_share=None, entry_date=date(2024, 1, 15)
            )
        scores = {f"STOCK{i}": float(i * 10) for i in range(5)}

        removed = mgr.enforce_focus_cap(max_focus=3, scores=scores)
        assert len(removed) == 2
        # Lowest scores (STOCK0=0.0, STOCK1=10.0) should be removed
        assert "STOCK0" in removed
        assert "STOCK1" in removed
        assert len(mgr.state.focus) == 3

    def test_structural_always_kept(self) -> None:
        """Structural tickers are never removed by cap."""
        mgr = UniverseManager()
        # Add structural
        mgr.promote_structural("AAPL", "SPY", 1, date(2024, 1, 15))
        mgr.promote_structural("MSFT", "SPY", 2, date(2024, 1, 15))
        # Add stress
        for i in range(5):
            mgr.promote_if_stressed(
                f"STOCK{i}", unusualness=80.0, z_gex=None,
                dark_share=None, entry_date=date(2024, 1, 15)
            )
        scores = {f"STOCK{i}": float(i * 10) for i in range(5)}

        removed = mgr.enforce_focus_cap(max_focus=5, scores=scores)

        # 2 structural + 3 stress = 5 total. Removed 2 lowest-score stress.
        assert "AAPL" in mgr.state.focus
        assert "MSFT" in mgr.state.focus
        assert len(mgr.state.focus) == 5
        assert len(removed) == 2

    def test_cap_with_z_gex_tiebreaker(self) -> None:
        """z_gex breaks ties when scores are equal."""
        mgr = UniverseManager()
        mgr.promote_if_stressed(
            "A", unusualness=80.0, z_gex=None,
            dark_share=None, entry_date=date(2024, 1, 15)
        )
        mgr.promote_if_stressed(
            "B", unusualness=80.0, z_gex=None,
            dark_share=None, entry_date=date(2024, 1, 15)
        )
        # Same score, different z_gex
        scores = {"A": 50.0, "B": 50.0}
        z_gex = {"A": 3.0, "B": 1.0}

        removed = mgr.enforce_focus_cap(max_focus=1, scores=scores, z_gex_values=z_gex)
        assert len(removed) == 1
        assert "B" in removed  # lower |z_gex|
        assert "A" in mgr.state.focus

    def test_structural_exceeds_cap_no_cut(self) -> None:
        """If structural alone >= cap, no tickers are cut."""
        mgr = UniverseManager()
        for i in range(5):
            mgr.promote_structural(f"S{i}", "SPY", i + 1, date(2024, 1, 15))

        removed = mgr.enforce_focus_cap(max_focus=3)
        assert removed == set()
        assert len(mgr.state.focus) == 5
