"""External service integrations (Open-Meteo, Sarvam AI, Gemini LLM, Replay)."""

from app.integrations.llm import (
    CauseLabel,
    ClassificationPayload,
    ClassificationResult,
    classify_reply,
)
from app.integrations.replay import IntegrationMode
from app.integrations.sarvam import (
    DEFAULT_KEYTERMS,
    STTResult,
    TTSResult,
    contains_tamil_script,
    synthesize_tamil,
    transcribe_tamil,
)
from app.integrations.weather import (
    WeatherDayResult,
    WeatherRangeResult,
    WeatherUnavailableError,
    fetch_daily_rain_range,
    get_daily_rain_mm,
)

__all__ = [
    "DEFAULT_KEYTERMS",
    "CauseLabel",
    "ClassificationPayload",
    "ClassificationResult",
    "IntegrationMode",
    "STTResult",
    "TTSResult",
    "WeatherDayResult",
    "WeatherRangeResult",
    "WeatherUnavailableError",
    "classify_reply",
    "contains_tamil_script",
    "fetch_daily_rain_range",
    "get_daily_rain_mm",
    "synthesize_tamil",
    "transcribe_tamil",
]
