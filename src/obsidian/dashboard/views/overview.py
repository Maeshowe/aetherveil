"""Overview page - All tickers at a glance."""

import math

import streamlit as st
from datetime import date

import plotly.graph_objects as go

from obsidian.dashboard.data import (
    get_available_tickers,
    get_cached_diagnostic,
    get_focus_entries,
    get_feature_weights,
    feature_label,
    regime_badge_html,
    REGIME_COLORS,
)
from obsidian.universe.manager import CORE_TICKERS


def _abs_z(diag, feature: str) -> float:
    """Get absolute z-score for a feature, defaulting to 0.0 on NaN/missing."""
    z = (diag.z_scores or {}).get(feature)
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return 0.0
    return abs(z)


def _raw_val(diag, feature: str) -> float:
    """Get raw feature value, defaulting to 0.0 on NaN/missing."""
    v = (getattr(diag, "raw_features", None) or {}).get(feature)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    return float(v)


def _score_color(pct: float | None) -> str:
    """Return hex color for a U percentile value."""
    if pct is None:
        return "#999"
    if pct >= 80:
        return "#f44336"
    if pct >= 60:
        return "#FF9800"
    if pct >= 30:
        return "#FFC107"
    return "#4CAF50"


def _top_driver(diag) -> str:
    """Return the label of the feature with highest |Z|."""
    if not diag or not diag.z_scores:
        return "—"
    best_feat = None
    best_abs = -1.0
    for feat, z in diag.z_scores.items():
        if isinstance(z, float) and math.isnan(z):
            continue
        if abs(z) > best_abs:
            best_abs = abs(z)
            best_feat = feat
    return feature_label(best_feat) if best_feat else "—"


def _sort_key(item: tuple[str, object]) -> tuple[float, str]:
    """Sort by U percentile descending. None goes to bottom."""
    _, diag = item
    if diag is None or diag.score_percentile is None:
        return (-1.0, item[0])
    return (diag.score_percentile, item[0])


def _render_ticker_table(tickers: list[str], diags: dict, header: str) -> None:
    """Render a group of tickers as a styled table."""
    if not tickers:
        return

    st.markdown(f"### {header}")

    # Header row
    hdr = st.columns([2, 2, 2, 3, 2])
    for col, label in zip(hdr, ["**Ticker**", "**Regime**", "**U percentile**", "**Top Driver**", "**Baseline**"]):
        with col:
            st.markdown(label)

    # Sort: U percentile descending, None at bottom
    items = [(t, diags.get(t)) for t in tickers]
    items.sort(key=_sort_key, reverse=True)

    for ticker, diag in items:
        cols = st.columns([2, 2, 2, 3, 2])

        if diag is None:
            # No data row — dimmed
            dim = "color:#999"
            with cols[0]:
                st.markdown(f"<span style='{dim}'>{ticker}</span>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown("<span style='color:#999'>—</span>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown("<span style='color:#999'>—</span>", unsafe_allow_html=True)
            with cols[3]:
                st.markdown("<span style='color:#999'>No data — run diagnostics</span>", unsafe_allow_html=True)
            with cols[4]:
                st.markdown("<span style='color:#999'>—</span>", unsafe_allow_html=True)
            continue

        badge = regime_badge_html(diag.regime_label)
        pct = diag.score_percentile
        color = _score_color(pct)
        pct_str = f"{pct:.1f}" if pct is not None else "N/A"
        driver = _top_driver(diag)
        baseline = diag.baseline_state or "—"

        with cols[0]:
            st.markdown(f"**{ticker}**")
        with cols[1]:
            st.markdown(badge, unsafe_allow_html=True)
        with cols[2]:
            st.markdown(
                f"<span style='color:{color}; font-weight:600;'>{pct_str}</span>",
                unsafe_allow_html=True,
            )
        with cols[3]:
            st.text(driver)
        with cols[4]:
            st.text(baseline)


def render(end_date: date) -> None:
    """Render the Overview page — all tickers at a glance.

    Args:
        end_date: Date for diagnostic lookup.
    """
    st.markdown("## Overview — All Tickers")
    st.markdown(f"**{end_date.strftime('%Y-%m-%d')}**")

    with st.expander("How to read this page"):
        st.markdown("""
**Overview** shows every active ticker's current diagnostic state in one view.

- **Regime** — colored badge showing today's classified regime
- **U percentile** — how unusual today's microstructure is (0 = normal, 100 = extreme)
  - Green (<30): normal | Yellow (30-60): elevated | Orange (60-80): high | Red (>80): extreme
- **Top Driver** — the feature with the largest |Z-score| today
- **Baseline** — data sufficiency: COMPLETE (all features valid), PARTIAL (some valid), EMPTY (none)

Tickers are sorted by U percentile descending — the "hottest" ticker is always at the top.
Tickers without cached data appear dimmed at the bottom.
        """)

    # Gather all diagnostics
    all_tickers = get_available_tickers()
    diags = {}
    for t in all_tickers:
        diags[t] = get_cached_diagnostic(t, end_date)

    has_any = any(d is not None for d in diags.values())

    if not has_any:
        st.info(
            "No diagnostic data loaded for any ticker. "
            "Use **Fetch + Run**, **Run (cached)**, or **Full Pipeline** in the sidebar."
        )

    # --- Stress Alerts ---
    _THRESHOLDS = {
        "U >= 70": lambda d: d.score_percentile is not None and d.score_percentile >= 70,
        "|Z_GEX| >= 2.0": lambda d: _abs_z(d, "gex") >= 2.0,
        "DarkShare >= 0.65": lambda d: _raw_val(d, "dark_share") >= 0.65,
        "|Z_block| >= 2.0": lambda d: _abs_z(d, "block_intensity") >= 2.0,
    }

    loaded = {t: d for t, d in diags.items() if d is not None}
    alerts: list[dict] = []
    for t, d in loaded.items():
        triggered = [name for name, check in _THRESHOLDS.items() if check(d)]
        if triggered:
            alerts.append({"ticker": t, "diag": d, "triggers": triggered})

    if alerts:
        alerts.sort(key=lambda a: -(a["diag"].score_percentile or 0))
        st.markdown("### Stress Alerts")
        for alert in alerts:
            d = alert["diag"]
            badge = regime_badge_html(d.regime_label)
            pct = d.score_percentile
            pct_str = f"{pct:.1f}" if pct is not None else "N/A"
            triggers_str = " | ".join(alert["triggers"])
            st.markdown(
                f"{badge} **{alert['ticker']}** — U = {pct_str} — {triggers_str}",
                unsafe_allow_html=True,
            )
        st.markdown("---")

    # --- CORE Tickers ---
    core = [t for t in all_tickers if t in CORE_TICKERS]
    _render_ticker_table(core, diags, "CORE Tickers")

    # --- FOCUS Tickers grouped by ETF structural ---
    focus_entries = get_focus_entries()

    # Group structural by ETF
    etf_structural: dict[str, list[str]] = {}
    stress_event: list[str] = []

    for entry in focus_entries:
        ticker = entry["ticker"]
        if ticker in CORE_TICKERS:
            continue  # Already shown in CORE section
        if entry["reason"] == "structural":
            # Extract ETF from details like "Top 10 holding in SPY (5.2%)"
            for etf in CORE_TICKERS:
                if f"in {etf}" in entry["details"]:
                    etf_structural.setdefault(etf, [])
                    if ticker not in etf_structural[etf]:
                        etf_structural[etf].append(ticker)
                    break
        else:
            if ticker not in stress_event:
                stress_event.append(ticker)

    # Render each ETF's structural group
    for etf in sorted(etf_structural.keys()):
        tickers = etf_structural[etf]
        _render_ticker_table(tickers, diags, f"FOCUS — {etf} Structural")

    # Render stress + event group
    if stress_event:
        _render_ticker_table(stress_event, diags, "FOCUS — Stress & Event")

    # --- Comparison Visualizations ---
    if len(loaded) >= 2:
        st.markdown("---")
        st.markdown("### Comparison")

        viz1, viz2 = st.columns(2)

        # --- U Score Scatter (colored by regime) ---
        with viz1:
            st.markdown("#### U Score Scatter")
            scatter_tickers = []
            scatter_scores = []
            scatter_colors = []
            scatter_regimes = []
            scatter_drivers = []

            for t, d in sorted(loaded.items()):
                if d.score_percentile is None:
                    continue
                short = (d.regime_label or "").split(" — ")[0].split(" ")[0].strip()
                scatter_tickers.append(t)
                scatter_scores.append(d.score_percentile)
                scatter_colors.append(REGIME_COLORS.get(short, "#999"))
                scatter_regimes.append(short)
                scatter_drivers.append(_top_driver(d))

            if scatter_tickers:
                fig = go.Figure()
                # Group by regime for legend
                seen_regimes: dict[str, bool] = {}
                for i, t in enumerate(scatter_tickers):
                    regime = scatter_regimes[i]
                    show_legend = regime not in seen_regimes
                    seen_regimes[regime] = True
                    fig.add_trace(go.Scatter(
                        x=[scatter_scores[i]],
                        y=[t],
                        mode="markers",
                        marker=dict(size=14, color=scatter_colors[i]),
                        name=regime,
                        showlegend=show_legend,
                        legendgroup=regime,
                        hovertemplate=(
                            f"<b>{t}</b><br>"
                            f"U = {scatter_scores[i]:.1f}<br>"
                            f"Regime: {regime}<br>"
                            f"Driver: {scatter_drivers[i]}"
                            "<extra></extra>"
                        ),
                    ))
                fig.add_vline(x=70, line_dash="dash", line_color="#f44336", opacity=0.5)
                fig.update_layout(
                    xaxis_title="U Percentile",
                    xaxis=dict(range=[0, 105]),
                    yaxis=dict(autorange="reversed"),
                    height=max(250, len(scatter_tickers) * 25 + 80),
                    margin=dict(l=10, r=10, t=10, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig, width="stretch")

        # --- Regime Distribution Pie ---
        with viz2:
            st.markdown("#### Regime Distribution")
            regime_counts: dict[str, int] = {}
            for d in loaded.values():
                short = (d.regime_label or "UND").split(" — ")[0].split(" ")[0].strip()
                regime_counts[short] = regime_counts.get(short, 0) + 1

            labels = list(regime_counts.keys())
            values = list(regime_counts.values())
            colors = [REGIME_COLORS.get(r, "#999") for r in labels]

            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+value",
                hovertemplate="%{label}: %{value} ticker(s) (%{percent})<extra></extra>",
                hole=0.4,
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

    # --- Data Quality Notice ---
    st.markdown("---")
    st.caption(
        "**Note**: This is a **diagnostic overview**, not a watchlist. "
        "OBSIDIAN MM classifies microstructure state but makes no claims about future price direction."
    )
