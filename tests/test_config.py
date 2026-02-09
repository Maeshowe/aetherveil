"""Tests for configuration management."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from obsidian.config import Settings


def test_settings_loads_from_env(monkeypatch):
    """Settings should load API keys from environment variables."""
    monkeypatch.setenv("UW_API_KEY", "test_uw_key_1234567890")
    monkeypatch.setenv("POLYGON_API_KEY", "test_polygon_key_1234567890")
    monkeypatch.setenv("FMP_API_KEY", "test_fmp_key_1234567890")

    settings = Settings()

    assert settings.uw_api_key == "test_uw_key_1234567890"
    assert settings.polygon_api_key == "test_polygon_key_1234567890"
    assert settings.fmp_api_key == "test_fmp_key_1234567890"


def test_settings_has_defaults():
    """Settings should have sensible defaults for optional fields."""
    # Use monkeypatch to provide required API keys
    os.environ["UW_API_KEY"] = "test_key_1234567890"
    os.environ["POLYGON_API_KEY"] = "test_key_1234567890"
    os.environ["FMP_API_KEY"] = "test_key_1234567890"

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.cache_dir == "data"
    assert settings.baseline_window == 63
    assert settings.baseline_min_obs == 21


def test_settings_validates_log_level(monkeypatch):
    """Settings should validate log level."""
    monkeypatch.setenv("UW_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("FMP_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("LOG_LEVEL", "INVALID")

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "log_level must be one of" in str(exc_info.value)


def test_settings_requires_api_keys(monkeypatch, tmp_path):
    """Settings should fail if API keys are missing."""
    # Clear all API key env vars
    monkeypatch.delenv("UW_API_KEY", raising=False)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    # Create empty .env file in temp directory to prevent loading from real .env
    empty_env = tmp_path / ".env"
    empty_env.write_text("")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    error_str = str(exc_info.value)
    assert "uw_api_key" in error_str.lower()


def test_settings_validates_api_key_length(monkeypatch):
    """Settings should reject API keys that are too short."""
    monkeypatch.setenv("UW_API_KEY", "short")  # Less than 10 chars
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("FMP_API_KEY", "test_key_1234567890")

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "uw_api_key" in str(exc_info.value).lower()


def test_baseline_window_constraint(monkeypatch):
    """Baseline window must be at least 21 days."""
    monkeypatch.setenv("UW_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("FMP_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("BASELINE_WINDOW", "10")  # Less than 21

    with pytest.raises(ValidationError):
        Settings()


def test_baseline_min_obs_cannot_exceed_window(monkeypatch):
    """Baseline min_obs cannot be greater than window."""
    monkeypatch.setenv("UW_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("FMP_API_KEY", "test_key_1234567890")
    monkeypatch.setenv("BASELINE_MIN_OBS", "100")  # Greater than default window (63)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "cannot exceed baseline_window" in str(exc_info.value)
