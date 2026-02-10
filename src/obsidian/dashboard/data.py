"""Data loading layer for Streamlit dashboard.

Bridges async Orchestrator pipeline to synchronous Streamlit context.
Uses a thread-based async bridge to avoid event loop conflicts with Streamlit.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import streamlit as st

logger = logging.getLogger(__name__)

from obsidian.pipeline.orchestrator import Orchestrator
from obsidian.pipeline.processor import DiagnosticResult
from obsidian.engine.scoring import FEATURE_WEIGHTS
from obsidian.universe.manager import CORE_TICKERS


_executor = ThreadPoolExecutor(max_workers=1)


def _run_async(coro):
    """Run an async coroutine from synchronous Streamlit context.

    Streamlit already runs an event loop, so ``asyncio.run()`` would raise
    "cannot be called from a running event loop".  Instead we spin up a
    *new* event loop in a dedicated thread.
    """
    def _target():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    future = _executor.submit(_target)
    return future.result()


def _get_orchestrator() -> Orchestrator:
    """Get or create a shared Orchestrator instance via session state."""
    if "orchestrator" not in st.session_state:
        st.session_state["orchestrator"] = Orchestrator()
    return st.session_state["orchestrator"]


def get_available_tickers() -> list[str]:
    """Return tickers available for selection (CORE + any FOCUS)."""
    orch = _get_orchestrator()
    active = orch.universe.get_active_tickers()
    # CORE first (sorted), then FOCUS (sorted)
    core = sorted(t for t in active if t in CORE_TICKERS)
    focus = sorted(t for t in active if t not in CORE_TICKERS)
    return core + focus


def fetch_and_diagnose(ticker: str, target_date: date) -> DiagnosticResult | None:
    """Fetch data from APIs and run diagnostic for a single ticker.

    Called explicitly by the user via the Fetch button.
    NOT cached — each call hits the APIs.

    Returns:
        DiagnosticResult on success, None on failure.
    """
    orch = _get_orchestrator()
    try:
        result = _run_async(
            orch.run_single_ticker(ticker, target_date, fetch_data=True)
        )
        # Store in session state for subsequent page renders
        _cache_key = f"diag_{ticker}_{target_date.isoformat()}"
        st.session_state[_cache_key] = result
        return result
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        return None


def diagnose_from_cache(ticker: str, target_date: date) -> DiagnosticResult | None:
    """Run diagnostic from cached data only (no API calls).

    Returns:
        DiagnosticResult on success, None on failure.
    """
    orch = _get_orchestrator()
    try:
        result = _run_async(
            orch.run_single_ticker(ticker, target_date, fetch_data=False)
        )
        _cache_key = f"diag_{ticker}_{target_date.isoformat()}"
        st.session_state[_cache_key] = result
        return result
    except Exception as e:
        st.error(f"Processing error: {e}")
        return None


def run_full_pipeline(target_date: date, fetch_data: bool = True) -> dict[str, DiagnosticResult] | None:
    """Run full two-pass pipeline (Pass 1 + main + Pass 2).

    This populates the FOCUS universe (structural + events + stress)
    and diagnoses all active tickers (CORE + FOCUS).

    Args:
        target_date: Date to diagnose
        fetch_data: Whether to fetch new data from APIs

    Returns:
        Dictionary mapping ticker -> DiagnosticResult, or None on failure.
    """
    orch = _get_orchestrator()
    try:
        results = _run_async(
            orch.run_diagnostics(target_date, fetch_data=fetch_data, update_focus=True)
        )
        # Cache each individual result for page navigation
        for ticker, diag in results.items():
            _cache_key = f"diag_{ticker}_{target_date.isoformat()}"
            st.session_state[_cache_key] = diag
        return results
    except Exception as e:
        st.error(f"Full pipeline error: {e}")
        logger.error("Full pipeline failed: %s", e, exc_info=True)
        return None


def get_cached_diagnostic(ticker: str, target_date: date) -> DiagnosticResult | None:
    """Retrieve a previously-computed diagnostic from session state."""
    _cache_key = f"diag_{ticker}_{target_date.isoformat()}"
    return st.session_state.get(_cache_key)


def get_historical_diagnostics(
    ticker: str,
    start_date: date,
    end_date: date,
) -> dict[date, DiagnosticResult]:
    """Return all cached diagnostics for a ticker in a date range.

    Only returns results that have already been computed and stored in
    session state. Does NOT fetch or process new data.
    """
    results = {}
    current = start_date
    while current <= end_date:
        diag = get_cached_diagnostic(ticker, current)
        if diag is not None:
            results[current] = diag
        current += timedelta(days=1)
    return results


def get_feature_weights() -> dict[str, float]:
    """Return the fixed scoring weights from the spec."""
    return FEATURE_WEIGHTS.copy()


# Human-readable labels for feature names
FEATURE_LABELS = {
    "dark_share": "Dark Pool Share",
    "gex": "Gamma Exposure",
    "venue_mix": "Venue Mix",
    "block_intensity": "Block Intensity",
    "iv_rank": "IV Rank",
    "dex": "Delta Exposure",
    "efficiency": "Efficiency",
    "impact": "Impact",
}


def feature_label(name: str) -> str:
    """Get human-readable label for a feature name."""
    return FEATURE_LABELS.get(name, name)


# Regime colour mapping for consistent badge rendering
REGIME_COLORS = {
    "Γ⁺": "#4CAF50",
    "Γ⁻": "#f44336",
    "DD": "#9C27B0",
    "ABS": "#2196F3",
    "DIST": "#FF9800",
    "NEU": "#9E9E9E",
    "UND": "#607D8B",
}


def regime_badge_html(label: str | None) -> str:
    """Return an inline HTML pill badge for a regime label.

    Args:
        label: Regime label (e.g. "Γ⁺", "DD") or None.

    Returns:
        HTML string for a coloured pill badge.
    """
    if not label:
        return '<span style="color:#999">—</span>'
    # Extract the short code (first token before " — ")
    short = label.split(" — ")[0].split(" ")[0].strip()
    color = REGIME_COLORS.get(short, "#666")
    return (
        f'<span style="background-color:{color}; color:white; '
        f'padding:2px 8px; border-radius:10px; font-weight:600; '
        f'font-size:0.85rem;">{short}</span>'
    )


def get_cached_date_count(ticker: str) -> int:
    """Return number of cached data dates for a ticker (from ParquetStore)."""
    orch = _get_orchestrator()
    dates = _run_async(orch.processor.cache.list_dates(ticker, "bars"))
    return len(dates)


def get_cached_date_range(ticker: str) -> tuple[date | None, date | None]:
    """Return (earliest, latest) cached date for a ticker."""
    orch = _get_orchestrator()
    dates = _run_async(orch.processor.cache.list_dates(ticker, "bars"))
    if not dates:
        return (None, None)
    return (dates[0], dates[-1])


def get_focus_diagnostics(target_date: date, etf: str | None = None) -> list[dict]:
    """Return FOCUS tickers with their cached diagnostics for cross-reference.

    Args:
        target_date: Date to look up cached diagnostics
        etf: If set, only return structural tickers from this ETF.
             Non-structural entries are always included.

    Returns:
        List of dicts with: ticker, reason, details, regime_label,
        score_percentile, z_scores. Sorted by reason then ticker.
    """
    orch = _get_orchestrator()
    focus = orch.universe.get_focus_tickers()

    reason_order = {"structural": 0, "stress": 1, "event": 2}
    results = []

    for entry in focus.values():
        # Filter structural by ETF if requested
        if etf and entry.reason == "structural":
            if f"in {etf}" not in entry.details:
                continue

        diag = get_cached_diagnostic(entry.ticker, target_date)
        results.append({
            "ticker": entry.ticker,
            "reason": entry.reason,
            "details": entry.details,
            "regime_label": diag.regime_label if diag else None,
            "regime": diag.regime if diag else None,
            "score_percentile": diag.score_percentile if diag else None,
            "z_scores": diag.z_scores if diag else None,
        })

    results.sort(key=lambda e: (reason_order.get(e["reason"], 9), e["ticker"]))
    return results


def get_focus_summary() -> dict:
    """Return summary of current FOCUS universe.

    Returns:
        Dictionary with: total, structural_count, stress_count, event_count,
        stress_zone_count (tickers in stress zone U >= 60).
    """
    orch = _get_orchestrator()
    focus = orch.universe.get_focus_tickers()

    structural = sum(1 for e in focus.values() if e.reason == "structural")
    stress = sum(1 for e in focus.values() if e.reason == "stress")
    event = sum(1 for e in focus.values() if e.reason == "event")

    return {
        "total": len(focus),
        "structural_count": structural,
        "stress_count": stress,
        "event_count": event,
    }


def get_focus_entries() -> list[dict]:
    """Return FOCUS entries with metadata for dashboard display.

    Returns:
        List of dicts with: ticker, reason, details, days_inactive, entry_date.
        Sorted by reason (structural first), then ticker.
    """
    orch = _get_orchestrator()
    focus = orch.universe.get_focus_tickers()

    reason_order = {"structural": 0, "stress": 1, "event": 2}

    entries = [
        {
            "ticker": entry.ticker,
            "reason": entry.reason,
            "details": entry.details,
            "days_inactive": entry.days_inactive,
            "entry_date": entry.entry_date.isoformat(),
        }
        for entry in focus.values()
    ]

    entries.sort(key=lambda e: (reason_order.get(e["reason"], 9), e["ticker"]))
    return entries
