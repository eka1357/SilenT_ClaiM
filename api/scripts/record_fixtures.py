"""Record real API responses into api/tests/fixtures/ for offline contract tests & replay.

Requires network access and valid SARVAM_API_KEY + LLM_API_KEY in api/.env.
Never writes API keys or secrets into fixtures.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.integrations.llm import classify_reply
from app.integrations.replay import (
    FIXTURES_DIR,
    save_json_fixture,
    short_bytes_hash,
    short_text_hash,
    weather_fixture_path,
)
from app.integrations.sarvam import DEFAULT_KEYTERMS, synthesize_tamil, transcribe_tamil
from app.integrations.weather import fetch_daily_rain_range

PROMPT_TEXT_TA = (
    "மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?"
)
SAMPLE_FILES: tuple[str, ...] = (
    "tts_flood.wav",
    "tts_leave.wav",
    "tts_qr_switch.wav",
    "tts_yes.wav",
)
SAMPLES_DIR = API_ROOT / "samples"
START_DAY = date(2026, 9, 24)
END_DAY = date(2026, 10, 22)


def _assert_no_secrets(fixtures_dir: Path, secrets: list[str]) -> None:
    non_empty = [s for s in secrets if s and len(s) >= 8]
    for path in fixtures_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for secret in non_empty:
            if secret in text:
                msg = f"Secret value leaked into fixture {path.name}; aborting!"
                raise RuntimeError(msg)


def main() -> None:
    """Record live responses from Open-Meteo, Sarvam TTS/STT, and Gemini classifier."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Force live calls even if caller shell had DEMO_OFFLINE=1
    os.environ["DEMO_OFFLINE"] = "0"
    cfg = get_settings()
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Open-Meteo historical archive response (24 Sep to 22 Oct 2026)
    weather_res = fetch_daily_rain_range(
        start_day=START_DAY,
        end_day=END_DAY,
        lat=cfg.weather_lat,
        lon=cfg.weather_lon,
        settings=cfg,
    )
    if not weather_res.live:
        msg = "Expected live Open-Meteo response while recording fixtures"
        raise RuntimeError(msg)
    weather_path = weather_fixture_path(
        cfg.weather_lat, cfg.weather_lon, START_DAY, END_DAY, fixtures_dir=FIXTURES_DIR
    )
    save_json_fixture(weather_path, weather_res.raw_response)
    print(f"Recorded weather fixture: {weather_path.name}")

    # 2. Sarvam TTS prompt response
    tts_res = synthesize_tamil(PROMPT_TEXT_TA, use_cache=False, settings=cfg)
    if not tts_res.live or tts_res.raw_response is None:
        msg = "Expected live Sarvam TTS response while recording fixtures"
        raise RuntimeError(msg)
    tts_hash = short_text_hash(PROMPT_TEXT_TA)
    tts_json_path = FIXTURES_DIR / f"sarvam_tts_prompt_{tts_hash}.json"
    tts_wav_path = FIXTURES_DIR / f"sarvam_tts_prompt_{tts_hash}.wav"
    save_json_fixture(tts_json_path, tts_res.raw_response)
    tts_wav_path.write_bytes(tts_res.audio_bytes)
    print(f"Recorded Sarvam TTS fixtures: {tts_json_path.name}, {tts_wav_path.name}")

    # 3 & 4. Sarvam STT + Gemini classification for each synthetic reply in api/samples/
    llm_failures: list[str] = []
    for filename in SAMPLE_FILES:
        sample_path = SAMPLES_DIR / filename
        stem = sample_path.stem
        audio_bytes = sample_path.read_bytes()
        audio_hash = short_bytes_hash(audio_bytes)

        stt_res = transcribe_tamil(
            audio_bytes,
            filename=filename,
            content_type="audio/wav",
            model="saaras:v4",
            mode="transcribe",
            language_code="ta-IN",
            keyterms=DEFAULT_KEYTERMS,
            settings=cfg,
        )
        if not stt_res.live:
            msg = f"Expected live Sarvam STT response for {filename}"
            raise RuntimeError(msg)

        stt_path = FIXTURES_DIR / f"sarvam_stt_{stem}_{audio_hash}.json"
        save_json_fixture(stt_path, stt_res.raw_response)
        print(f"Recorded STT fixture: {stt_path.name} (tamil={stt_res.is_tamil_script})")

        cls_res = classify_reply(
            stt_res.transcript,
            settings=cfg,
            allow_replay_fallback=False,
        )
        if not cls_res.live or cls_res.raw_response is None:
            llm_failures.append(f"{filename}: {cls_res.fallback_reason or cls_res.mode}")
            print(
                f"Skipped LLM fixture for {filename}: live call failed "
                f"(mode={cls_res.mode}, reason={cls_res.fallback_reason})"
            )
            continue

        text_hash = short_text_hash(stt_res.transcript)
        llm_path = FIXTURES_DIR / f"llm_classify_{stem}_{text_hash}.json"
        save_json_fixture(llm_path, cls_res.raw_response)
        print(
            f"Recorded LLM fixture: {llm_path.name} "
            f"(label={cls_res.cause_label.value}, conf={cls_res.confidence:.2f})"
        )

    _assert_no_secrets(
        FIXTURES_DIR,
        [
            cfg.sarvam_api_key.get_secret_value(),
            cfg.llm_api_key.get_secret_value(),
            cfg.paytm_merchant_key.get_secret_value(),
        ],
    )
    print("Secret scan passed: zero keys found in recorded fixtures.")
    if llm_failures:
        msg = f"Failed to record live LLM fixtures: {'; '.join(llm_failures)}"
        raise SystemExit(msg)


if __name__ == "__main__":
    main()
