"""Baseline Status page - Data sufficiency and quality indicators."""

import math

import streamlit as st
from datetime import date
import pandas as pd

from obsidian.dashboard.data import (
    get_cached_diagnostic,
    get_feature_weights,
    feature_label,
)


# Minimum observations for valid baseline (from spec)
_MIN_OBS = 21
_WINDOW = 63


def _feature_state(z_val: float | None) -> str:
    """Classify a feature's baseline state from its z-score value.

    If z-score is a valid number the baseline had enough data.
    If NaN the feature was excluded (PARTIAL or EMPTY).
    """
    if z_val is None:
        return "EMPTY"
    if isinstance(z_val, float) and math.isnan(z_val):
        return "EMPTY"
    return "COMPLETE"


def render(ticker: str, end_date: date) -> None:
    """Render the Baseline Status page.

    Args:
        ticker: Instrument ticker symbol
        end_date: Date for analysis
    """
    st.markdown("## Baseline Status")
    st.markdown(f"**{ticker}** -- {end_date.strftime('%Y-%m-%d')}")

    st.markdown(f"""
    Data quality and sufficiency for the rolling {_WINDOW}-day baseline window.

    **Baseline States**:
    - COMPLETE: valid z-score computed (>={_MIN_OBS} observations)
    - EMPTY: insufficient data or feature unavailable (z-score = NaN)
    """)

    diag = get_cached_diagnostic(ticker, end_date)

    if diag is None:
        st.info("No diagnostic data loaded. Use **Fetch + Run** or **Run (cached)** in the sidebar.")
        return

    st.markdown("---")

    # --- Overall baseline state from DiagnosticResult ---
    st.markdown("### Overall Baseline State")
    st.text(f"Engine state: {diag.baseline_state}")

    st.markdown("---")

    # --- Per-feature status ---
    st.markdown("### Per-Feature Status")
    st.caption(f"Rolling {_WINDOW}-day window ending {end_date.strftime('%Y-%m-%d')}")

    weights = get_feature_weights()

    # Gather all features (weighted + unweighted)
    all_feature_names = set((diag.z_scores or {}).keys()) | set(weights.keys())
    features = []
    for name in sorted(all_feature_names):
        z_val = diag.z_scores.get(name)
        state = _feature_state(z_val)
        weight = weights.get(name, 0.0)
        features.append({
            "name": name,
            "label": feature_label(name),
            "state": state,
            "z_score": z_val,
            "weight": weight,
            "is_weighted": weight > 0,
        })

    for f in features:
        state_emoji = {"COMPLETE": "G", "EMPTY": "R"}.get(f["state"], "?")
        state_color = {"COMPLETE": "green", "EMPTY": "red"}.get(f["state"], "gray")

        col1, col2, col3 = st.columns([3, 2, 5])
        with col1:
            st.markdown(f"**{f['label']}**")
        with col2:
            st.text(f"State: {f['state']}")
        with col3:
            if f["state"] == "COMPLETE":
                z_val = f["z_score"]
                z_str = f"{z_val:+.2f}" if z_val is not None and not (isinstance(z_val, float) and math.isnan(z_val)) else "N/A"
                st.success(f"Baseline usable -- Z = {z_str}, w = {f['weight']:.2f}")
            else:
                if f["is_weighted"]:
                    st.error(f"Excluded from scoring (weight = {f['weight']:.2f})")
                else:
                    st.warning("Informational feature -- no data")

    st.markdown("---")

    # --- Summary ---
    st.markdown("### Window Summary")

    complete_count = sum(1 for f in features if f["state"] == "COMPLETE" and f["is_weighted"])
    total_weighted = sum(1 for f in features if f["is_weighted"])
    empty_count = sum(1 for f in features if f["state"] == "EMPTY" and f["is_weighted"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Weighted Features Ready", f"{complete_count}/{total_weighted}")
    with col2:
        st.metric("Features Missing", f"{empty_count}")
    with col3:
        st.metric("Baseline State", diag.baseline_state)

    # --- Recommendations ---
    st.markdown("---")
    st.markdown("### Data Quality Recommendations")

    empty_weighted = [f for f in features if f["state"] == "EMPTY" and f["is_weighted"]]
    empty_unweighted = [f for f in features if f["state"] == "EMPTY" and not f["is_weighted"]]

    if not empty_weighted and not empty_unweighted:
        st.success(
            "All features have sufficient baseline data. "
            "The diagnostic engine is operating with the full feature set."
        )
    else:
        if empty_weighted:
            names = ", ".join(f["label"] for f in empty_weighted)
            st.warning(
                f"**{len(empty_weighted)} weighted feature(s) excluded**: {names}\n\n"
                "These features are excluded from unusualness scoring and may affect "
                "regime classification. Check API connectivity and data availability."
            )
        if empty_unweighted:
            names = ", ".join(f["label"] for f in empty_unweighted)
            st.info(
                f"**{len(empty_unweighted)} informational feature(s) unavailable**: {names}\n\n"
                "These do not affect scoring but may limit classification accuracy."
            )

    st.markdown("---")
    st.caption(
        "**Baseline Philosophy**: OBSIDIAN MM never imputes, interpolates, or forward-fills missing data. "
        "Missing observations result in NaN baselines, which exclude features from scoring. "
        "This prevents false confidence from approximate data."
    )
