"""Events Module — Earnings and macro event detection.

Detects calendar events that trigger FOCUS tier promotion:
- Earnings announcements (FMP earnings calendar)
- Macro releases: CPI, NFP (FRED release dates)
- FOMC meetings (hardcoded annual dates)

All events use a ±1 trading day window per spec §2.3.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from obsidian.clients.fmp import FMPClient
from obsidian.clients.fred import FREDClient

logger = logging.getLogger(__name__)

# FRED release IDs
FRED_CPI_RELEASE_ID = 10
FRED_NFP_RELEASE_ID = 50

# FOMC meeting dates — manually maintained (updated annually)
FOMC_DATES_2025 = [
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 10, 29),
    date(2025, 12, 10),
]

FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 16),
]

# Combined for lookup
_ALL_FOMC_DATES = frozenset(FOMC_DATES_2025 + FOMC_DATES_2026)


@dataclass(frozen=True)
class EventEntry:
    """A single calendar event that may trigger FOCUS promotion."""

    event_type: Literal["earnings", "macro"]
    event_date: date
    ticker: str | None    # None for macro events (CPI, NFP, FOMC)
    description: str


def _is_within_window(
    target_date: date,
    event_date: date,
    window_days: int = 1,
) -> bool:
    """Check if event_date is within ±window_days of target_date."""
    delta = abs((event_date - target_date).days)
    return delta <= window_days


async def fetch_earnings_events(
    fmp: FMPClient,
    target_date: date,
    window: int = 1,
) -> list[EventEntry]:
    """Fetch earnings events near target_date.

    Queries FMP earnings calendar for [target_date - window, target_date + window].

    Args:
        fmp: Active FMP client
        target_date: Center date for the window
        window: Days on each side (default: 1 = ±1 day)

    Returns:
        List of EventEntry for each ticker reporting earnings in the window.
    """
    date_from = target_date - timedelta(days=window)
    date_to = target_date + timedelta(days=window)

    try:
        calendar = await fmp.get_earnings_calendar(
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        logger.warning("Failed to fetch earnings calendar: %s", e)
        return []

    events: list[EventEntry] = []
    skipped = 0
    for entry in calendar:
        symbol = entry.get("symbol", "")
        event_date_str = entry.get("date", "")
        if not symbol or not event_date_str:
            continue

        # Filter to US-listed tickers only.
        # FMP earnings calendar returns global tickers. We skip:
        #   1. International exchange suffixes: .BO, .NS, .KS, .AX, .HK, etc.
        #   2. Numeric Asian tickers: 0941, 3100, etc.
        #   3. OTC foreign ordinaries: 5-char ending in F (ABCFF, AKEMF)
        #   4. OTC ADRs / unsponsored: 5-char ending in Y (AKRYY, BCNAY)
        if "." in symbol or symbol[0].isdigit():
            skipped += 1
            continue
        if len(symbol) == 5 and symbol[-1] in ("F", "Y"):
            skipped += 1
            continue

        try:
            event_date = date.fromisoformat(event_date_str)
        except ValueError:
            continue

        events.append(EventEntry(
            event_type="earnings",
            event_date=event_date,
            ticker=symbol.upper(),
            description=f"Earnings on {event_date_str}",
        ))

    logger.info(
        "Earnings events in [%s, %s]: %d US tickers (%d non-US/OTC filtered)",
        date_from, date_to, len(events), skipped,
    )
    return events


async def fetch_macro_events(
    fred: FREDClient | None,
    target_date: date,
    window: int = 1,
) -> list[EventEntry]:
    """Fetch macro release events (CPI, NFP) near target_date.

    If fred is None, returns empty (graceful degradation).

    Args:
        fred: Active FRED client (or None to skip)
        target_date: Center date
        window: Days on each side (default: 1)

    Returns:
        List of EventEntry for macro releases within ±window.
    """
    if fred is None:
        logger.debug("FRED client not available — skipping macro events")
        return []

    events: list[EventEntry] = []

    for release_id, label in [
        (FRED_CPI_RELEASE_ID, "CPI"),
        (FRED_NFP_RELEASE_ID, "NFP"),
    ]:
        try:
            dates = await fred.get_release_dates(release_id=release_id, limit=20)
        except Exception as e:
            logger.warning("Failed to fetch %s release dates: %s", label, e)
            continue

        for entry in dates:
            date_str = entry.get("date", "")
            if not date_str:
                continue

            try:
                release_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            if _is_within_window(target_date, release_date, window):
                events.append(EventEntry(
                    event_type="macro",
                    event_date=release_date,
                    ticker=None,
                    description=f"{label} release on {date_str}",
                ))

    logger.info("Macro events near %s: %d", target_date, len(events))
    return events


def get_fomc_events(
    target_date: date,
    window: int = 1,
) -> list[EventEntry]:
    """Get FOMC meeting events near target_date.

    Pure function — uses hardcoded FOMC dates (no API call).

    Args:
        target_date: Center date
        window: Days on each side (default: 1)

    Returns:
        List of EventEntry for FOMC meetings within ±window.
    """
    events: list[EventEntry] = []

    for fomc_date in _ALL_FOMC_DATES:
        if _is_within_window(target_date, fomc_date, window):
            events.append(EventEntry(
                event_type="macro",
                event_date=fomc_date,
                ticker=None,
                description=f"FOMC meeting on {fomc_date.isoformat()}",
            ))

    return events


async def fetch_all_events(
    fmp: FMPClient,
    fred: FREDClient | None,
    target_date: date,
    window: int = 1,
) -> list[EventEntry]:
    """Fetch all event types: earnings + macro (CPI/NFP) + FOMC.

    Args:
        fmp: Active FMP client
        fred: Active FRED client (or None)
        target_date: Center date
        window: Days on each side (default: 1)

    Returns:
        Combined list of all events in the window.
    """
    earnings = await fetch_earnings_events(fmp, target_date, window)
    macro = await fetch_macro_events(fred, target_date, window)
    fomc = get_fomc_events(target_date, window)

    all_events = earnings + macro + fomc
    logger.info(
        "Total events near %s: %d (earnings=%d, macro=%d, fomc=%d)",
        target_date, len(all_events), len(earnings), len(macro), len(fomc),
    )
    return all_events
