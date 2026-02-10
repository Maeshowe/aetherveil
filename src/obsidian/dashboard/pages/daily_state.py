"""Daily State page - Current regime and unusualness score."""

import math

import streamlit as st
from datetime import date
import plotly.graph_objects as go

from obsidian.dashboard.data import (
    get_cached_diagnostic,
    get_feature_weights,
    get_focus_entries,
    get_focus_diagnostics,
    get_focus_summary,
    feature_label,
    regime_badge_html,
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


def _render_explanation(explanation: str) -> None:
    """Render formatted diagnostic explanation with sections and highlights."""
    if not explanation:
        st.caption("_No explanation available._")
        return

    lines = explanation.strip().split("\n")

    # Parse into sections (split on blank lines, skip header)
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("==="):
            continue
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    for section in sections:
        first = section[0]

        if first.startswith("Regime:"):
            # Regime section — bold header + triggering conditions as bullets
            st.markdown(f"**{first}**")
            for line in section[1:]:
                st.markdown(f"- `{line.strip()}`")

        elif first.startswith("Unusualness:"):
            # Score section — header + drivers as bullet list
            st.markdown(f"**{first}**")
            for line in section[1:]:
                if line.startswith("Top drivers:"):
                    drivers = line.replace("Top drivers: ", "").split("; ")
                    for d in drivers:
                        parts = d.split(" contrib=")
                        if len(parts) == 2:
                            name, val = parts
                            st.markdown(
                                f"- **{name}** — contribution: `{val}`"
                            )
                        else:
                            st.markdown(f"- {d}")
                else:
                    st.markdown(f"  {line}")

        elif first.startswith("Excluded:"):
            excluded_text = first.replace("Excluded: ", "")
            if excluded_text == "none":
                st.success("**Excluded features:** none — full feature set active")
            else:
                items = excluded_text.split(", ")
                st.warning(
                    "**Excluded features:** "
                    + " | ".join(f"`{item}`" for item in items)
                )

        elif first.startswith("Baseline:"):
            state = first.replace("Baseline: ", "")
            if state == "COMPLETE":
                st.success(f"**Baseline:** {state} — all features have sufficient history")
            elif state == "PARTIAL":
                st.info(f"**Baseline:** {state} — some features lack sufficient history")
            else:
                st.warning(f"**Baseline:** {state} — insufficient data for baseline computation")


def render(ticker: str, end_date: date) -> None:
    """Render the Daily State page.

    Args:
        ticker: Instrument ticker symbol
        end_date: Date for diagnostic
    """
    st.markdown("## Daily State")
    st.markdown(f"**{ticker}** -- {end_date.strftime('%Y-%m-%d')}")

    with st.expander("How to read this page"):
        st.markdown("""
**Daily State** shows today's microstructure diagnosis for a single ticker.

- **Regime** — what behavioral pattern the market-makers exhibit today
  - **Γ⁺** (green): Dealers long gamma — volatility suppression, tight range
  - **Γ⁻** (red): Dealers short gamma — liquidity vacuum, amplified moves
  - **DD** (purple): Dark-dominant — institutional positioning via dark pools
  - **ABS** (blue): Absorption — passive buying absorbs sell pressure
  - **DIST** (orange): Distribution — supply distributed into strength
  - **NEU** (gray): No dominant pattern
  - **UND**: Insufficient data to classify
- **Unusualness Score (U)** — how unusual today's microstructure is compared to the last 63 trading days (0 = normal, 100 = extreme)
- **Z-Scores** — how many standard deviations each feature is from its recent baseline
- **FOCUS** — structural tickers that explain *why* this ETF behaves this way (e.g., NVDA stress may explain QQQ regime)

This is a **diagnostic**, not a prediction. It tells you *what is happening*, not *what will happen*.
        """)

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

    # --- Explainability Text (structured) ---
    st.markdown("### Diagnostic Explanation")
    _render_explanation(diag.explanation)

    # --- AI Analysis (optional enrichment) ---
    if diag.ai_explanation:
        st.markdown("---")
        st.markdown("### AI Analysis")
        st.markdown(diag.ai_explanation)

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

            # Build regime lookup from focus diagnostics
            focus_diags = get_focus_diagnostics(end_date)
            regime_lookup = {
                fd["ticker"]: fd["regime_label"]
                for fd in focus_diags
            }

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
            hdr = st.columns([2, 2, 2, 3, 1])
            for col, label in zip(hdr, ["**Ticker**", "**Regime**", "**Reason**", "**Details**", "**Idle**"]):
                with col:
                    st.markdown(label)

            def _render_focus_row(entry: dict, style: str = "normal") -> None:
                """Render a single focus row with regime badge."""
                cols = st.columns([2, 2, 2, 3, 1])
                badge = regime_badge_html(regime_lookup.get(entry["ticker"]))

                if style == "bold":
                    with cols[0]:
                        st.markdown(f"**{entry['ticker']}**")
                    with cols[1]:
                        st.markdown(badge, unsafe_allow_html=True)
                    with cols[2]:
                        st.markdown(f"**{entry['reason']}**")
                    with cols[3]:
                        st.markdown(f"**{entry['details']}**")
                    with cols[4]:
                        st.markdown(f"**{entry['days_inactive']}d**")
                elif style == "dimmed":
                    dim = "color:#999"
                    with cols[0]:
                        st.markdown(f"<span style='{dim}'>{entry['ticker']}</span>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(badge, unsafe_allow_html=True)
                    with cols[2]:
                        st.markdown(f"<span style='{dim}'>{entry['reason']}</span>", unsafe_allow_html=True)
                    with cols[3]:
                        st.markdown(f"<span style='{dim}'>{entry['details']}</span>", unsafe_allow_html=True)
                    with cols[4]:
                        st.markdown(f"<span style='{dim}'>{entry['days_inactive']}d</span>", unsafe_allow_html=True)
                else:
                    with cols[0]:
                        st.text(entry["ticker"])
                    with cols[1]:
                        st.markdown(badge, unsafe_allow_html=True)
                    with cols[2]:
                        st.text(entry["reason"])
                    with cols[3]:
                        st.text(entry["details"])
                    with cols[4]:
                        st.text(f"{entry['days_inactive']}d")

            # This ETF's structural tickers — bold
            for entry in etf_structural:
                _render_focus_row(entry, style="bold")
            # Other structural tickers — dimmed
            for entry in other_structural:
                _render_focus_row(entry, style="dimmed")
            # Stress + event tickers — normal
            for entry in non_structural:
                _render_focus_row(entry, style="normal")

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
