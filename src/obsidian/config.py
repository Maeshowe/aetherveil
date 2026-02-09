"""Configuration management for OBSIDIAN MM.

Loads API keys and settings from environment variables using Pydantic.
All secrets must be stored in .env (never hardcoded).

Usage:
    from obsidian.config import settings

    print(settings.uw_api_key)  # Validated at import
    print(settings.log_level)
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OBSIDIAN MM configuration from environment variables.

    Loads from .env file automatically. Validates on instantiation.
    All API keys are required — system will not start without them.

    Attributes:
        uw_api_key: Unusual Whales API key (https://unusualwhales.com/api)
        polygon_api_key: Polygon.io API key (https://polygon.io)
        fmp_api_key: Financial Modeling Prep API key (https://financialmodelingprep.com)
        log_level: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
        cache_dir: Directory for Parquet cache files
        baseline_window: Rolling window for baseline stats (days)
        baseline_min_obs: Minimum observations for valid baseline
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars
    )

    # API Keys (REQUIRED)
    uw_api_key: str = Field(..., min_length=10, description="Unusual Whales API key")
    polygon_api_key: str = Field(..., min_length=10, description="Polygon.io API key")
    fmp_api_key: str = Field(..., min_length=10, description="FMP API key")

    # System Settings
    log_level: str = Field(default="INFO", description="Logging level")
    cache_dir: str = Field(default="data", description="Parquet cache directory")

    # Domain Constants (from spec Section 3)
    baseline_window: int = Field(
        default=63,
        ge=21,
        description="Rolling window for baseline stats (trading days)",
    )
    baseline_min_obs: int = Field(
        default=21,
        ge=1,
        description="Minimum non-NaN observations for valid baseline",
    )

    # FRED API (optional — graceful degradation if absent)
    fred_api_key: str | None = Field(
        default=None,
        description="FRED API key (https://fred.stlouisfed.org/docs/api/api_key.html)",
    )
    fred_rate_limit: int = Field(default=5, ge=1, description="FRED requests/second")

    # Rate Limiting (conservative defaults)
    uw_rate_limit: int = Field(default=10, ge=1, description="UW requests/second per client")
    uw_concurrency: int = Field(default=3, ge=1, le=50, description="Max concurrent UW ticker fetches")
    polygon_rate_limit: int = Field(default=5, ge=1, description="Polygon requests/second")
    fmp_rate_limit: int = Field(default=10, ge=1, description="FMP requests/second")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid:
            raise ValueError(f"log_level must be one of {valid}, got {v}")
        return v_upper

    @field_validator("baseline_min_obs", "baseline_window")
    @classmethod
    def validate_baseline_params(cls, v: int, info) -> int:
        """Ensure baseline parameters are valid."""
        if info.field_name == "baseline_min_obs":
            if v > 63:
                raise ValueError("baseline_min_obs cannot exceed baseline_window (63)")
        return v


# Global settings instance — loaded once at import
settings = Settings()
