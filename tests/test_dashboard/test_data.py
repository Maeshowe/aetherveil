"""Tests for dashboard data layer — focus helpers."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from obsidian.universe.manager import FocusEntry, UniverseManager


class TestGetFocusSummary:
    """Test get_focus_summary()."""

    @patch("obsidian.dashboard.data.st")
    def test_empty_focus(self, mock_st):
        """No focus tickers returns all zeros."""
        orch = MagicMock()
        orch.universe = UniverseManager()
        mock_st.session_state = {"orchestrator": orch}

        from obsidian.dashboard.data import get_focus_summary
        summary = get_focus_summary()

        assert summary["total"] == 0
        assert summary["structural_count"] == 0
        assert summary["stress_count"] == 0
        assert summary["event_count"] == 0

    @patch("obsidian.dashboard.data.st")
    def test_mixed_focus(self, mock_st):
        """Mix of structural, stress, and event entries."""
        orch = MagicMock()
        mgr = UniverseManager()
        mgr.promote_structural("AAPL", "SPY", 1, date(2024, 1, 15))
        mgr.promote_structural("MSFT", "SPY", 2, date(2024, 1, 15))
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.promote_event("TSLA", "earnings", date(2024, 1, 25), date(2024, 1, 15))
        orch.universe = mgr
        mock_st.session_state = {"orchestrator": orch}

        from obsidian.dashboard.data import get_focus_summary
        summary = get_focus_summary()

        assert summary["total"] == 4
        assert summary["structural_count"] == 2
        assert summary["stress_count"] == 1
        assert summary["event_count"] == 1


class TestGetFocusEntries:
    """Test get_focus_entries()."""

    @patch("obsidian.dashboard.data.st")
    def test_sorted_by_reason_then_ticker(self, mock_st):
        """Entries sorted: structural first, then stress, then event."""
        orch = MagicMock()
        mgr = UniverseManager()
        mgr.promote_event("TSLA", "earnings", date(2024, 1, 25), date(2024, 1, 15))
        mgr.promote_if_stressed("NVDA", unusualness=80.0, z_gex=None, dark_share=None, entry_date=date(2024, 1, 15))
        mgr.promote_structural("AAPL", "SPY", 1, date(2024, 1, 15))
        orch.universe = mgr
        mock_st.session_state = {"orchestrator": orch}

        from obsidian.dashboard.data import get_focus_entries
        entries = get_focus_entries()

        assert len(entries) == 3
        # Structural first
        assert entries[0]["ticker"] == "AAPL"
        assert entries[0]["reason"] == "structural"
        # Then stress
        assert entries[1]["ticker"] == "NVDA"
        assert entries[1]["reason"] == "stress"
        # Then event
        assert entries[2]["ticker"] == "TSLA"
        assert entries[2]["reason"] == "event"

    @patch("obsidian.dashboard.data.st")
    def test_empty_focus_entries(self, mock_st):
        """Empty focus returns empty list."""
        orch = MagicMock()
        orch.universe = UniverseManager()
        mock_st.session_state = {"orchestrator": orch}

        from obsidian.dashboard.data import get_focus_entries
        entries = get_focus_entries()

        assert entries == []

    @patch("obsidian.dashboard.data.st")
    def test_entry_has_required_fields(self, mock_st):
        """Each entry dict has required fields."""
        orch = MagicMock()
        mgr = UniverseManager()
        mgr.promote_structural("AAPL", "SPY", 1, date(2024, 1, 15))
        orch.universe = mgr
        mock_st.session_state = {"orchestrator": orch}

        from obsidian.dashboard.data import get_focus_entries
        entries = get_focus_entries()

        entry = entries[0]
        assert "ticker" in entry
        assert "reason" in entry
        assert "details" in entry
        assert "days_inactive" in entry
        assert "entry_date" in entry
