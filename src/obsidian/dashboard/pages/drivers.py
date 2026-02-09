"""Drivers & Contributors page - Feature breakdown analysis."""

import math

import streamlit as st
from datetime import date
import plotly.graph_objects as go
import pandas as pd

from obsidian.dashboard.data import (
    get_cached_diagnostic,
    get_feature_weights,
    get_focus_diagnostics,
    feature_label,
)
from obsidian.universe.manager import CORE_TICKERS


def render(ticker: str, end_date: date) -> None:
    """Render the Drivers & Contributors page.

    Args:
        ticker: Instrument ticker symbol
        end_date: Date for analysis
    """
    st.markdown("## Drivers & Contributors")
    st.markdown(f"**{ticker}** -- {end_date.strftime('%Y-%m-%d')}")

    diag = get_cached_diagnostic(ticker, end_date)

    if diag is None:
        st.info("No diagnostic data loaded. Use **Fetch + Run** or **Run (cached)** in the sidebar.")
        return

    if not diag.z_scores:
        st.warning("No z-scores available for this diagnostic.")
        return

    weights = get_feature_weights()

    # Build feature list with contributions
    features = []
    for name, z_val in diag.z_scores.items():
        is_nan = isinstance(z_val, float) and math.isnan(z_val)
        weight = weights.get(name, 0.0)
        contribution = weight * abs(z_val) if (not is_nan and weight > 0) else 0.0
        features.append({
            "name": name,
            "label": feature_label(name),
            "z_score": z_val if not is_nan else 0.0,
            "weight": weight,
            "contribution": contribution,
            "is_nan": is_nan,
        })

    # Sort by contribution descending
    features.sort(key=lambda f: f["contribution"], reverse=True)

    # Separate valid and NaN features
    valid_features = [f for f in features if not f["is_nan"] and f["weight"] > 0]
    nan_features = [f for f in features if f["is_nan"]]
    unweighted_features = [f for f in features if not f["is_nan"] and f["weight"] == 0]

    total_score = sum(f["contribution"] for f in valid_features)

    # --- Feature Contribution Breakdown ---
    st.markdown("### Feature Contributions to Unusualness Score")

    if valid_features:
        fig_contrib = go.Figure()
        fig_contrib.add_trace(go.Bar(
            x=[f["contribution"] for f in valid_features],
            y=[f["label"] for f in valid_features],
            orientation='h',
            marker=dict(
                color=[f["z_score"] for f in valid_features],
                colorscale='RdBu',
                cmin=-3,
                cmax=3,
                colorbar=dict(title="Z-Score"),
            ),
            text=[f"{f['contribution']:.3f}" for f in valid_features],
            textposition='auto',
            hovertemplate='%{y}<br>Contribution: %{x:.3f}<br>Z-score: %{marker.color:.2f}<extra></extra>',
        ))
        fig_contrib.update_layout(
            xaxis_title="Contribution to Unusualness",
            yaxis_title="Feature",
            height=300,
            showlegend=False,
        )
        st.plotly_chart(fig_contrib, width="stretch")

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Score", f"{total_score:.3f}" if diag.score_raw is not None else "N/A")
    with col2:
        if valid_features:
            st.metric("Top Driver", valid_features[0]["label"])
        else:
            st.metric("Top Driver", "N/A")
    with col3:
        total_possible = len(weights)
        st.metric("Features Used", f"{len(valid_features)}/{total_possible}")

    st.markdown("---")

    # --- Waterfall Chart ---
    st.markdown("### Score Composition (Waterfall)")

    if valid_features:
        fig_waterfall = go.Figure(go.Waterfall(
            name="Contribution",
            orientation="v",
            measure=["relative"] * len(valid_features) + ["total"],
            x=[f["label"] for f in valid_features] + ["Total"],
            y=[f["contribution"] for f in valid_features] + [total_score],
            text=[f"+{f['contribution']:.3f}" for f in valid_features] + [f"{total_score:.3f}"],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        fig_waterfall.update_layout(
            title="Cumulative Contribution Breakdown",
            showlegend=False,
            height=400,
        )
        st.plotly_chart(fig_waterfall, width="stretch")

    st.markdown("---")

    # --- Feature Details Table ---
    st.markdown("### Feature Details")

    rows = []
    for f in features:
        if f["is_nan"]:
            z_str = "NaN (excluded)"
        else:
            z_str = f"{f['z_score']:+.2f}"

        rows.append({
            "Feature": f["label"],
            "Z-Score": z_str,
            "Weight": f"{f['weight']:.2f}" if f["weight"] > 0 else "-- (unweighted)",
            "Contribution": f"{f['contribution']:.3f}" if not f["is_nan"] else "N/A",
        })

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # --- Excluded / unweighted features ---
    if nan_features:
        st.markdown("---")
        st.markdown("### Excluded Features (NaN)")
        for f in nan_features:
            st.text(f"  {f['label']}: insufficient baseline data")

    if unweighted_features:
        st.markdown("---")
        st.markdown("### Informational Features (unweighted)")
        st.caption("These features are computed but do not contribute to the unusualness score.")
        for f in unweighted_features:
            st.text(f"  {f['label']}: Z = {f['z_score']:+.2f}")

    # --- FOCUS Z-Score Cross-Reference (CORE tickers only) ---
    if ticker in CORE_TICKERS:
        focus_diags = get_focus_diagnostics(end_date, etf=ticker)
        focus_with_z = [fd for fd in focus_diags if fd["z_scores"]]

        if focus_with_z:
            st.markdown("---")
            st.markdown("### FOCUS Z-Score Cross-Reference")
            st.caption(
                f"Comparing {ticker}'s z-scores with its structural/event FOCUS tickers."
            )

            # Weighted features only (the 5 scoring features)
            scored_features = sorted(weights.keys())

            # Build comparison table: rows = features, columns = tickers
            header_cols = st.columns([3] + [2] * min(len(focus_with_z) + 1, 8))
            with header_cols[0]:
                st.markdown("**Feature**")
            # Show the CORE ticker first
            col_idx = 1
            with header_cols[col_idx]:
                st.markdown(f"**{ticker}**")
            col_idx += 1

            # Then FOCUS tickers (limit to 6 to avoid cramming)
            display_focus = focus_with_z[:6]
            for fd in display_focus:
                if col_idx < len(header_cols):
                    with header_cols[col_idx]:
                        st.markdown(f"**{fd['ticker']}**")
                    col_idx += 1

            # Rows for each scored feature
            for feat in scored_features:
                row_cols = st.columns([3] + [2] * min(len(focus_with_z) + 1, 8))
                with row_cols[0]:
                    st.text(feature_label(feat))

                # CORE ticker value
                col_idx = 1
                core_z = diag.z_scores.get(feat)
                if core_z is not None and not (isinstance(core_z, float) and math.isnan(core_z)):
                    with row_cols[col_idx]:
                        st.text(f"{core_z:+.2f}")
                else:
                    with row_cols[col_idx]:
                        st.text("NaN")
                col_idx += 1

                # FOCUS ticker values
                for fd in display_focus:
                    if col_idx < len(row_cols):
                        z = fd["z_scores"].get(feat) if fd["z_scores"] else None
                        if z is not None and not (isinstance(z, float) and math.isnan(z)):
                            with row_cols[col_idx]:
                                st.text(f"{z:+.2f}")
                        else:
                            with row_cols[col_idx]:
                                st.text("NaN")
                        col_idx += 1

            if len(focus_with_z) > 6:
                st.caption(f"Showing 6 of {len(focus_with_z)} FOCUS tickers with z-scores.")

    st.markdown("---")
    st.caption(
        "**Reminder**: Feature contributions are based on **fixed weights** (not optimized). "
        "They reflect conceptual importance in market microstructure diagnostics."
    )
