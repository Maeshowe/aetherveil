"""Daily State page - Current regime and unusualness score."""

import math

import streamlit as st
from datetime import date
import plotly.graph_objects as go

from obsidian.dashboard.data import (
    get_cached_diagnostic,
    get_feature_weights,
    get_focus_entries,
    get_focus_summary,
    feature_label,
)
from obsidian.engine.classifier import RegimeType
from obsidian.universe.manager import CORE_TICKERS


# Map RegimeType enum value to CSS class
_REGIME_CSS = {
    RegimeType.GAMMA_POSITIVE: "regime-gamma-pos",
    RegimeType.GAMMA_NEGATIVE: "regime-gamma-neg",
    RegimeType.DARK_DOMINANT: "regime-dark-dom",
    RegimeType.ABSORPTION: "regime-absorption",
    RegimeType.DISTRIBUTION: "regime-distribution",
    RegimeType.NEUTRAL: "regime-neutral",
    RegimeType.UNDETERMINED: "regime-undetermined",
}


def render(ticker: str, end_date: date) -> None:
    """Render the Daily State page.

    Args:
        ticker: Instrument ticker symbol
        end_date: Date for diagnostic
    """
    st.markdown("## Daily State")
    st.markdown(f"**{ticker}** -- {end_date.strftime('%Y-%m-%d')}")

    diag = get_cached_diagnostic(ticker, end_date)

    if diag is None:
        st.info("No diagnostic data loaded. Use **Fetch + Run** or **Run (cached)** in the sidebar.")
        return

    # --- Regime Badge ---
    st.markdown("### Current Regime")

    badge_class = _REGIME_CSS.get(diag.regime, "regime-neutral")
    st.markdown(
        f'<div class="{badge_class} regime-badge">{diag.regime_label}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # --- Unusualness Score Gauge ---
    st.markdown("### Unusualness Score")

    if diag.score_raw is not None:
        percentile = diag.score_percentile or 0.0

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=percentile,
            title={'text': "Percentile"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 30], 'color': "lightgray"},
                    {'range': [30, 60], 'color': "gray"},
                    {'range': [60, 80], 'color': "lightsalmon"},
                    {'range': [80, 100], 'color': "lightcoral"},
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 80,
                },
            },
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, width="stretch")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Raw Score", f"{diag.score_raw:.3f}")
        with col2:
            st.metric("Percentile", f"{percentile:.1f}")
        with col3:
            st.metric("Interpretation", diag.interpretation or "N/A")
    else:
        st.warning("Score unavailable (insufficient baseline data).")

    st.markdown("---")

    # --- Top Drivers ---
    st.markdown("### Feature Z-Scores")

    weights = get_feature_weights()

    if diag.z_scores:
        # Sort by absolute z-score descending; NaN last
        def _sort_key(kv: tuple[str, float]) -> float:
            v = kv[1]
            return abs(v) if not (math.isnan(v) if isinstance(v, float) else False) else -1

        for name, z_val in sorted(diag.z_scores.items(), key=_sort_key, reverse=True):
            weight = weights.get(name, 0.0)
            is_nan = isinstance(z_val, float) and math.isnan(z_val)

            if is_nan:
                contribution_str = "N/A"
                z_str = "NaN"
            else:
                contribution = weight * abs(z_val)
                contribution_str = f"{contribution:.3f}"
                z_str = f"{z_val:+.2f}"

            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.text(feature_label(name))
            with col2:
                st.text(f"Z = {z_str}")
            with col3:
                st.text(f"w = {weight:.2f}")
            with col4:
                st.text(f"C = {contribution_str}")
    else:
        st.caption("No z-scores available.")

    st.markdown("---")

    # --- Baseline Status ---
    st.markdown("### Baseline Status")
    st.text(f"State: {diag.baseline_state}")

    st.markdown("---")

    # --- Explainability Text ---
    st.markdown("### Diagnostic Explanation")
    st.markdown(diag.explanation or "_No explanation available._")

    # --- Focus Decomposition (CORE tickers only) ---
    if ticker in CORE_TICKERS:
        st.markdown("---")
        st.markdown("### Focus Decomposition")

        focus_entries = get_focus_entries()
        summary = get_focus_summary()

        if focus_entries:
            st.markdown(
                f"**{summary['total']}** focus tickers "
                f"({summary['structural_count']} structural, "
                f"{summary['stress_count']} stress, "
                f"{summary['event_count']} event)"
            )

            # Partition entries: this ETF's structural first, then other structural, then rest
            etf_structural = []
            other_structural = []
            non_structural = []

            for entry in focus_entries:
                if entry["reason"] == "structural":
                    if f"in {ticker}" in entry["details"]:
                        etf_structural.append(entry)
                    else:
                        other_structural.append(entry)
                else:
                    non_structural.append(entry)

            # Render header
            col_ticker, col_reason, col_details, col_inactive = st.columns([2, 2, 4, 2])
            with col_ticker:
                st.markdown("**Ticker**")
            with col_reason:
                st.markdown("**Reason**")
            with col_details:
                st.markdown("**Details**")
            with col_inactive:
                st.markdown("**Inactive**")

            # This ETF's structural tickers — bold
            if etf_structural:
                for entry in etf_structural:
                    col_ticker, col_reason, col_details, col_inactive = st.columns([2, 2, 4, 2])
                    with col_ticker:
                        st.markdown(f"**{entry['ticker']}**")
                    with col_reason:
                        st.markdown(f"**{entry['reason']}**")
                    with col_details:
                        st.markdown(f"**{entry['details']}**")
                    with col_inactive:
                        st.markdown(f"**{entry['days_inactive']}d**")

            # Other structural tickers — dimmed
            if other_structural:
                for entry in other_structural:
                    col_ticker, col_reason, col_details, col_inactive = st.columns([2, 2, 4, 2])
                    with col_ticker:
                        st.markdown(f"<span style='color:#999'>{entry['ticker']}</span>", unsafe_allow_html=True)
                    with col_reason:
                        st.markdown(f"<span style='color:#999'>{entry['reason']}</span>", unsafe_allow_html=True)
                    with col_details:
                        st.markdown(f"<span style='color:#999'>{entry['details']}</span>", unsafe_allow_html=True)
                    with col_inactive:
                        st.markdown(f"<span style='color:#999'>{entry['days_inactive']}d</span>", unsafe_allow_html=True)

            # Stress + event tickers — normal
            for entry in non_structural:
                col_ticker, col_reason, col_details, col_inactive = st.columns([2, 2, 4, 2])
                with col_ticker:
                    st.text(entry["ticker"])
                with col_reason:
                    st.text(entry["reason"])
                with col_details:
                    st.text(entry["details"])
                with col_inactive:
                    st.text(f"{entry['days_inactive']}d")

            st.caption(
                "Focus tickers are **lenses**, not targets. "
                "They explain CORE behavior, not predict individual moves."
            )
        else:
            st.caption("No focus tickers active. Run full diagnostics to populate.")

    # --- Data Quality Notice ---
    st.markdown("---")
    st.caption(
        "**Note**: This is a **diagnostic**, not a prediction. "
        "OBSIDIAN MM classifies microstructure state but makes no claims about future price direction."
    )
