"""Command-line interface for OBSIDIAN MM.

Provides commands for running market microstructure diagnostics from the terminal.

Usage:
    obsidian diagnose SPY
    obsidian diagnose SPY --date 2024-01-15
    obsidian diagnose SPY --format json
"""

import argparse
import asyncio
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type
from pathlib import Path
from typing import Optional

from obsidian.pipeline.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser.

    Returns:
        Configured ArgumentParser with all commands and arguments.
    """
    parser = argparse.ArgumentParser(
        prog="obsidian",
        description="OBSIDIAN MM — Market-Maker Regime Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  obsidian diagnose SPY
  obsidian diagnose SPY --date 2024-01-15
  obsidian diagnose SPY --format json

For detailed documentation, see: reference/OBSIDIAN_MM_SPEC.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # diagnose command
    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Run full diagnostic for an instrument",
        description="Analyze market microstructure and classify regime",
    )
    diagnose_parser.add_argument(
        "ticker",
        type=str,
        help="Ticker symbol (e.g., SPY, AAPL, QQQ)",
    )
    diagnose_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date in YYYY-MM-DD format (default: latest available)",
    )
    diagnose_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    diagnose_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data"),
        help="Directory for Parquet cache (default: ./data)",
    )
    diagnose_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache and fetch fresh data from APIs",
    )

    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
    )

    return parser


def _run_async(coro):
    """Run an async coroutine from synchronous CLI context.

    Spins up a new event loop in a dedicated thread to avoid conflicts
    with any existing event loop.
    """
    def _target():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    future = _executor.submit(_target)
    return future.result()


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Execute the diagnose command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Parse date
        if args.date:
            target_date = date_type.fromisoformat(args.date)
        else:
            target_date = date_type.today()

        fetch_data = not args.no_cache
        cache_dir = str(args.cache_dir)

        logger.info(
            "Running diagnostic for %s on %s (cache_dir=%s, fetch=%s)",
            args.ticker, target_date.isoformat(), cache_dir, fetch_data,
        )

        orchestrator = Orchestrator(cache_dir=cache_dir)
        result = _run_async(
            orchestrator.run_single_ticker(
                ticker=args.ticker,
                target_date=target_date,
                fetch_data=fetch_data,
            )
        )

        # Output in requested format
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.explanation)

        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error("Diagnostic failed: %s", e, exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_version(args: argparse.Namespace) -> int:
    """Execute the version command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    print("OBSIDIAN MM v0.2.0")
    print("Market-Maker Regime Engine")
    print("https://github.com/Maeshowe/aetherveil")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = create_parser()
    args = parser.parse_args(argv)

    # Route to command handler
    if args.command == "diagnose":
        return cmd_diagnose(args)
    elif args.command == "version":
        return cmd_version(args)
    else:
        # No command specified
        parser.print_help()
        return 0


def cli_entry() -> None:
    """Console script entry point for setuptools."""
    sys.exit(main())


if __name__ == "__main__":
    cli_entry()
