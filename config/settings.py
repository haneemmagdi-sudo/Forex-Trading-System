"""
============================================================
config/settings.py — Antigravity Data Layer Configuration
============================================================
Secure, centralized settings management using pydantic-settings.
All secrets are loaded exclusively from environment variables
or a .env file — never hardcoded.

Usage:
    from config.settings import settings

    key = settings.FMP_API_KEY
    provider = settings.DEFAULT_EQUITY_PROVIDER
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Resolve root .env file (two levels up from this file) ──────────────
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class OpenBBProviderSettings(BaseSettings):
    """
    Pydantic-Settings model for all Antigravity Data Layer configuration.

    All values are sourced from environment variables or the project-root
    `.env` file.  Sensitive fields are typed as ``SecretStr`` so that they
    are redacted in log output.

    Attributes:
        OPENBB_PAT: Personal Access Token for OpenBB Hub (optional).
        FMP_API_KEY: Financial Modeling Prep API key (equity fundamentals).
        POLYGON_API_KEY: Polygon.io API key (real-time quotes / order book).
        FRED_API_KEY: FRED (St. Louis Fed) API key (macro indicators).
        ALPHAVANTAGE_API_KEY: Alpha Vantage key (technical indicators).
        FINNHUB_API_KEY: Finnhub key (news sentiment).
        TIINGO_API_KEY: Tiingo key (alternative historical OHLCV).
        DEFAULT_EQUITY_PROVIDER: Which provider is used by default for equities.
        DEFAULT_MACRO_PROVIDER: Which provider is used for macro data.
        CACHE_TTL_SECONDS: How long cached data remains valid (default 900 = 15 min).
        CACHE_DB_PATH: Filesystem path for the SQLite cache database.
        LOG_LEVEL: Logging verbosity level.
        ENVIRONMENT: Deployment environment tag (development / staging / production).
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,          # OPENBB_PAT == openbb_pat
        extra="ignore",                # ignore unknown env vars gracefully
        populate_by_name=True,
    )

    # ── OpenBB Hub (optional — syncs API keys across devices) ───────────
    OPENBB_PAT: Optional[SecretStr] = Field(
        default=None,
        description="OpenBB Hub Personal Access Token",
        alias="OPENBB_PAT",
    )

    # ── Data Provider API Keys ───────────────────────────────────────────
    FMP_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Financial Modeling Prep API key",
    )
    POLYGON_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Polygon.io API key (real-time + order book)",
    )
    FRED_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="St. Louis Federal Reserve FRED API key",
    )
    ALPHAVANTAGE_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Alpha Vantage API key",
    )
    FINNHUB_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Finnhub.io API key (news + sentiment)",
    )
    TIINGO_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Tiingo API key (alternative OHLCV source)",
    )

    # ── Provider Preferences ─────────────────────────────────────────────
    DEFAULT_EQUITY_PROVIDER: str = Field(
        default="yfinance",
        description=(
            "Default provider for equity OHLCV and quote calls. "
            "Options: yfinance | fmp | polygon | tiingo"
        ),
    )
    DEFAULT_FUNDAMENTAL_PROVIDER: str = Field(
        default="fmp",
        description=(
            "Default provider for fundamental financial data. "
            "Options: fmp | yfinance"
        ),
    )
    DEFAULT_MACRO_PROVIDER: str = Field(
        default="fred",
        description=(
            "Default provider for macroeconomic indicators. "
            "Options: fred | econdb"
        ),
    )
    DEFAULT_NEWS_PROVIDER: str = Field(
        default="tiingo",
        description=(
            "Default provider for news and sentiment. "
            "Options: tiingo | fmp | intrinio"
        ),
    )

    # ── Caching ──────────────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = Field(
        default=900,          # 15 minutes
        ge=60,
        le=86400,
        description="Time-to-live for cached API responses (seconds).",
    )
    CACHE_DB_PATH: str = Field(
        default="data_layer/cache/market_data.db",
        description="Relative or absolute path for the SQLite cache file.",
    )

    # ── General ──────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
    )
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
    )

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("DEFAULT_EQUITY_PROVIDER")
    @classmethod
    def validate_equity_provider(cls, v: str) -> str:
        allowed = {"yfinance", "fmp", "polygon", "tiingo", "intrinio"}
        if v not in allowed:
            raise ValueError(
                f"DEFAULT_EQUITY_PROVIDER must be one of {allowed}, got '{v}'"
            )
        return v

    @field_validator("DEFAULT_MACRO_PROVIDER")
    @classmethod
    def validate_macro_provider(cls, v: str) -> str:
        allowed = {"fred", "econdb", "oecd"}
        if v not in allowed:
            raise ValueError(
                f"DEFAULT_MACRO_PROVIDER must be one of {allowed}, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def warn_missing_keys(self) -> "OpenBBProviderSettings":
        """
        Emit runtime warnings for providers that require API keys but
        have not been configured.  This does NOT raise — the system can
        still fall back to free providers (yfinance / FRED demo).
        """
        import warnings

        if self.DEFAULT_EQUITY_PROVIDER == "fmp" and not self.FMP_API_KEY:
            warnings.warn(
                "DEFAULT_EQUITY_PROVIDER='fmp' but FMP_API_KEY is not set. "
                "Set FMP_API_KEY in .env or fall back to 'yfinance'.",
                RuntimeWarning,
                stacklevel=2,
            )
        if self.DEFAULT_EQUITY_PROVIDER == "polygon" and not self.POLYGON_API_KEY:
            warnings.warn(
                "DEFAULT_EQUITY_PROVIDER='polygon' but POLYGON_API_KEY is not set.",
                RuntimeWarning,
                stacklevel=2,
            )
        if self.DEFAULT_MACRO_PROVIDER == "fred" and not self.FRED_API_KEY:
            warnings.warn(
                "DEFAULT_MACRO_PROVIDER='fred' but FRED_API_KEY is not set. "
                "FRED allows anonymous access for basic series but sets strict rate limits.",
                RuntimeWarning,
                stacklevel=2,
            )
        return self

    # ── Convenience helpers ──────────────────────────────────────────────

    def get_secret(self, field_name: str) -> Optional[str]:
        """
        Safely retrieve the plaintext value of a SecretStr field by name.

        Args:
            field_name: Attribute name of the SecretStr field (e.g., 'FMP_API_KEY').

        Returns:
            The plaintext secret string, or None if not configured.
        """
        value = getattr(self, field_name, None)
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return value

    def get_openbb_provider_credentials(self) -> dict[str, Optional[str]]:
        """
        Build a flat mapping of provider credential names used by OpenBB.
        These names correspond to what ``obb.user.credentials`` expects.

        Returns:
            Dict mapping OpenBB credential keys to their plaintext values.
        """
        return {
            "fmp_api_key": self.get_secret("FMP_API_KEY"),
            "polygon_api_key": self.get_secret("POLYGON_API_KEY"),
            "fred_api_key": self.get_secret("FRED_API_KEY"),
            "alpha_vantage_api_key": self.get_secret("ALPHAVANTAGE_API_KEY"),
            "finnhub_api_key": self.get_secret("FINNHUB_API_KEY"),
            "tiingo_token": self.get_secret("TIINGO_API_KEY"),
        }

    def resolved_cache_db_path(self) -> Path:
        """
        Return an absolute Path for the SQLite cache database,
        creating parent directories if they do not exist.

        Returns:
            Absolute Path object pointing to the cache DB file.
        """
        path = Path(self.CACHE_DB_PATH)
        if not path.is_absolute():
            # Resolve relative to project root (two levels up from this file)
            path = Path(__file__).resolve().parents[1] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> OpenBBProviderSettings:
    """
    Module-level singleton factory for ``OpenBBProviderSettings``.

    Cached via ``functools.lru_cache`` so the .env file is only
    parsed once per process lifetime.

    Returns:
        Singleton ``OpenBBProviderSettings`` instance.
    """
    return OpenBBProviderSettings()


# ── Public module-level alias ────────────────────────────────────────────
settings: OpenBBProviderSettings = get_settings()
