"""Spike script: Tamil TTS prompt + STT & Gemini classification on api/samples/tts_*.wav.

Outputs:
- api/runs/prompt.wav (Sarvam bulbul:v3 Tamil TTS of the US2 prompt)
- api/runs/sarvam_spike.json (structured spike results labelled "Simulated reply")
- Printed table of transcript, predicted label, confidence, and expected US3 label.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.integrations.llm import classify_reply
from app.integrations.sarvam import DEFAULT_KEYTERMS, synthesize_tamil, transcribe_tamil

PROMPT_TEXT_TA = (
    "மழையால் உங்கள் தெருவில் 12 கடைகளில் 9 மூடியிருந்தன. உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?"
)

SAMPLE_CASES: tuple[tuple[str, str], ...] = (
    ("tts_flood.wav", "flood_closure"),
    ("tts_leave.wav", "leave"),
    ("tts_qr_switch.wav", "qr_switch"),
    ("tts_yes.wav", "consent (no label)"),
)

SAMPLES_DIR = API_ROOT / "samples"
RUNS_DIR = API_ROOT / "runs"


def _configure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    """Run Sarvam TTS, Sarvam STT, and Gemini classification spike."""
    _configure_utf8_stdout()
    settings = get_settings()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. TTS of the US2 Tamil prompt -> api/runs/prompt.wav
    tts_res = synthesize_tamil(PROMPT_TEXT_TA, use_cache=False, settings=settings)
    prompt_wav_path = RUNS_DIR / "prompt.wav"
    prompt_wav_path.write_bytes(tts_res.audio_bytes)
    print(
        f"TTS prompt saved to {prompt_wav_path} "
        f"({len(tts_res.audio_bytes)} bytes, mode={tts_res.mode}, latency={tts_res.latency_ms}ms)"
    )
    print("-" * 80)

    # 2. STT + classification on each synthetic sample in api/samples/
    results: list[dict[str, Any]] = []
    for filename, expected_label in SAMPLE_CASES:
        sample_path = SAMPLES_DIR / filename
        audio_bytes = sample_path.read_bytes()

        stt_res = transcribe_tamil(
            audio_bytes,
            filename=filename,
            content_type="audio/wav",
            model="saaras:v4",
            mode="transcribe",
            language_code="ta-IN",
            keyterms=DEFAULT_KEYTERMS,
            settings=settings,
        )
        cls_res = classify_reply(stt_res.transcript, settings=settings)

        entry: dict[str, Any] = {
            "file": filename,
            "source_label": "Simulated reply",
            "transcript": stt_res.transcript,
            "is_tamil_script": stt_res.is_tamil_script,
            "language_code": stt_res.language_code,
            "label": cls_res.cause_label.value,
            "confidence": round(cls_res.confidence, 4),
            "reason": cls_res.reason,
            "expected_label": expected_label,
            "stt_mode": stt_res.mode,
            "llm_provider": cls_res.provider,
            "llm_mode": cls_res.mode,
            "llm_model": cls_res.model,
            "llm_fallback_reason": cls_res.fallback_reason,
            "stt_latency_ms": stt_res.latency_ms,
            "llm_latency_ms": cls_res.latency_ms,
        }
        results.append(entry)

        print(f"File           : {filename} [Simulated reply]")
        print(f"Transcript     : {stt_res.transcript}")
        print(
            f"Tamil script?  : {stt_res.is_tamil_script} "
            f"(stt_mode={stt_res.mode}, lang={stt_res.language_code}, stt={stt_res.latency_ms}ms)"
        )
        print(
            f"Label          : {cls_res.cause_label.value} "
            f"(confidence={cls_res.confidence:.2f}, reason={cls_res.reason!r}, "
            f"provider={cls_res.provider}, llm_mode={cls_res.mode}, model={cls_res.model}, "
            f"llm={cls_res.latency_ms}ms)"
        )
        print(f"Expected (US3) : {expected_label}")
        print("-" * 80)

    report = {
        "prompt_text_ta": PROMPT_TEXT_TA,
        "prompt_wav": str(prompt_wav_path.relative_to(API_ROOT).as_posix()),
        "tts_mode": tts_res.mode,
        "tts_latency_ms": tts_res.latency_ms,
        "source_label": "Simulated reply",
        "results": results,
    }
    report_path = RUNS_DIR / "sarvam_spike.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved spike results to {report_path}")


if __name__ == "__main__":
    main()
