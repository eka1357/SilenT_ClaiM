"""Open-Meteo Historical Weather API client with 4 s timeout and replay fallback.

Docs: https://open-meteo.com/en/docs/historical-weather-api
Endpoint: https://archive-api.open-meteo.com/v1/archive
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import Settings, get_settings, is_offline
from app.integrations.replay import (
    FIXTURES_DIR,
    HealthCallback,
    IntegrationMode,
    load_weather_fixture,
    weather_fixture_path,
)

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class WeatherUnavailableError(RuntimeError):
    """Raised when both live Open-Meteo and replay fixtures lack data for the requested dates."""


class OpenMeteoDaily(BaseModel):
    """Daily arrays returned by Open-Meteo archive API."""

    time: list[str]
    precipitation_sum: list[float | None]


class OpenMeteoArchiveResponse(BaseModel):
    """Validated subset of the Open-Meteo archive JSON response."""

    latitude: float
    longitude: float
    timezone: str | None = None
    daily: OpenMeteoDaily = Field(...)

    @model_validator(mode="after")
    def _lengths_match(self) -> OpenMeteoArchiveResponse:
        if len(self.daily.time) != len(self.daily.precipitation_sum):
            msg = "Open-Meteo daily time and precipitation_sum arrays have unequal lengths"
            raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class WeatherRangeResult:
    """Parsed daily precipitation series with live/replay provenance."""

    daily_rain_mm: dict[str, float]
    mode: IntegrationMode
    live: bool
    source: str
    raw_response: dict[str, Any]
    latency_ms: int


@dataclass(frozen=True, slots=True)
class WeatherDayResult:
    """Single-day precipitation reading with live/replay provenance."""

    day: date
    rain_mm: float
    mode: IntegrationMode
    live: bool
    source: str
    raw_response: dict[str, Any]
    latency_ms: int


def parse_open_meteo_response(payload: dict[str, Any]) -> dict[str, float]:
    """Validate an Open-Meteo archive JSON payload and return {iso_date: rain_mm}."""
    parsed = OpenMeteoArchiveResponse.model_validate(payload)
    return {
        day_str: float(val) if val is not None else 0.0
        for day_str, val in zip(parsed.daily.time, parsed.daily.precipitation_sum, strict=True)
    }


def _emit_health(callback: HealthCallback | None, mode: IntegrationMode) -> None:
    if callback is not None:
        callback("weather", mode)


def fetch_daily_rain_range(
    start_day: date | str,
    end_day: date | str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    fixtures_dir: Any = FIXTURES_DIR,
    health_callback: HealthCallback | None = None,
) -> WeatherRangeResult:
    """Fetch daily precipitation_sum (mm, Asia/Kolkata) from Open-Meteo or replay fixtures."""
    cfg = settings or get_settings()
    lat_val = cfg.weather_lat if lat is None else lat
    lon_val = cfg.weather_lon if lon is None else lon
    start_str = start_day.isoformat() if isinstance(start_day, date) else start_day
    end_str = end_day.isoformat() if isinstance(end_day, date) else end_day

    if is_offline(cfg):
        fixture = load_weather_fixture(
            lat_val, lon_val, start_str, end_str, fixtures_dir=fixtures_dir
        )
        if fixture is None:
            _emit_health(health_callback, "down")
            msg = f"No weather replay fixture found for {start_str}..{end_str}"
            raise WeatherUnavailableError(msg)
        daily_map = parse_open_meteo_response(fixture)
        _emit_health(health_callback, "replay")
        return WeatherRangeResult(
            daily_rain_mm=daily_map,
            mode="replay",
            live=False,
            source="Open-Meteo archive (Replay)",
            raw_response=fixture,
            latency_ms=0,
        )

    params: dict[str, str | float] = {
        "latitude": lat_val,
        "longitude": lon_val,
        "start_date": start_str,
        "end_date": end_str,
        "daily": "precipitation_sum",
        "timezone": cfg.tz,
    }

    t0 = time.monotonic()
    try:
        if client is not None:
            resp = client.get(
                OPEN_METEO_ARCHIVE_URL,
                params=params,
                timeout=cfg.request_timeout_s,
            )
        else:
            with httpx.Client(timeout=cfg.request_timeout_s) as own_client:
                resp = own_client.get(OPEN_METEO_ARCHIVE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
        daily_map = parse_open_meteo_response(payload)
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info("weather mode=live latency_ms=%d days=%d", latency_ms, len(daily_map))
        _emit_health(health_callback, "live")
        return WeatherRangeResult(
            daily_rain_mm=daily_map,
            mode="live",
            live=True,
            source="Open-Meteo archive (Live)",
            raw_response=payload,
            latency_ms=latency_ms,
        )
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "weather live call failed (%s) after %dms; falling back to replay",
            type(exc).__name__,
            latency_ms,
        )
        fixture = load_weather_fixture(
            lat_val, lon_val, start_str, end_str, fixtures_dir=fixtures_dir
        )
        if fixture is not None:
            daily_map = parse_open_meteo_response(fixture)
            _emit_health(health_callback, "replay")
            return WeatherRangeResult(
                daily_rain_mm=daily_map,
                mode="replay",
                live=False,
                source="Open-Meteo archive (Replay fallback)",
                raw_response=fixture,
                latency_ms=latency_ms,
            )
        _emit_health(health_callback, "down")
        msg = f"Open-Meteo unavailable and no replay fixture covers {start_str}..{end_str}"
        raise WeatherUnavailableError(msg) from exc


def get_daily_rain_mm(
    target_day: date | str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    fixtures_dir: Any = FIXTURES_DIR,
    health_callback: HealthCallback | None = None,
) -> WeatherDayResult:
    """Retrieve daily precipitation_sum (mm) for a single calendar day."""
    day_obj = target_day if isinstance(target_day, date) else date.fromisoformat(target_day)
    day_iso = day_obj.isoformat()
    range_res = fetch_daily_rain_range(
        start_day=day_iso,
        end_day=day_iso,
        lat=lat,
        lon=lon,
        settings=settings,
        client=client,
        fixtures_dir=fixtures_dir,
        health_callback=health_callback,
    )
    if day_iso not in range_res.daily_rain_mm:
        _emit_health(health_callback, "down")
        msg = f"Open-Meteo response missing precipitation_sum for {day_iso}"
        raise WeatherUnavailableError(msg)
    return WeatherDayResult(
        day=day_obj,
        rain_mm=range_res.daily_rain_mm[day_iso],
        mode=range_res.mode,
        live=range_res.live,
        source=range_res.source,
        raw_response=range_res.raw_response,
        latency_ms=range_res.latency_ms,
    )


__all__ = [
    "OPEN_METEO_ARCHIVE_URL",
    "OpenMeteoArchiveResponse",
    "WeatherDayResult",
    "WeatherRangeResult",
    "WeatherUnavailableError",
    "fetch_daily_rain_range",
    "get_daily_rain_mm",
    "parse_open_meteo_response",
    "weather_fixture_path",
]
