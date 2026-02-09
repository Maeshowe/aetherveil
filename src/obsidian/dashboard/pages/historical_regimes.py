"""Historical Regimes page - Regime timeline and transitions."""

import streamlit as st
from datetime import date
import plotly.graph_objects as go
import pandas as pd

from obsidian.dashboard.data import get_historical_diagnostics, get_focus_diagnostics
from obsidian.engine.classifier import RegimeType
from obsidian.universe.manager import CORE_TICKERS


# Display order and colours for regimes
_REGIME_ORDER = [
    RegimeType.GAMMA_POSITIVE,
    RegimeType.GAMMA_NEGATIVE,
    RegimeType.DARK_DOMINANT,
    RegimeType.ABSORPTION,
    RegimeType.DISTRIBUTION,
    RegimeType.NEUTRAL,
    RegimeType.UNDETERMINED,
]

_REGIME_COLORS = {
    RegimeType.GAMMA_POSITIVE: "#4CAF50",
    RegimeType.GAMMA_NEGATIVE: "#f44336",
    RegimeType.DARK_DOMINANT: "#9C27B0",
    RegimeType.ABSORPTION: "#2196F3",
    RegimeType.DISTRIBUTION: "#FF9800",
    RegimeType.NEUTRAL: "#9E9E9E",
    RegimeType.UNDETERMINED: "#607D8B",
}

_REGIME_LABELS = {r: r.value for r in _REGIME_ORDER}


def render(ticker: str, start_date: date, end_date: date) -> None:
    """Render the Historical Regimes page.

    Args:
        ticker: Instrument ticker symbol
        start_date: Start of analysis window
        end_date: End of analysis window
    """
    st.markdown("## Historical Regimes")
    st.markdown(f"**{ticker}** -- {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    history = get_historical_diagnostics(ticker, start_date, end_date)

    if not history:
        st.info(
            "No historical diagnostics cached for this range. "
            "Run diagnostics for multiple dates to populate the timeline."
        )
        return

    # Build dataframe from cached results
    rows = []
    for d, diag in sorted(history.items()):
        rows.append({
            "date": d,
            "regime": diag.regime,
            "regime_label": _REGIME_LABELS.get(diag.regime, diag.regime.value),
            "score_raw": diag.score_raw,
            "score_pct": diag.score_percentile,
        })

    df = pd.DataFrame(rows)
    regime_to_num = {r: i for i, r in enumerate(_REGIME_ORDER)}
    df["regime_num"] = df["regime"].map(regime_to_num)

    # --- Regime Timeline Chart ---
    st.markdown("### Regime Timeline")

    fig = go.Figure()
    for regime in _REGIME_ORDER:
        regime_df = df[df["regime"] == regime]
        if regime_df.empty:
            continue
        label = _REGIME_LABELS[regime]
        fig.add_trace(go.Scatter(
            x=regime_df["date"],
            y=regime_df["regime_num"],
            mode='markers',
            marker=dict(size=10, color=_REGIME_COLORS[regime], symbol='square'),
            name=label,
            hovertemplate=f"{label}<br>%{{x}}<extra></extra>",
        ))

    fig.update_layout(
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(_REGIME_ORDER))),
            ticktext=[_REGIME_LABELS[r] for r in _REGIME_ORDER],
            title="Regime",
        ),
        xaxis=dict(title="Date"),
        hovermode='closest',
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # --- Regime Distribution ---
    st.markdown("### Regime Distribution")

    regime_counts = df["regime_label"].value_counts()
    all_labels = [_REGIME_LABELS[r] for r in _REGIME_ORDER]
    regime_counts = regime_counts.reindex(all_labels, fill_value=0)

    fig_dist = go.Figure(data=[go.Bar(
        x=regime_counts.index,
        y=regime_counts.values,
        marker=dict(color=[_REGIME_COLORS[r] for r in _REGIME_ORDER]),
    )])
    fig_dist.update_layout(
        xaxis_title="Regime", yaxis_title="Days", height=300, showlegend=False,
    )
    st.plotly_chart(fig_dist, width="stretch")

    total_days = len(df)
    cols = st.columns(len(_REGIME_ORDER))
    for i, regime in enumerate(_REGIME_ORDER):
        label = _REGIME_LABELS[regime]
        count = regime_counts.get(label, 0)
        pct = (count / total_days * 100) if total_days > 0 else 0
        with cols[i]:
            st.metric(label, f"{pct:.0f}%", f"{count} days")

    st.markdown("---")

    # --- Transition Analysis ---
    st.markdown("### Regime Transitions")

    transitions = []
    sorted_dates = sorted(history.keys())
    for i in range(len(sorted_dates) - 1):
        d_from = sorted_dates[i]
        d_to = sorted_dates[i + 1]
        r_from = history[d_from].regime
        r_to = history[d_to].regime
        if r_from != r_to:
            transitions.append({
                "date": d_to,
                "from": _REGIME_LABELS[r_from],
                "to": _REGIME_LABELS[r_to],
                "from_regime": r_from,
                "to_regime": r_to,
            })

    if transitions:
        st.markdown(f"**{len(transitions)} transitions detected**")
        for trans in reversed(transitions[-10:]):
            from_color = _REGIME_COLORS[trans["from_regime"]]
            to_color = _REGIME_COLORS[trans["to_regime"]]
            st.markdown(
                f'<div style="padding: 0.5rem; margin: 0.25rem 0; background-color: #f0f2f6; border-radius: 0.3rem;">'
                f'<span style="color: {from_color}; font-weight: 600;">{trans["from"]}</span>'
                f' -> '
                f'<span style="color: {to_color}; font-weight: 600;">{trans["to"]}</span>'
                f'<span style="float: right; color: #666;">{trans["date"].strftime("%Y-%m-%d")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        if len(sorted_dates) < 2:
            st.info("Need at least 2 dates of diagnostics to detect transitions.")
        else:
            st.info("No regime transitions in selected period.")

    st.markdown("---")

    # --- Transition Matrix ---
    if transitions:
        st.markdown("### Transition Matrix")
        st.caption("Rows = from, Columns = to")

        all_labels_list = [_REGIME_LABELS[r] for r in _REGIME_ORDER]
        transition_matrix = pd.DataFrame(0, index=all_labels_list, columns=all_labels_list)
        for trans in transitions:
            transition_matrix.loc[trans["from"], trans["to"]] += 1

        transition_probs = transition_matrix.div(
            transition_matrix.sum(axis=1).replace(0, 1), axis=0
        )

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=transition_probs.values,
            x=transition_probs.columns,
            y=transition_probs.index,
            colorscale='Blues',
            text=transition_matrix.values,
            texttemplate='%{text}',
            textfont={"size": 10},
            hovertemplate='From %{y} to %{x}<br>Count: %{text}<br>Prob: %{z:.0%}<extra></extra>',
        ))
        fig_heatmap.update_layout(
            xaxis_title="To Regime", yaxis_title="From Regime", height=400,
        )
        st.plotly_chart(fig_heatmap, width="stretch")

    # --- FOCUS Regime Snapshot (CORE tickers only) ---
    if ticker in CORE_TICKERS:
        focus_diags = get_focus_diagnostics(end_date, etf=ticker)
        if focus_diags:
            st.markdown("---")
            st.markdown("### FOCUS Regime Snapshot")
            st.caption(
                f"Current regimes for {ticker}'s structural FOCUS tickers "
                f"(plus stress/event entries)."
            )

            # Build compact regime grid
            col_t, col_r, col_regime, col_score = st.columns([2, 2, 3, 2])
            with col_t:
                st.markdown("**Ticker**")
            with col_r:
                st.markdown("**Reason**")
            with col_regime:
                st.markdown("**Regime**")
            with col_score:
                st.markdown("**U percentile**")

            for fd in focus_diags:
                col_t, col_r, col_regime, col_score = st.columns([2, 2, 3, 2])

                regime = fd["regime"]
                color = _REGIME_COLORS.get(regime, "#666") if regime else "#666"
                regime_text = fd["regime_label"] or "—"
                score_text = f"{fd['score_percentile']:.1f}" if fd["score_percentile"] is not None else "—"

                with col_t:
                    if fd["reason"] == "structural":
                        st.markdown(f"**{fd['ticker']}**")
                    else:
                        st.text(fd["ticker"])
                with col_r:
                    st.text(fd["reason"])
                with col_regime:
                    st.markdown(
                        f"<span style='color:{color}; font-weight:600'>{regime_text}</span>",
                        unsafe_allow_html=True,
                    )
                with col_score:
                    st.text(score_text)

    st.caption(
        "**Note**: Historical data is populated as you run diagnostics for different dates. "
        "Only dates with cached results appear in this timeline."
    )
