"""Data Health page — cache statistics, collection status, gap detection."""

import streamlit as st
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from obsidian.dashboard.data import get_cache_health_report
from obsidian.universe.manager import CORE_TICKERS


def render() -> None:
    """Render the Data Health page."""
    st.markdown("## Data Health")

    with st.expander("About this page"):
        st.markdown("""
**Data Health** shows the state of the parquet cache — what data has been
collected, how complete it is, and where gaps exist. This is the dashboard
equivalent of `scripts/check_status.py`.

- **Collection Summary**: total tickers, files, storage size
- **Baseline Readiness**: how many tickers have enough data for full scoring
- **Per-Ticker Detail**: source counts, date ranges, missing sources
- **Gap Detection**: missing trading days in the collection window
        """)

    with st.spinner("Scanning cache..."):
        report = get_cache_health_report()

    summary = report.get("summary", {})
    tickers = report.get("tickers", {})

    if not tickers:
        st.warning("No cached data found. Run the pipeline to start collecting.")
        return

    # --- Collection Summary ---
    st.markdown("### Collection Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Tickers", summary.get("total_tickers", 0))
    with c2:
        st.metric(
            "CORE / FOCUS",
            f"{summary.get('core_tickers', 0)} / {summary.get('focus_tickers', 0)}",
        )
    with c3:
        st.metric("Parquet Files", f"{summary.get('total_files', 0):,}")
    with c4:
        st.metric("Cache Size", summary.get("total_size", "0 B"))

    st.markdown("---")

    # --- Baseline Readiness ---
    st.markdown("### Baseline Readiness")
    st.caption("Based on dark pool observation count (need 21+ days for valid baseline)")

    complete = summary.get("baseline_complete", 0)
    partial = summary.get("baseline_partial", 0)
    empty = summary.get("baseline_empty", 0)
    total = summary.get("total_tickers", 1)

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.metric("COMPLETE", complete)
    with rc2:
        st.metric("PARTIAL", partial)
    with rc3:
        st.metric("EMPTY", empty)

    # Stacked bar for readiness
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[complete], y=["Baseline"], orientation="h", name="COMPLETE",
        marker_color="#4CAF50", text=[str(complete)], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        x=[partial], y=["Baseline"], orientation="h", name="PARTIAL",
        marker_color="#FF9800", text=[str(partial)], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        x=[empty], y=["Baseline"], orientation="h", name="EMPTY",
        marker_color="#f44336", text=[str(empty)], textposition="inside",
    ))
    fig.update_layout(
        barmode="stack", height=100,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # --- CORE Ticker Detail ---
    st.markdown("### CORE Ticker Detail")
    core_data = {t: v for t, v in tickers.items() if v["is_core"]}

    if core_data:
        rows = []
        for ticker in sorted(core_data.keys()):
            info = core_data[ticker]
            src = info["sources"]
            rows.append({
                "Ticker": ticker,
                "Bars": src.get("bars", 0),
                "Dark Pool": src.get("dark_pool", 0),
                "Greeks": src.get("greeks", 0),
                "IV Rank": src.get("iv_rank", 0),
                "Quote": src.get("quote", 0),
                "Baseline": info["baseline_state"],
                "From": info["first_date"].isoformat() if info["first_date"] else "—",
                "To": info["last_date"].isoformat() if info["last_date"] else "—",
                "Gaps": len(info["gaps"]),
            })

        df = pd.DataFrame(rows)

        # Style: highlight low counts
        def _style_count(val):
            if isinstance(val, int):
                if val == 0:
                    return "color: #f44336; font-weight: bold"
                if val < 21:
                    return "color: #FF9800"
            return ""

        styled = df.style.map(_style_count, subset=["Bars", "Dark Pool", "Greeks", "IV Rank", "Quote", "Gaps"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Gap details per CORE ticker
        for ticker in sorted(core_data.keys()):
            info = core_data[ticker]
            if info["gaps"]:
                with st.expander(f"{ticker} — {len(info['gaps'])} missing trading day(s)"):
                    gap_strs = [g.isoformat() for g in info["gaps"]]
                    st.text(", ".join(gap_strs))
    else:
        st.info("No CORE tickers found in cache.")

    st.markdown("---")

    # --- FOCUS Ticker Overview ---
    st.markdown("### FOCUS Ticker Overview")
    focus_data = {t: v for t, v in tickers.items() if not v["is_core"]}

    if focus_data:
        st.caption(f"{len(focus_data)} FOCUS tickers in cache")

        rows = []
        for ticker in sorted(focus_data.keys()):
            info = focus_data[ticker]
            src = info["sources"]
            missing = ", ".join(info["missing_sources"]) if info["missing_sources"] else "—"
            rows.append({
                "Ticker": ticker,
                "Bars": src.get("bars", 0),
                "DP": src.get("dark_pool", 0),
                "Greeks": src.get("greeks", 0),
                "IV": src.get("iv_rank", 0),
                "Baseline": info["baseline_state"],
                "Missing Sources": missing,
                "Gaps": len(info["gaps"]),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("No FOCUS tickers in cache yet.")

    st.markdown("---")

    # --- Source coverage heatmap ---
    st.markdown("### Source Coverage Heatmap")
    st.caption("CORE tickers — days per source")

    if core_data:
        heatmap_tickers = sorted(core_data.keys())
        sources = ["bars", "dark_pool", "greeks", "iv_rank", "quote"]
        z_data = []
        for src in sources:
            row = [core_data[t]["sources"].get(src, 0) for t in heatmap_tickers]
            z_data.append(row)

        fig = go.Figure(go.Heatmap(
            z=z_data,
            x=heatmap_tickers,
            y=[s.replace("_", " ").title() for s in sources],
            colorscale=[[0, "#f44336"], [0.5, "#FF9800"], [1, "#4CAF50"]],
            text=z_data,
            texttemplate="%{text}",
            hovertemplate="Ticker: %{x}<br>Source: %{y}<br>Days: %{z}<extra></extra>",
        ))
        fig.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")
