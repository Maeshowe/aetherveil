"""Main Streamlit application for OBSIDIAN MM Dashboard.

Run with:
    streamlit run src/obsidian/dashboard/app.py
"""

import streamlit as st
from datetime import date, timedelta

from obsidian.dashboard.data import (
    get_available_tickers,
    fetch_and_diagnose,
    diagnose_from_cache,
    run_full_pipeline,
    get_cached_diagnostic,
)

# Page configuration
st.set_page_config(
    page_title="OBSIDIAN MM",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .regime-badge {
        display: inline-block;
        padding: 0.5rem 1.5rem;
        border-radius: 1rem;
        font-weight: 700;
        font-size: 1.2rem;
        letter-spacing: 0.05em;
    }
    .regime-gamma-pos { background-color: #4CAF50; color: white; }
    .regime-gamma-neg { background-color: #f44336; color: white; }
    .regime-dark-dom { background-color: #9C27B0; color: white; }
    .regime-absorption { background-color: #2196F3; color: white; }
    .regime-distribution { background-color: #FF9800; color: white; }
    .regime-neutral { background-color: #9E9E9E; color: white; }
    .regime-undetermined { background-color: #607D8B; color: white; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">OBSIDIAN MM</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Market-Maker Regime Engine</div>',
    unsafe_allow_html=True
)

# Sidebar
with st.sidebar:
    st.markdown("### Configuration")

    # Ticker selection from Universe
    available = get_available_tickers()
    ticker = st.selectbox(
        "Ticker",
        available,
        index=0,
        help="CORE tickers always shown. FOCUS tickers appear when promoted.",
    )

    # Date range
    st.markdown("### Date Range")
    end_date = st.date_input(
        "End Date",
        value=date.today(),
        max_value=date.today(),
        help="Latest date for analysis"
    )

    start_date = st.date_input(
        "Start Date",
        value=end_date - timedelta(days=90),
        max_value=end_date,
        help="Earliest date for analysis"
    )

    if start_date > end_date:
        st.error("Start date must be before end date")

    # --- Fetch / Process controls ---
    st.markdown("### Data")

    col_fetch, col_process = st.columns(2)
    with col_fetch:
        do_fetch = st.button("Fetch + Run", use_container_width=True,
                             help="Fetch fresh data from APIs, then run diagnostics")
    with col_process:
        do_process = st.button("Run (cached)", use_container_width=True,
                               help="Run diagnostics on already-cached data")

    if do_fetch:
        with st.spinner(f"Fetching {ticker} for {end_date}..."):
            result = fetch_and_diagnose(ticker, end_date)
        if result:
            st.success(f"{ticker}: {result.regime_label}")
        else:
            st.error("Fetch failed. Check logs.")

    if do_process:
        with st.spinner(f"Processing {ticker} for {end_date}..."):
            result = diagnose_from_cache(ticker, end_date)
        if result:
            st.success(f"{ticker}: {result.regime_label}")
        else:
            st.error("Processing failed. Is data cached?")

    do_full = st.button(
        "Full Pipeline (CORE + FOCUS)",
        use_container_width=True,
        help="Run two-pass pipeline: structural/event focus + fetch + diagnose all tickers",
    )

    if do_full:
        with st.spinner(f"Running full pipeline for {end_date}..."):
            results = run_full_pipeline(end_date, fetch_data=True)
        if results:
            st.success(f"Done: {len(results)} tickers diagnosed")
        else:
            st.error("Full pipeline failed. Check logs.")

    # Status indicator
    diag = get_cached_diagnostic(ticker, end_date)
    if diag:
        st.markdown(f"**Last result**: {diag.regime_label}")
    else:
        st.caption("No diagnostic loaded. Press a button above.")

    # Page selection
    st.markdown("### Navigation")
    page = st.radio(
        "Select Page",
        [
            "Daily State",
            "Historical Regimes",
            "Drivers & Contributors",
            "Baseline Status",
        ],
        label_visibility="collapsed"
    )

    # Info
    st.markdown("---")
    st.markdown("### About")
    st.caption("""
    **OBSIDIAN MM** analyzes market microstructure to classify
    institutional and dealer behavior into explainable regimes.

    **Version**: 0.2.0
    """)

# Store selections in session state
st.session_state['ticker'] = ticker
st.session_state['start_date'] = start_date
st.session_state['end_date'] = end_date

# Route to selected page
if page == "Daily State":
    from obsidian.dashboard.pages import daily_state
    daily_state.render(ticker, end_date)

elif page == "Historical Regimes":
    from obsidian.dashboard.pages import historical_regimes
    historical_regimes.render(ticker, start_date, end_date)

elif page == "Drivers & Contributors":
    from obsidian.dashboard.pages import drivers
    drivers.render(ticker, end_date)

elif page == "Baseline Status":
    from obsidian.dashboard.pages import baseline_status
    baseline_status.render(ticker, end_date)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>OBSIDIAN MM &mdash; Diagnostic tool only. Not for trading signals or price predictions.</p>
</div>
""", unsafe_allow_html=True)
