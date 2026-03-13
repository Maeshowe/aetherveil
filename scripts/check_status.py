#!/usr/bin/env python3
"""OBSIDIAN MM — Cache Health & Collection Status Report.

Scans the Parquet cache to produce a comprehensive status report:
  - Per-ticker data counts by source
  - Baseline readiness (EMPTY / PARTIAL / COMPLETE)
  - Missing trading days detection
  - Date range and gap analysis
  - Overall collection summary

Usage:
    python scripts/check_status.py
    python scripts/check_status.py --cache-dir /path/to/data
    python scripts/check_status.py --json          # machine-readable output
    python scripts/check_status.py --ticker SPY    # single ticker detail
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Known data sources written by the pipeline
EXPECTED_SOURCES = ["bars", "dark_pool", "greeks", "iv_rank", "quote"]
CORE_TICKERS = frozenset(["SPY", "QQQ", "IWM", "DIA"])
BASELINE_MIN_OBS = 21
BASELINE_WINDOW = 63


def scan_ticker(raw_dir: Path) -> dict:
    """Scan a ticker's raw/ directory and return per-source date lists.

    Returns:
        Dict mapping source_name -> sorted list of date objects.
    """
    sources: dict[str, list[date]] = {}
    if not raw_dir.exists():
        return sources

    for f in raw_dir.glob("*.parquet"):
        try:
            parts = f.stem.rsplit("_", 1)
            source = parts[0]
            dt = datetime.strptime(parts[1], "%Y-%m-%d").date()
            sources.setdefault(source, []).append(dt)
        except (ValueError, IndexError):
            continue

    # Sort each source's dates
    for src in sources:
        sources[src].sort()

    return sources


def get_trading_days(start: date, end: date) -> list[date]:
    """Generate approximate US trading days (weekdays, no holidays)."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def baseline_state(count: int) -> str:
    """Classify baseline state from observation count."""
    if count == 0:
        return "EMPTY"
    elif count < BASELINE_MIN_OBS:
        return "PARTIAL"
    elif count < BASELINE_WINDOW:
        return "COMPLETE"
    else:
        return "COMPLETE+"


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def analyze_cache(cache_dir: Path) -> dict:
    """Full cache analysis. Returns structured report."""
    tickers: dict[str, dict] = {}
    total_files = 0
    total_size = 0

    # Find all ticker directories
    if not cache_dir.exists():
        return {"error": f"Cache directory not found: {cache_dir}"}

    ticker_dirs = sorted(
        d for d in cache_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    for ticker_dir in ticker_dirs:
        ticker = ticker_dir.name
        raw_dir = ticker_dir / "raw"

        if not raw_dir.exists():
            continue

        sources = scan_ticker(raw_dir)
        if not sources:
            continue

        # File count and size
        parquet_files = list(raw_dir.glob("*.parquet"))
        file_count = len(parquet_files)
        dir_size = sum(f.stat().st_size for f in parquet_files)
        total_files += file_count
        total_size += dir_size

        # All dates across sources
        all_dates = sorted(set(d for dates in sources.values() for d in dates))
        first_date = all_dates[0] if all_dates else None
        last_date = all_dates[-1] if all_dates else None

        # Dark pool count determines baseline readiness
        dp_count = len(sources.get("dark_pool", []))
        bars_count = len(sources.get("bars", []))

        # Detect gaps (missing weekdays in the date range)
        gaps = []
        if first_date and last_date and bars_count > 1:
            expected = get_trading_days(first_date, last_date)
            bars_set = set(sources.get("bars", []))
            gaps = [d for d in expected if d not in bars_set]

        # Determine feature completeness
        is_core = ticker in CORE_TICKERS
        available_sources = set(sources.keys())
        expected_set = set(EXPECTED_SOURCES)
        missing_sources = expected_set - available_sources

        tickers[ticker] = {
            "is_core": is_core,
            "sources": {src: len(dates) for src, dates in sources.items()},
            "first_date": first_date.isoformat() if first_date else None,
            "last_date": last_date.isoformat() if last_date else None,
            "trading_days": bars_count,
            "dark_pool_days": dp_count,
            "baseline_state": baseline_state(dp_count),
            "bars_baseline": baseline_state(bars_count),
            "missing_sources": sorted(missing_sources),
            "gaps": [d.isoformat() for d in gaps],
            "gap_count": len(gaps),
            "file_count": file_count,
            "size_bytes": dir_size,
        }

    # Summary
    core_tickers = {t: v for t, v in tickers.items() if v["is_core"]}
    focus_tickers = {t: v for t, v in tickers.items() if not v["is_core"]}

    complete_count = sum(1 for v in tickers.values() if v["baseline_state"] in ("COMPLETE", "COMPLETE+"))
    partial_count = sum(1 for v in tickers.values() if v["baseline_state"] == "PARTIAL")

    # Log file analysis
    log_dir = cache_dir.parent / "logs"
    log_files = sorted(log_dir.glob("daily_*.log")) if log_dir.exists() else []
    run_dates = []
    for lf in log_files:
        try:
            dt_str = lf.stem.replace("daily_", "")
            run_dates.append(datetime.strptime(dt_str, "%Y-%m-%d").date())
        except ValueError:
            continue
    run_dates.sort()

    return {
        "summary": {
            "total_tickers": len(tickers),
            "core_tickers": len(core_tickers),
            "focus_tickers": len(focus_tickers),
            "baseline_complete": complete_count,
            "baseline_partial": partial_count,
            "baseline_empty": len(tickers) - complete_count - partial_count,
            "total_files": total_files,
            "total_size": format_size(total_size),
            "total_size_bytes": total_size,
        },
        "daily_runs": {
            "total_runs": len(run_dates),
            "first_run": run_dates[0].isoformat() if run_dates else None,
            "last_run": run_dates[-1].isoformat() if run_dates else None,
            "missing_weekdays": len(
                get_trading_days(run_dates[0], run_dates[-1])
            ) - len(run_dates) if len(run_dates) >= 2 else 0,
        },
        "tickers": tickers,
    }


def print_report(report: dict, ticker_filter: str | None = None) -> None:
    """Print human-readable status report."""
    if "error" in report:
        print(f"ERROR: {report['error']}")
        return

    s = report["summary"]
    r = report["daily_runs"]

    print("=" * 70)
    print("  OBSIDIAN MM — Cache Health Report")
    print("=" * 70)
    print()

    # Daily runs
    print("  Daily Collection")
    print(f"    Total runs:        {r['total_runs']}")
    print(f"    First run:         {r['first_run']}")
    print(f"    Last run:          {r['last_run']}")
    if r["missing_weekdays"] > 0:
        print(f"    Missing weekdays:  {r['missing_weekdays']}  (holidays or failures)")
    print()

    # Summary
    print("  Cache Summary")
    print(f"    Tickers:           {s['total_tickers']}  (CORE: {s['core_tickers']}, FOCUS: {s['focus_tickers']})")
    print(f"    Parquet files:     {s['total_files']}")
    print(f"    Total size:        {s['total_size']}")
    print()

    # Baseline status
    print("  Baseline Readiness (dark pool — need 21+ days)")
    complete = s["baseline_complete"]
    partial = s["baseline_partial"]
    empty = s["baseline_empty"]
    total = s["total_tickers"]
    bar_len = 40
    c_bar = int(complete / total * bar_len) if total else 0
    p_bar = int(partial / total * bar_len) if total else 0
    e_bar = bar_len - c_bar - p_bar
    print(f"    [{'█' * c_bar}{'▓' * p_bar}{'░' * e_bar}]")
    print(f"    COMPLETE: {complete}  |  PARTIAL: {partial}  |  EMPTY: {empty}")
    print()

    # Ticker details
    tickers = report["tickers"]
    if ticker_filter:
        ticker_filter = ticker_filter.upper()
        if ticker_filter in tickers:
            tickers = {ticker_filter: tickers[ticker_filter]}
        else:
            print(f"  Ticker {ticker_filter} not found in cache.")
            return

    # CORE tickers first
    core = {t: v for t, v in tickers.items() if v["is_core"]}
    focus = {t: v for t, v in tickers.items() if not v["is_core"]}

    print("  CORE Tickers")
    print("  " + "-" * 68)
    print(f"  {'Ticker':<8} {'Bars':>5} {'DP':>5} {'Greeks':>6} {'IV':>5} {'Quote':>5}  {'Baseline':<10} {'Range'}")
    print("  " + "-" * 68)

    for ticker in sorted(core.keys()):
        info = core[ticker]
        src = info["sources"]
        bs = info["baseline_state"]
        date_range = f"{info['first_date']} → {info['last_date']}" if info["first_date"] else "—"
        gaps = f"  ({info['gap_count']} gaps)" if info["gap_count"] > 0 else ""
        print(
            f"  {ticker:<8} {src.get('bars', 0):>5} {src.get('dark_pool', 0):>5} "
            f"{src.get('greeks', 0):>6} {src.get('iv_rank', 0):>5} {src.get('quote', 0):>5}  "
            f"{bs:<10} {date_range}{gaps}"
        )
    print()

    if focus:
        print("  FOCUS Tickers")
        print("  " + "-" * 68)
        print(f"  {'Ticker':<8} {'Bars':>5} {'DP':>5} {'Greeks':>6} {'IV':>5} {'Quote':>5}  {'Baseline':<10} {'Range'}")
        print("  " + "-" * 68)

        for ticker in sorted(focus.keys()):
            info = focus[ticker]
            src = info["sources"]
            bs = info["baseline_state"]
            date_range = f"{info['first_date']} → {info['last_date']}" if info["first_date"] else "—"
            gaps = f"  ({info['gap_count']} gaps)" if info["gap_count"] > 0 else ""
            missing = ""
            if info["missing_sources"]:
                missing = f"  [no: {', '.join(info['missing_sources'])}]"
            print(
                f"  {ticker:<8} {src.get('bars', 0):>5} {src.get('dark_pool', 0):>5} "
                f"{src.get('greeks', 0):>6} {src.get('iv_rank', 0):>5} {src.get('quote', 0):>5}  "
                f"{bs:<10} {date_range}{gaps}{missing}"
            )
        print()

    # Single ticker detail
    if ticker_filter and ticker_filter in report["tickers"]:
        info = report["tickers"][ticker_filter]
        if info["gaps"]:
            print(f"  Missing dates for {ticker_filter}:")
            for gap in info["gaps"]:
                print(f"    - {gap}")
            print()

    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OBSIDIAN MM — Cache health & collection status",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=str(PROJECT_ROOT / "data"),
        help="Parquet cache directory (default: data/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted report",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Show detail for a single ticker",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    report = analyze_cache(cache_dir)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report, ticker_filter=args.ticker)

    return 0


if __name__ == "__main__":
    sys.exit(main())
