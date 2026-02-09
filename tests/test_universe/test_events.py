"""Tests for events module (earnings + macro + FOMC)."""

from datetime import date

import httpx
import pytest

from obsidian.clients.fmp import FMPClient
from obsidian.clients.fred import FREDClient
from obsidian.universe.events import (
    FOMC_DATES_2025,
    FOMC_DATES_2026,
    FRED_CPI_RELEASE_ID,
    FRED_NFP_RELEASE_ID,
    EventEntry,
    _is_within_window,
    fetch_all_events,
    fetch_earnings_events,
    fetch_macro_events,
    get_fomc_events,
)

FMP_BASE = "https://financialmodelingprep.com/stable"
FRED_BASE = "https://api.stlouisfed.org/fred"


class TestIsWithinWindow:
    """Tests for _is_within_window helper."""

    def test_same_day(self):
        assert _is_within_window(date(2024, 1, 15), date(2024, 1, 15), 1)

    def test_one_day_before(self):
        assert _is_within_window(date(2024, 1, 15), date(2024, 1, 14), 1)

    def test_one_day_after(self):
        assert _is_within_window(date(2024, 1, 15), date(2024, 1, 16), 1)

    def test_two_days_away_fails(self):
        assert not _is_within_window(date(2024, 1, 15), date(2024, 1, 17), 1)

    def test_window_zero(self):
        assert _is_within_window(date(2024, 1, 15), date(2024, 1, 15), 0)
        assert not _is_within_window(date(2024, 1, 15), date(2024, 1, 14), 0)


class TestFetchEarningsEvents:
    """Tests for fetch_earnings_events."""

    @pytest.mark.asyncio
    async def test_earnings_found(self, respx_mock):
        """Should return EventEntry for tickers with earnings."""
        mock_calendar = [
            {"symbol": "AAPL", "date": "2024-01-25", "epsActual": 2.18},
            {"symbol": "MSFT", "date": "2024-01-23", "epsActual": 2.93},
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 24))

        assert len(result) == 2
        assert all(e.event_type == "earnings" for e in result)
        assert result[0].ticker == "AAPL"
        assert result[1].ticker == "MSFT"

    @pytest.mark.asyncio
    async def test_earnings_empty(self, respx_mock):
        """Should return empty list when no earnings."""
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 7, 4))

        assert result == []

    @pytest.mark.asyncio
    async def test_earnings_api_failure(self, respx_mock):
        """Should return empty on API error."""
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 15))

        assert result == []

    @pytest.mark.asyncio
    async def test_earnings_skips_missing_symbol(self, respx_mock):
        """Should skip entries without symbol."""
        mock_calendar = [
            {"symbol": "", "date": "2024-01-25"},
            {"symbol": "AAPL", "date": "2024-01-25"},
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_earnings_uppercases_ticker(self, respx_mock):
        """Ticker should be uppercased."""
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=[
                {"symbol": "aapl", "date": "2024-01-25"},
            ])
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert result[0].ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_filters_international_dot_suffix(self, respx_mock):
        """International tickers with exchange suffix (.BO, .NS, .KS, etc.) filtered."""
        mock_calendar = [
            {"symbol": "SBIN.NS", "date": "2024-01-25"},
            {"symbol": "000050.KS", "date": "2024-01-25"},
            {"symbol": "0941.HK", "date": "2024-01-25"},
            {"symbol": "CAR.AX", "date": "2024-01-25"},
            {"symbol": "AAPL", "date": "2024-01-25"},  # This should pass
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert len(result) == 1
        assert result[0].ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_filters_numeric_prefix_tickers(self, respx_mock):
        """Tickers starting with digits (Asian markets) filtered."""
        mock_calendar = [
            {"symbol": "3100", "date": "2024-01-25"},
            {"symbol": "9434", "date": "2024-01-25"},
            {"symbol": "MSFT", "date": "2024-01-25"},
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert len(result) == 1
        assert result[0].ticker == "MSFT"

    @pytest.mark.asyncio
    async def test_filters_otc_foreign_ordinaries(self, respx_mock):
        """5-char tickers ending in F (OTC foreign ordinaries) filtered."""
        mock_calendar = [
            {"symbol": "ABCFF", "date": "2024-01-25"},
            {"symbol": "AKEMF", "date": "2024-01-25"},
            {"symbol": "AMKR", "date": "2024-01-25"},  # 4-char, should pass
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert len(result) == 1
        assert result[0].ticker == "AMKR"

    @pytest.mark.asyncio
    async def test_filters_otc_adr_tickers(self, respx_mock):
        """5-char tickers ending in Y (OTC ADRs) filtered."""
        mock_calendar = [
            {"symbol": "AKRYY", "date": "2024-01-25"},
            {"symbol": "BCNAY", "date": "2024-01-25"},
            {"symbol": "AVGO", "date": "2024-01-25"},  # 4-char, should pass
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        assert len(result) == 1
        assert result[0].ticker == "AVGO"

    @pytest.mark.asyncio
    async def test_preserves_us_preferred_shares(self, respx_mock):
        """US preferred shares with dashes (BRK-B, CMS-PB) are kept."""
        mock_calendar = [
            {"symbol": "BRK-B", "date": "2024-01-25"},
            {"symbol": "CMS-PB", "date": "2024-01-25"},
            {"symbol": "ACGLN", "date": "2024-01-25"},  # 5-char preferred, not F/Y
        ]
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=mock_calendar)
        )

        async with FMPClient(api_key="test") as fmp:
            result = await fetch_earnings_events(fmp, date(2024, 1, 25))

        tickers = [e.ticker for e in result]
        assert "BRK-B" in tickers
        assert "CMS-PB" in tickers
        assert "ACGLN" in tickers
        assert len(result) == 3


class TestFetchMacroEvents:
    """Tests for fetch_macro_events."""

    @pytest.mark.asyncio
    async def test_cpi_within_window(self, respx_mock):
        """Should detect CPI release within ±1 day."""
        respx_mock.get(f"{FRED_BASE}/release/dates").mock(
            side_effect=[
                # CPI response
                httpx.Response(200, json={"release_dates": [
                    {"release_id": 10, "date": "2024-01-11"},
                ]}),
                # NFP response
                httpx.Response(200, json={"release_dates": []}),
            ]
        )

        async with FREDClient(api_key="test") as fred:
            result = await fetch_macro_events(fred, date(2024, 1, 11))

        assert len(result) == 1
        assert result[0].event_type == "macro"
        assert "CPI" in result[0].description

    @pytest.mark.asyncio
    async def test_nfp_within_window(self, respx_mock):
        """Should detect NFP release within ±1 day."""
        respx_mock.get(f"{FRED_BASE}/release/dates").mock(
            side_effect=[
                # CPI response
                httpx.Response(200, json={"release_dates": []}),
                # NFP response
                httpx.Response(200, json={"release_dates": [
                    {"release_id": 50, "date": "2024-02-02"},
                ]}),
            ]
        )

        async with FREDClient(api_key="test") as fred:
            result = await fetch_macro_events(fred, date(2024, 2, 2))

        assert len(result) == 1
        assert "NFP" in result[0].description

    @pytest.mark.asyncio
    async def test_no_macro_events(self, respx_mock):
        """Should return empty when no macro events near date."""
        respx_mock.get(f"{FRED_BASE}/release/dates").mock(
            return_value=httpx.Response(200, json={"release_dates": [
                {"release_id": 10, "date": "2024-06-15"},
            ]})
        )

        async with FREDClient(api_key="test") as fred:
            result = await fetch_macro_events(fred, date(2024, 1, 15))

        assert result == []

    @pytest.mark.asyncio
    async def test_fred_none_graceful(self):
        """Should return empty when FRED client is None."""
        result = await fetch_macro_events(None, date(2024, 1, 15))
        assert result == []

    @pytest.mark.asyncio
    async def test_macro_ticker_is_none(self, respx_mock):
        """Macro events should have ticker=None."""
        respx_mock.get(f"{FRED_BASE}/release/dates").mock(
            side_effect=[
                httpx.Response(200, json={"release_dates": [
                    {"release_id": 10, "date": "2024-01-11"},
                ]}),
                httpx.Response(200, json={"release_dates": []}),
            ]
        )

        async with FREDClient(api_key="test") as fred:
            result = await fetch_macro_events(fred, date(2024, 1, 11))

        assert result[0].ticker is None


class TestGetFOMCEvents:
    """Tests for get_fomc_events (pure function)."""

    def test_fomc_on_exact_date(self):
        """Should detect FOMC on the meeting date."""
        result = get_fomc_events(date(2025, 1, 29))
        assert len(result) == 1
        assert result[0].event_type == "macro"
        assert "FOMC" in result[0].description

    def test_fomc_one_day_before(self):
        """Should detect FOMC one day before meeting."""
        result = get_fomc_events(date(2025, 1, 28))
        assert len(result) == 1

    def test_fomc_one_day_after(self):
        """Should detect FOMC one day after meeting."""
        result = get_fomc_events(date(2025, 1, 30))
        assert len(result) == 1

    def test_fomc_two_days_away(self):
        """Should NOT detect FOMC two days away."""
        result = get_fomc_events(date(2025, 1, 31))
        assert result == []

    def test_fomc_2025_count(self):
        """Should have 8 FOMC dates for 2025."""
        assert len(FOMC_DATES_2025) == 8

    def test_fomc_2026_count(self):
        """Should have 8 FOMC dates for 2026."""
        assert len(FOMC_DATES_2026) == 8

    def test_fomc_ticker_is_none(self):
        """FOMC events should have ticker=None."""
        result = get_fomc_events(date(2025, 3, 19))
        assert result[0].ticker is None


class TestFetchAllEvents:
    """Tests for fetch_all_events."""

    @pytest.mark.asyncio
    async def test_combines_all_sources(self, respx_mock):
        """Should combine earnings + macro + FOMC."""
        # Earnings
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=[
                {"symbol": "AAPL", "date": "2025-01-29"},
            ])
        )

        # FRED
        respx_mock.get(f"{FRED_BASE}/release/dates").mock(
            return_value=httpx.Response(200, json={"release_dates": []})
        )

        # FOMC on 2025-01-29
        async with FMPClient(api_key="t") as fmp, FREDClient(api_key="t") as fred:
            result = await fetch_all_events(fmp, fred, date(2025, 1, 29))

        # Should have: 1 earnings (AAPL) + 0 macro + 1 FOMC
        earnings = [e for e in result if e.event_type == "earnings"]
        macro = [e for e in result if e.event_type == "macro"]
        assert len(earnings) == 1
        assert len(macro) == 1  # FOMC

    @pytest.mark.asyncio
    async def test_no_fred_still_works(self, respx_mock):
        """Should work with fred=None (FOMC + earnings only)."""
        respx_mock.get(f"{FMP_BASE}/earnings-calendar").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with FMPClient(api_key="t") as fmp:
            result = await fetch_all_events(fmp, None, date(2025, 3, 19))

        # Should have FOMC event
        assert any("FOMC" in e.description for e in result)
