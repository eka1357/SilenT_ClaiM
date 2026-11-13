"""Application configuration loaded from api/.env via pydantic-settings.

Secrets are wrapped in SecretStr so they are never accidentally serialized or logged.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT: Path = Path(__file__).resolve().parent.parent
ENV_FILE: Path = API_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime configuration for Silent Claim."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = True
    demo_offline: bool = False
    payback_enabled: bool = True
    rate_limit_per_minute: int = 30
    tz: str = "Asia/Kolkata"

    database_url: SecretStr = Field(default=SecretStr("sqlite:///./silent_claim.db"))

    paytm_mode: str = "pending"
    paytm_host: str = "https://securestage.paytmpayments.com"
    paytm_mid: str = ""
    paytm_merchant_key: SecretStr = Field(default=SecretStr(""))
    paytm_website: str = "WEBSTAGING"

    sarvam_api_key: SecretStr = Field(default=SecretStr(""))

    llm_provider: str = "sarvam"
    llm_model: str = "sarvam-105b-conversations"
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_use_vertex_express: bool = False

    weather_lat: float = 13.04
    weather_lon: float = 80.25

    web_origin: str = "http://localhost:5173"
    request_timeout_s: float = 4.0


def get_settings() -> Settings:
    """Return freshly loaded settings so environment overrides take effect immediately."""
    return Settings()


def is_offline(settings: Settings | None = None) -> bool:
    """Check whether offline fixture replay mode (DEMO_OFFLINE=1) is active."""
    env_override = os.getenv("DEMO_OFFLINE")
    if env_override is not None:
        return env_override.strip().lower() in {"1", "true", "yes", "on"}
    cfg = settings or get_settings()
    return cfg.demo_offline
