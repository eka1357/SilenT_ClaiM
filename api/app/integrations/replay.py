"""Offline fixture store and replay loader for DEMO_OFFLINE=1 and live fallbacks.

Fixtures stored in api/tests/fixtures/ are unmodified real recorded API responses
(with secrets excluded) so contract tests and offline demos replay real payloads.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal

IntegrationMode = Literal["live", "replay", "down"]
HealthCallback = Callable[[str, IntegrationMode], None]

API_ROOT: Path = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR: Path = API_ROOT / "tests" / "fixtures"
TTS_CACHE_DIR: Path = API_ROOT / "runs" / "tts_cache"


def short_text_hash(text: str) -> str:
    """Return a deterministic 16-char SHA-256 hex digest for UTF-8 text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def short_bytes_hash(data: bytes) -> str:
    """Return a deterministic 16-char SHA-256 hex digest for binary payloads."""
    return hashlib.sha256(data).hexdigest()[:16]


def weather_fixture_path(
    lat: float,
    lon: float,
    start_day: date | str,
    end_day: date | str,
    fixtures_dir: Path = FIXTURES_DIR,
) -> Path:
    """Canonical path for a recorded Open-Meteo archive response."""
    start_str = start_day.isoformat() if isinstance(start_day, date) else start_day
    end_str = end_day.isoformat() if isinstance(end_day, date) else end_day
    return fixtures_dir / f"weather_{lat:.2f}_{lon:.2f}_{start_str}_{end_str}.json"


def save_json_fixture(path: Path, payload: dict[str, Any]) -> Path:
    """Persist a raw API JSON response fixture without adding wrapper keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_weather_fixture(
    lat: float,
    lon: float,
    start_day: date | str,
    end_day: date | str,
    fixtures_dir: Path = FIXTURES_DIR,
) -> dict[str, Any] | None:
    """Load an exact or covering recorded Open-Meteo archive JSON fixture."""
    exact = weather_fixture_path(lat, lon, start_day, end_day, fixtures_dir=fixtures_dir)
    if exact.exists():
        return json.loads(exact.read_text(encoding="utf-8"))

    if not fixtures_dir.exists():
        return None

    start_str = start_day.isoformat() if isinstance(start_day, date) else start_day
    end_str = end_day.isoformat() if isinstance(end_day, date) else end_day
    prefix = f"weather_{lat:.2f}_{lon:.2f}_"
    for candidate in sorted(fixtures_dir.glob(f"{prefix}*.json")):
        data = json.loads(candidate.read_text(encoding="utf-8"))
        times: list[str] = data.get("daily", {}).get("time", [])
        if times and times[0] <= start_str and times[-1] >= end_str:
            return data
    return None


def tts_cache_path(text: str, cache_dir: Path = TTS_CACHE_DIR) -> Path:
    """Disk cache path for synthesized WAV audio keyed by hash of prompt text."""
    return cache_dir / f"tts_{short_text_hash(text)}.wav"


def load_tts_fixture(
    text: str,
    fixtures_dir: Path = FIXTURES_DIR,
) -> tuple[dict[str, Any] | None, bytes | None]:
    """Load a recorded Sarvam TTS JSON response and/or WAV bytes by text hash."""
    if not fixtures_dir.exists():
        return None, None
    digest = short_text_hash(text)
    json_matches = sorted(fixtures_dir.glob(f"sarvam_tts_*_{digest}.json"))
    wav_matches = sorted(fixtures_dir.glob(f"sarvam_tts_*_{digest}.wav"))
    raw_json = json.loads(json_matches[0].read_text(encoding="utf-8")) if json_matches else None
    wav_bytes = wav_matches[0].read_bytes() if wav_matches else None
    return raw_json, wav_bytes


def load_stt_fixture(
    audio_bytes: bytes,
    fixtures_dir: Path = FIXTURES_DIR,
) -> dict[str, Any] | None:
    """Load a recorded Sarvam STT JSON response matching the audio SHA-256 hash."""
    if not fixtures_dir.exists():
        return None
    digest = short_bytes_hash(audio_bytes)
    matches = sorted(fixtures_dir.glob(f"sarvam_stt_*_{digest}.json"))
    if not matches:
        return None
    return json.loads(matches[0].read_text(encoding="utf-8"))


def load_llm_fixture(
    transcript: str,
    fixtures_dir: Path = FIXTURES_DIR,
) -> dict[str, Any] | None:
    """Load a recorded Gemini classification JSON response matching the transcript hash."""
    if not fixtures_dir.exists():
        return None
    digest = short_text_hash(transcript)
    matches = sorted(fixtures_dir.glob(f"llm_classify_*_{digest}.json"))
    if not matches:
        return None
    return json.loads(matches[0].read_text(encoding="utf-8"))
