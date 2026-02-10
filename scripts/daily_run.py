#!/usr/bin/env python3
"""OBSIDIAN MM — Daily Data Collection Runner.

Runs the full two-pass diagnostic pipeline for all CORE + FOCUS tickers.
Designed to be called from cron daily after US market close.

Usage:
    python scripts/daily_run.py
    python scripts/daily_run.py --date 2026-02-07
    python scripts/daily_run.py --no-focus   # skip focus update (CORE only)

Scheduling (CET — US market closes 22:00 CET winter / 22:30 CET summer):
    crontab -e
    30 23 * * 1-5 /path/to/aetherveil/.venv/bin/python /path/to/aetherveil/scripts/daily_run.py >> /path/to/aetherveil/logs/daily.log 2>&1
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path so 'obsidian' is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env before importing obsidian (pydantic-settings needs env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed — env vars must be set externally

from obsidian.pipeline.orchestrator import Orchestrator


def setup_logging(log_dir: Path, target_date: date) -> None:
    """Configure logging to both console and daily log file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"daily_{target_date.isoformat()}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


async def run_pipeline(target_date: date, update_focus: bool, cache_dir: str) -> dict:
    """Run the full two-pass diagnostic pipeline.

    Args:
        target_date: Date to diagnose.
        update_focus: Whether to run Pass 1 + Pass 2 (focus updates).
        cache_dir: Directory for Parquet cache.

    Returns:
        Dictionary mapping ticker -> diagnostic dict.
    """
    orchestrator = Orchestrator(cache_dir=cache_dir)

    results = await orchestrator.run_diagnostics(
        target_date=target_date,
        fetch_data=True,
        update_focus=update_focus,
    )

    return results


def print_summary(results: dict, target_date: date) -> None:
    """Print a human-readable summary of results."""
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("OBSIDIAN MM Daily Run — %s", target_date.isoformat())
    logger.info("=" * 60)
    logger.info("Tickers processed: %d", len(results))

    for ticker in sorted(results.keys()):
        diag = results[ticker]
        score = diag.score_percentile
        score_str = f"U={score:.1f}" if diag.score_raw is not None else "U=N/A"
        regime = diag.regime_label

        # Count available features
        z = diag.z_scores
        available = sum(1 for v in z.values() if v is not None)
        total = len(z) if z else 0

        logger.info(
            "  %-6s  %-6s  %s  features=%d/%d",
            ticker, regime, score_str, available, total,
        )

    logger.info("=" * 60)
    logger.info("Done. Next valid baseline in %d+ more daily runs.",
                max(0, 21 - 1))  # rough estimate


def save_results(results: dict, target_date: date, output_dir: Path) -> None:
    """Save results as JSON for inspection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"results_{target_date.isoformat()}.json"

    serialized = {}
    for ticker, diag in results.items():
        serialized[ticker] = diag.to_dict()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, default=str)

    logging.getLogger(__name__).info("Results saved to %s", output_file)


def main() -> int:
    """Main entry point for daily runner."""
    parser = argparse.ArgumentParser(
        description="OBSIDIAN MM — Daily data collection pipeline",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--no-focus",
        action="store_true",
        help="Skip focus update (CORE tickers only)",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=str(PROJECT_ROOT / "data"),
        help="Parquet cache directory (default: data/)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "output"),
        help="JSON results directory (default: output/)",
    )
    args = parser.parse_args()

    # Parse date first (needed for log file name)
    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = date.today()

    # Setup logging (uses target_date for log file name)
    log_dir = PROJECT_ROOT / "logs"
    setup_logging(log_dir, target_date)
    logger = logging.getLogger(__name__)

    update_focus = not args.no_focus

    logger.info("Starting OBSIDIAN MM daily run")
    logger.info("  Date: %s", target_date.isoformat())
    logger.info("  Focus update: %s", update_focus)
    logger.info("  Cache dir: %s", args.cache_dir)

    try:
        # Run pipeline
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                run_pipeline(target_date, update_focus, args.cache_dir)
            )
        finally:
            loop.close()

        # Output
        print_summary(results, target_date)
        save_results(results, target_date, Path(args.output_dir))

        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error("Daily run failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
