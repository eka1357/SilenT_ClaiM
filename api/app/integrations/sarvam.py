"""Sarvam AI Tamil TTS (bulbul:v3) and STT (saaras:v4) client with 4 s timeout.

Docs: https://docs.sarvam.ai
Endpoints:
- POST https://api.sarvam.ai/text-to-speech
- POST https://api.sarvam.ai/speech-to-text

Security: never log API keys, raw audio bytes, or full transcripts.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings, get_settings, is_offline
from app.integrations.replay import (
    FIXTURES_DIR,
    TTS_CACHE_DIR,
    HealthCallback,
    IntegrationMode,
    load_stt_fixture,
    load_tts_fixture,
    short_bytes_hash,
    short_text_hash,
    tts_cache_path,
)

logger = logging.getLogger(__name__)

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = "ishita"
TTS_LANGUAGE_CODE = "ta-IN"
TTS_SAMPLE_RATE = 24000

STT_MODEL = "saaras:v4"
STT_LANGUAGE_CODE = "ta-IN"
STT_MODE = "transcribe"
DEFAULT_KEYTERMS: tuple[str, ...] = ("QR", "Paytm")

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MB cap per docs/SECURITY.md


class SarvamUnavailableError(RuntimeError):
    """Raised when Sarvam AI fails and no matching offline fixture exists."""


class SarvamTTSResponse(BaseModel):
    """Validated JSON response from Sarvam /text-to-speech."""

    request_id: str | None = None
    audios: list[str] = Field(min_length=1)


class SarvamSTTResponse(BaseModel):
    """Validated JSON response from Sarvam /speech-to-text."""

    request_id: str | None = None
    transcript: str
    language_code: str | None = None


@dataclass(frozen=True, slots=True)
class TTSResult:
    """Synthesized Tamil prompt audio and provenance."""

    audio_bytes: bytes
    audio_path: Path | None
    request_id: str | None
    mode: IntegrationMode
    live: bool
    cached: bool
    raw_response: dict[str, Any] | None
    latency_ms: int


@dataclass(frozen=True, slots=True)
class STTResult:
    """Transcribed Tamil reply and provenance."""

    transcript: str
    is_tamil_script: bool
    language_code: str | None
    request_id: str | None
    mode: IntegrationMode
    live: bool
    raw_response: dict[str, Any]
    latency_ms: int


def contains_tamil_script(text: str) -> bool:
    """Return True if text contains at least one Unicode Tamil character (U+0B80..U+0BFF)."""
    return any("\u0b80" <= ch <= "\u0bff" for ch in text)


def _emit_health(callback: HealthCallback | None, mode: IntegrationMode) -> None:
    if callback is not None:
        callback("sarvam", mode)


def parse_tts_response(payload: dict[str, Any]) -> tuple[SarvamTTSResponse, bytes]:
    """Validate Sarvam TTS JSON payload and decode the WAV audio bytes."""
    parsed = SarvamTTSResponse.model_validate(payload)
    audio_bytes = base64.b64decode(parsed.audios[0], validate=True)
    if not audio_bytes:
        msg = "Sarvam TTS decoded audio payload is empty"
        raise ValueError(msg)
    return parsed, audio_bytes


def parse_stt_response(payload: dict[str, Any]) -> SarvamSTTResponse:
    """Validate Sarvam STT JSON payload."""
    return SarvamSTTResponse.model_validate(payload)


def synthesize_tamil(
    text: str,
    *,
    speaker: str = TTS_SPEAKER,
    model: str = TTS_MODEL,
    language_code: str = TTS_LANGUAGE_CODE,
    pace: float = 1.0,
    speech_sample_rate: int = TTS_SAMPLE_RATE,
    use_cache: bool = True,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    fixtures_dir: Path = FIXTURES_DIR,
    cache_dir: Path = TTS_CACHE_DIR,
    health_callback: HealthCallback | None = None,
) -> TTSResult:
    """Synthesize Tamil speech via Sarvam bulbul:v3, with disk cache and replay fallback."""
    if not text.strip():
        msg = "TTS text must not be empty"
        raise ValueError(msg)

    cfg = settings or get_settings()
    text_hash = short_text_hash(text)
    cache_file = tts_cache_path(text, cache_dir=cache_dir)

    if is_offline(cfg):
        raw_json, wav_bytes = load_tts_fixture(text, fixtures_dir=fixtures_dir)
        if raw_json is not None:
            parsed, decoded = parse_tts_response(raw_json)
            audio = wav_bytes or decoded
            _emit_health(health_callback, "replay")
            return TTSResult(
                audio_bytes=audio,
                audio_path=cache_file if cache_file.exists() else None,
                request_id=parsed.request_id,
                mode="replay",
                live=False,
                cached=False,
                raw_response=raw_json,
                latency_ms=0,
            )
        if wav_bytes is not None:
            _emit_health(health_callback, "replay")
            return TTSResult(
                audio_bytes=wav_bytes,
                audio_path=None,
                request_id=None,
                mode="replay",
                live=False,
                cached=False,
                raw_response=None,
                latency_ms=0,
            )
        if use_cache and cache_file.exists():
            _emit_health(health_callback, "replay")
            return TTSResult(
                audio_bytes=cache_file.read_bytes(),
                audio_path=cache_file,
                request_id=None,
                mode="replay",
                live=False,
                cached=True,
                raw_response=None,
                latency_ms=0,
            )
        _emit_health(health_callback, "down")
        msg = f"No Sarvam TTS replay fixture found for text hash {text_hash}"
        raise SarvamUnavailableError(msg)

    if use_cache and cache_file.exists():
        logger.info("sarvam_tts mode=cache text_hash=%s", text_hash)
        _emit_health(health_callback, "live")
        return TTSResult(
            audio_bytes=cache_file.read_bytes(),
            audio_path=cache_file,
            request_id=None,
            mode="live",
            live=True,
            cached=True,
            raw_response=None,
            latency_ms=0,
        )

    api_key = cfg.sarvam_api_key.get_secret_value()
    if not api_key:
        raw_json, wav_bytes = load_tts_fixture(text, fixtures_dir=fixtures_dir)
        if raw_json is not None:
            parsed, decoded = parse_tts_response(raw_json)
            _emit_health(health_callback, "replay")
            return TTSResult(
                audio_bytes=wav_bytes or decoded,
                audio_path=None,
                request_id=parsed.request_id,
                mode="replay",
                live=False,
                cached=False,
                raw_response=raw_json,
                latency_ms=0,
            )
        _emit_health(health_callback, "down")
        msg = "SARVAM_API_KEY is not configured and no replay fixture matched"
        raise SarvamUnavailableError(msg)

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "text": text,
        "target_language_code": language_code,
        "model": model,
        "speaker": speaker,
        "pace": pace,
        "speech_sample_rate": speech_sample_rate,
        "output_audio_codec": "wav",
    }

    t0 = time.monotonic()
    try:
        if client is not None:
            resp = client.post(
                SARVAM_TTS_URL, headers=headers, json=body, timeout=cfg.request_timeout_s
            )
        else:
            with httpx.Client(timeout=cfg.request_timeout_s) as own_client:
                resp = own_client.post(SARVAM_TTS_URL, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()
        parsed, audio_bytes = parse_tts_response(payload)

        saved_path: Path | None = None
        if use_cache:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(audio_bytes)
            saved_path = cache_file

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "sarvam_tts mode=live text_hash=%s latency_ms=%d bytes=%d",
            text_hash,
            latency_ms,
            len(audio_bytes),
        )
        _emit_health(health_callback, "live")
        return TTSResult(
            audio_bytes=audio_bytes,
            audio_path=saved_path,
            request_id=parsed.request_id,
            mode="live",
            live=True,
            cached=False,
            raw_response=payload,
            latency_ms=latency_ms,
        )
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "sarvam_tts failed (%s) after %dms; trying replay fixture",
            type(exc).__name__,
            latency_ms,
        )
        raw_json, wav_bytes = load_tts_fixture(text, fixtures_dir=fixtures_dir)
        if raw_json is not None or wav_bytes is not None:
            parsed_fix = parse_tts_response(raw_json) if raw_json is not None else None
            audio = wav_bytes or (parsed_fix[1] if parsed_fix is not None else b"")
            _emit_health(health_callback, "replay")
            return TTSResult(
                audio_bytes=audio,
                audio_path=None,
                request_id=parsed_fix[0].request_id if parsed_fix is not None else None,
                mode="replay",
                live=False,
                cached=False,
                raw_response=raw_json,
                latency_ms=latency_ms,
            )
        _emit_health(health_callback, "down")
        msg = f"Sarvam TTS failed ({type(exc).__name__}) and no replay fixture exists"
        raise SarvamUnavailableError(msg) from exc


def transcribe_tamil(
    audio_bytes: bytes,
    *,
    filename: str = "reply.wav",
    content_type: str = "audio/wav",
    model: str = STT_MODEL,
    mode: str = STT_MODE,
    language_code: str = STT_LANGUAGE_CODE,
    keyterms: tuple[str, ...] | list[str] = DEFAULT_KEYTERMS,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    fixtures_dir: Path = FIXTURES_DIR,
    health_callback: HealthCallback | None = None,
) -> STTResult:
    """Transcribe Tamil audio using Sarvam saaras:v4 with transcribe mode and keyterms."""
    if not audio_bytes:
        msg = "Audio payload must not be empty"
        raise ValueError(msg)
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        msg = f"Audio exceeds 2 MB limit ({len(audio_bytes)} bytes)"
        raise ValueError(msg)

    cfg = settings or get_settings()
    audio_hash = short_bytes_hash(audio_bytes)

    if is_offline(cfg):
        fixture = load_stt_fixture(audio_bytes, fixtures_dir=fixtures_dir)
        if fixture is None:
            _emit_health(health_callback, "down")
            msg = f"No Sarvam STT replay fixture found for audio hash {audio_hash}"
            raise SarvamUnavailableError(msg)
        parsed = parse_stt_response(fixture)
        _emit_health(health_callback, "replay")
        return STTResult(
            transcript=parsed.transcript,
            is_tamil_script=contains_tamil_script(parsed.transcript),
            language_code=parsed.language_code,
            request_id=parsed.request_id,
            mode="replay",
            live=False,
            raw_response=fixture,
            latency_ms=0,
        )

    api_key = cfg.sarvam_api_key.get_secret_value()
    if not api_key:
        fixture = load_stt_fixture(audio_bytes, fixtures_dir=fixtures_dir)
        if fixture is not None:
            parsed = parse_stt_response(fixture)
            _emit_health(health_callback, "replay")
            return STTResult(
                transcript=parsed.transcript,
                is_tamil_script=contains_tamil_script(parsed.transcript),
                language_code=parsed.language_code,
                request_id=parsed.request_id,
                mode="replay",
                live=False,
                raw_response=fixture,
                latency_ms=0,
            )
        _emit_health(health_callback, "down")
        msg = "SARVAM_API_KEY is not configured and no replay fixture matched"
        raise SarvamUnavailableError(msg)

    headers = {"api-subscription-key": api_key}

    def _call_stt(req_mode: str) -> tuple[dict[str, Any], SarvamSTTResponse]:
        form_data: dict[str, str] = {
            "model": model,
            "mode": req_mode,
            "language_code": language_code,
            "keyterms": json.dumps(list(keyterms)),
        }
        files = {"file": (filename, audio_bytes, content_type)}
        if client is not None:
            resp = client.post(
                SARVAM_STT_URL,
                headers=headers,
                data=form_data,
                files=files,
                timeout=cfg.request_timeout_s,
            )
        else:
            with httpx.Client(timeout=cfg.request_timeout_s) as own_client:
                resp = own_client.post(
                    SARVAM_STT_URL,
                    headers=headers,
                    data=form_data,
                    files=files,
                )
        resp.raise_for_status()
        raw_payload = resp.json()
        return raw_payload, parse_stt_response(raw_payload)

    t0 = time.monotonic()
    try:
        payload, parsed = _call_stt(mode)
        is_tamil = contains_tamil_script(parsed.transcript)

        # If caller did not force transcribe mode and English/Latin came back, re-run in transcribe mode.
        if not is_tamil and mode != STT_MODE:
            logger.info(
                "sarvam_stt non_tamil_script_detected audio_hash=%s retrying_mode=%s",
                audio_hash,
                STT_MODE,
            )
            payload, parsed = _call_stt(STT_MODE)
            is_tamil = contains_tamil_script(parsed.transcript)

        if not is_tamil:
            logger.warning(
                "sarvam_stt transcript_missing_tamil_script audio_hash=%s mode=%s",
                audio_hash,
                mode,
            )

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "sarvam_stt mode=live audio_hash=%s latency_ms=%d tamil_script=%s",
            audio_hash,
            latency_ms,
            is_tamil,
        )
        _emit_health(health_callback, "live")
        return STTResult(
            transcript=parsed.transcript,
            is_tamil_script=is_tamil,
            language_code=parsed.language_code,
            request_id=parsed.request_id,
            mode="live",
            live=True,
            raw_response=payload,
            latency_ms=latency_ms,
        )
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "sarvam_stt failed (%s) after %dms; trying replay fixture",
            type(exc).__name__,
            latency_ms,
        )
        fixture = load_stt_fixture(audio_bytes, fixtures_dir=fixtures_dir)
        if fixture is not None:
            parsed = parse_stt_response(fixture)
            _emit_health(health_callback, "replay")
            return STTResult(
                transcript=parsed.transcript,
                is_tamil_script=contains_tamil_script(parsed.transcript),
                language_code=parsed.language_code,
                request_id=parsed.request_id,
                mode="replay",
                live=False,
                raw_response=fixture,
                latency_ms=latency_ms,
            )
        _emit_health(health_callback, "down")
        msg = f"Sarvam STT failed ({type(exc).__name__}) and no replay fixture exists"
        raise SarvamUnavailableError(msg) from exc
