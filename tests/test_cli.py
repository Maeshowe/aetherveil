"""Tests for CLI interface.

Test Coverage:
    - Argument parsing
    - Command routing
    - Help text generation
    - Error handling
    - Diagnose command with mocked pipeline
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obsidian.cli import cmd_diagnose, cmd_version, create_parser, main


class TestParserCreation:
    """Test CLI parser creation."""

    def test_parser_has_commands(self):
        """Parser has diagnose and version commands."""
        parser = create_parser()
        # Parse with --help to see available commands
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_parser_prog_name(self):
        """Parser has correct program name."""
        parser = create_parser()
        assert parser.prog == "obsidian"


class TestDiagnoseCommand:
    """Test diagnose command parsing."""

    def test_diagnose_required_ticker(self):
        """Diagnose command requires ticker argument."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            # Should fail without ticker
            parser.parse_args(["diagnose"])

    def test_diagnose_ticker_parsed(self):
        """Diagnose command parses ticker correctly."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY"])
        assert args.command == "diagnose"
        assert args.ticker == "SPY"
        assert args.date is None  # Default
        assert args.format == "text"  # Default

    def test_diagnose_with_date(self):
        """Diagnose command accepts --date option."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15"])
        assert args.ticker == "SPY"
        assert args.date == "2024-01-15"

    def test_diagnose_with_format_text(self):
        """Diagnose command accepts --format text."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "AAPL", "--format", "text"])
        assert args.ticker == "AAPL"
        assert args.format == "text"

    def test_diagnose_with_format_json(self):
        """Diagnose command accepts --format json."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "QQQ", "--format", "json"])
        assert args.ticker == "QQQ"
        assert args.format == "json"

    def test_diagnose_invalid_format_rejected(self):
        """Diagnose command rejects invalid --format values."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["diagnose", "SPY", "--format", "xml"])

    def test_diagnose_with_cache_dir(self):
        """Diagnose command accepts --cache-dir option."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--cache-dir", "/tmp/cache"])
        assert args.ticker == "SPY"
        assert args.cache_dir == Path("/tmp/cache")

    def test_diagnose_default_cache_dir(self):
        """Diagnose command has default cache directory."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY"])
        assert args.cache_dir == Path("data")

    def test_diagnose_with_no_cache_flag(self):
        """Diagnose command accepts --no-cache flag."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--no-cache"])
        assert args.ticker == "SPY"
        assert args.no_cache is True

    def test_diagnose_no_cache_flag_default_false(self):
        """Diagnose command --no-cache defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY"])
        assert args.no_cache is False


class TestVersionCommand:
    """Test version command."""

    def test_version_command_parsed(self):
        """Version command is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_version_command_execution(self, capsys):
        """Version command executes and prints version."""
        parser = create_parser()
        args = parser.parse_args(["version"])
        exit_code = cmd_version(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "OBSIDIAN MM" in captured.out
        assert "v0.1.0" in captured.out


class TestMainEntryPoint:
    """Test main() entry point."""

    def test_main_no_args_shows_help(self, capsys):
        """Main with no arguments shows help."""
        exit_code = main([])
        assert exit_code == 0
        captured = capsys.readouterr()
        # Should show usage/help
        assert "obsidian" in captured.out.lower() or "usage" in captured.out.lower()

    def test_main_version_command(self, capsys):
        """Main routes version command correctly."""
        exit_code = main(["version"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "OBSIDIAN MM" in captured.out

    def test_main_with_help_flag(self):
        """Main with --help exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


class TestErrorHandling:
    """Test CLI error handling."""

    def test_invalid_command_shows_help(self, capsys):
        """Invalid command shows help message."""
        with pytest.raises(SystemExit):
            main(["invalid-command"])

    def test_diagnose_missing_ticker_exits(self):
        """Diagnose without ticker exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["diagnose"])
        # argparse exits with code 2 for usage errors
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Pipeline integration tests (mocked Orchestrator)
# ---------------------------------------------------------------------------

def _make_mock_result(
    ticker: str = "SPY",
    target_date: date = date(2024, 1, 15),
) -> MagicMock:
    """Create a mock DiagnosticResult for testing."""
    result = MagicMock()
    result.ticker = ticker
    result.date = target_date
    result.regime.value = "NEU"
    result.regime_label = "Neutral / Mixed"
    result.score_raw = 1.5
    result.score_percentile = 42.0
    result.interpretation = "Normal"
    result.z_scores = {"dark_share": 0.5, "gex": -0.3}
    result.baseline_state = "COMPLETE"
    result.explanation = f"OBSIDIAN MM — {ticker} — Neutral / Mixed\nScore: 42.0"
    result.to_dict.return_value = {
        "ticker": ticker,
        "date": target_date.isoformat(),
        "regime": "NEU",
        "regime_label": "Neutral / Mixed",
        "score_raw": 1.5,
        "score_percentile": 42.0,
        "interpretation": "Normal",
        "z_scores": {"dark_share": 0.5, "gex": -0.3},
        "baseline_state": "COMPLETE",
        "explanation": f"OBSIDIAN MM — {ticker} — Neutral / Mixed\nScore: 42.0",
    }
    return result


class TestDiagnoseExecution:
    """Test cmd_diagnose with mocked pipeline."""

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_text_output(self, MockOrch, capsys):
        """Text format prints the explanation."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15"])
        exit_code = cmd_diagnose(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Neutral / Mixed" in captured.out
        assert "SPY" in captured.out
        mock_orch.run_single_ticker.assert_called_once()

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_json_output(self, MockOrch, capsys):
        """JSON format prints valid JSON with expected keys."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15", "--format", "json"])
        exit_code = cmd_diagnose(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ticker"] == "SPY"
        assert data["regime"] == "NEU"
        assert data["score_percentile"] == 42.0

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_default_date_is_today(self, MockOrch):
        """Without --date, uses today's date."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY"])
        cmd_diagnose(args)

        call_kwargs = mock_orch.run_single_ticker.call_args
        # target_date should be today
        assert call_kwargs.kwargs.get("target_date") or call_kwargs[1].get("target_date") or call_kwargs[0][1] == date.today()

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_no_cache_sets_fetch_false(self, MockOrch):
        """--no-cache passes fetch_data=False to orchestrator."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15", "--no-cache"])
        cmd_diagnose(args)

        call_args = mock_orch.run_single_ticker.call_args
        assert call_args.kwargs["fetch_data"] is False

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_default_fetches_data(self, MockOrch):
        """Without --no-cache, fetch_data=True."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15"])
        cmd_diagnose(args)

        call_args = mock_orch.run_single_ticker.call_args
        assert call_args.kwargs["fetch_data"] is True

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_custom_cache_dir(self, MockOrch):
        """--cache-dir passes to Orchestrator constructor."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15", "--cache-dir", "/tmp/my-cache"])
        cmd_diagnose(args)

        MockOrch.assert_called_once_with(cache_dir="/tmp/my-cache")

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_pipeline_error_returns_1(self, MockOrch, capsys):
        """Pipeline exception returns exit code 1."""
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(side_effect=RuntimeError("API down"))

        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "2024-01-15"])
        exit_code = cmd_diagnose(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "API down" in captured.err

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_invalid_date_returns_1(self, MockOrch, capsys):
        """Invalid date string returns exit code 1."""
        parser = create_parser()
        args = parser.parse_args(["diagnose", "SPY", "--date", "not-a-date"])
        exit_code = cmd_diagnose(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err or "error" in captured.err.lower()


class TestMainDiagnoseRouting:
    """Test main() routes diagnose to cmd_diagnose with pipeline."""

    @patch("obsidian.cli.Orchestrator")
    def test_main_diagnose_command(self, MockOrch, capsys):
        """main() routes diagnose command to pipeline."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        exit_code = main(["diagnose", "SPY", "--date", "2024-01-15"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "SPY" in captured.out

    @patch("obsidian.cli.Orchestrator")
    def test_main_diagnose_json(self, MockOrch, capsys):
        """main() JSON diagnose round-trip."""
        mock_result = _make_mock_result(ticker="AAPL")
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        exit_code = main(["diagnose", "AAPL", "--date", "2024-01-15", "--format", "json"])
        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["ticker"] == "AAPL"


class TestIntegration:
    """Test full CLI integration scenarios."""

    @patch("obsidian.cli.Orchestrator")
    def test_full_diagnose_workflow(self, MockOrch, capsys):
        """Full diagnose command workflow executes."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        exit_code = main(
            [
                "diagnose",
                "SPY",
                "--date",
                "2024-01-15",
                "--format",
                "text",
                "--cache-dir",
                "./test-cache",
            ]
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "SPY" in captured.out
        MockOrch.assert_called_once_with(cache_dir="test-cache")

    @patch("obsidian.cli.Orchestrator")
    def test_diagnose_with_no_cache_flag(self, MockOrch, capsys):
        """Diagnose with --no-cache flag passes fetch_data=False."""
        mock_result = _make_mock_result()
        mock_orch = MockOrch.return_value
        mock_orch.run_single_ticker = AsyncMock(return_value=mock_result)

        exit_code = main(["diagnose", "AAPL", "--no-cache", "--date", "2024-01-15"])

        assert exit_code == 0
        call_args = mock_orch.run_single_ticker.call_args
        assert call_args.kwargs["fetch_data"] is False
