"""LangGraph node implementations and runtime container for Silent Claim."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.state import ClaimState
from app.config import Settings, is_offline
from app.db import DatabaseManager
from app.detector.baseline import (
    DailyIncome,
    ShopHistory,
    compute_baseline_paise,
    count_trading_days_before,
    get_day_income_paise,
)
from app.detector.config import PLAN_FEE_PAISE, RULES_VERSION
from app.detector.rules import (
    DecisionOutcome,
    check_payout_cap,
    compute_street_quorum,
    decide,
    is_day_dropped,
    is_eligible_before_event,
)
from app.events import EventBus, IntegrationHealthTracker
from app.evidence.pdf import EvidencePackData, build_evidence_pdf
from app.integrations.llm import CauseLabel, classify_reply, summarize_evidence
from app.integrations.paytm import (
    PENDING_DUMMY_KEY,
    PENDING_DUMMY_MID,
    PENDING_SIMULATED_LABEL,
    PaytmClient,
    PaytmUnavailableError,
    build_refund_id,
    build_refund_request,
    redact_paytm_payload,
)
from app.integrations.replay import tts_cache_path
from app.integrations.sarvam import (
    SarvamUnavailableError,
    synthesize_tamil,
    transcribe_tamil,
)
from app.integrations.weather import (
    WeatherDayResult,
    WeatherUnavailableError,
    get_daily_rain_mm,
)
from app.models import (
    IST,
    Ask,
    AuditLog,
    Batch,
    Claim,
    Detection,
    PaymentHourly,
    Refund,
    Shop,
    Street,
    now_ist,
    to_ist,
)

logger = logging.getLogger(__name__)


def build_consent_prompt_ta(quorum_dropped: int, quorum_total: int) -> str:
    """Build the canonical US2 Tamil consent prompt for flood-quorum claims."""
    return (
        f"மழையால் உங்கள் தெருவில் {quorum_total} கடைகளில் {quorum_dropped} மூடியிருந்தன. "
        "உங்கள் காப்பீட்டுக் கோரிக்கையை நான் பதிவு செய்யட்டுமா?"
    )


def build_voice_prompt_ta(reason: str) -> str:
    """Build a short Tamil voice-clarification prompt for non-auto-filed asks."""
    if reason == "inactive_before_event":
        return (
            "உங்கள் கடை கடந்த சில நாட்களாக குறைந்த வருமானத்தில் இருந்தது. "
            "இன்று கடை ஏன் மூடியிருந்தது என்று குரல் பதிவில் சொல்லுங்கள்."
        )
    return (
        "இன்று உங்கள் கடையில் Paytm பரிவர்த்தனைகள் குறைந்துள்ளன. "
        "கடை மூடப்பட்டதற்கான காரணத்தை குரல் பதிவில் சொல்லுங்கள்."
    )


@dataclass
class AgentRuntime:
    """Shared runtime dependencies injected into LangGraph nodes and API routes."""

    db: DatabaseManager
    bus: EventBus
    health: IntegrationHealthTracker
    settings_getter: Callable[[], Settings]
    fixtures_dir: Any
    runs_dir: Any
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _rain_cache: dict[tuple[str, float, float], WeatherDayResult] = field(default_factory=dict)
    _voice_blobs: dict[str, tuple[bytes, str, str]] = field(default_factory=dict)

    def clear_run_caches(self) -> None:
        """Clear transient per-run weather cache and pending voice blobs."""
        with self._lock:
            self._rain_cache.clear()
            self._voice_blobs.clear()

    def put_voice_blob(
        self, ask_id: str, audio_bytes: bytes, filename: str, content_type: str
    ) -> None:
        """Temporarily hold an uploaded/simulated voice note in RAM until classify() reads it."""
        with self._lock:
            self._voice_blobs[ask_id] = (audio_bytes, filename, content_type)

    def pop_voice_blob(self, ask_id: str) -> tuple[bytes, str, str] | None:
        """Retrieve and discard pending voice audio for `ask_id`."""
        with self._lock:
            return self._voice_blobs.pop(ask_id, None)

    def get_weather_for_day(self, day_val: date, lat: float, lon: float) -> WeatherDayResult:
        """Fetch daily precipitation once per street-day (with replay fallback inside weather.py)."""
        key = (day_val.isoformat(), round(lat, 2), round(lon, 2))
        with self._lock:
            cached = self._rain_cache.get(key)
        if cached is not None:
            return cached

        cfg = self.settings_getter()
        res = get_daily_rain_mm(
            day_val,
            lat=lat,
            lon=lon,
            settings=cfg,
            fixtures_dir=self.fixtures_dir,
            health_callback=self.health.make_callback(),
        )
        with self._lock:
            self._rain_cache[key] = res
        return res


def load_street_histories(
    session: Session,
    street_id: str,
    up_to_day: date,
) -> dict[str, ShopHistory]:
    """Load full calendar-day payment totals from `payments_hourly` up to `up_to_day` inclusive."""
    shop_ids = list(
        session.scalars(select(Shop.id).where(Shop.street_id == street_id).order_by(Shop.id))
    )
    end_exclusive = datetime(
        up_to_day.year,
        up_to_day.month,
        up_to_day.day,
        tzinfo=IST,
    ) + timedelta(days=1)

    stmt = (
        select(
            PaymentHourly.shop_id,
            PaymentHourly.ts_hour,
            PaymentHourly.n_payments,
            PaymentHourly.amount_paise,
        )
        .where(PaymentHourly.shop_id.in_(shop_ids), PaymentHourly.ts_hour < end_exclusive)
        .order_by(PaymentHourly.shop_id, PaymentHourly.ts_hour)
    )
    daily_totals: dict[str, dict[date, tuple[int, int]]] = {sid: {} for sid in shop_ids}
    for sid, ts_hour, n_pay, amt in session.execute(stmt):
        day_key = to_ist(ts_hour).date()
        prev_amt, prev_cnt = daily_totals[sid].get(day_key, (0, 0))
        daily_totals[sid][day_key] = (prev_amt + int(amt), prev_cnt + int(n_pay))

    histories: dict[str, ShopHistory] = {}
    for sid in shop_ids:
        days = tuple(
            DailyIncome(day=d, amount_paise=amt, n_payments=cnt)
            for d, (amt, cnt) in sorted(daily_totals[sid].items())
        )
        histories[sid] = ShopHistory(shop_id=sid, days=days)
    return histories


def build_nodes(runtime: AgentRuntime) -> dict[str, Callable[[ClaimState], dict[str, Any]]]:
    """Create bound LangGraph node functions sharing `runtime`."""

    def sense(state: ClaimState) -> dict[str, Any]:
        day_val = date.fromisoformat(state.day)
        runtime.bus.publish(
            "agent.step",
            {
                "node": "sense",
                "status": "start",
                "detail": f"Checking 28-day baseline and daily total for {state.shop_id}",
                "live": True,
            },
        )
        with runtime.db.session() as sess:
            histories = load_street_histories(sess, state.street_id, day_val)

        shop_hist = histories[state.shop_id]
        baseline_paise = compute_baseline_paise(shop_hist, day_val)
        day_income_paise = get_day_income_paise(shop_hist, day_val)
        trading_days_count = count_trading_days_before(shop_hist, day_val)
        dropped = is_day_dropped(day_income_paise, baseline_paise)

        runtime.bus.publish(
            "agent.step",
            {
                "node": "sense",
                "status": "ok",
                "detail": (
                    f"{state.shop_id} income={day_income_paise}p baseline={baseline_paise}p "
                    f"dropped={dropped}"
                ),
                "live": True,
            },
        )
        return {
            "detection": {
                "shop_id": state.shop_id,
                "day": state.day,
                "baseline_paise": baseline_paise,
                "day_income_paise": day_income_paise,
                "trading_days_count": trading_days_count,
                "dropped": dropped,
            },
            "trace": [*state.trace, "sense"],
        }

    def confirm(state: ClaimState) -> dict[str, Any]:
        cfg = runtime.settings_getter()
        offline = is_offline(cfg)
        day_val = date.fromisoformat(state.day)

        runtime.bus.publish(
            "agent.step",
            {
                "node": "confirm",
                "status": "start",
                "detail": f"Evaluating quorum, eligibility, and rainfall for {state.shop_id}",
                "live": not offline,
            },
        )

        with runtime.db.session() as sess:
            street = sess.get(Street, state.street_id)
            lat = street.lat if street is not None else cfg.weather_lat
            lon = street.lon if street is not None else cfg.weather_lon
            histories = load_street_histories(sess, state.street_id, day_val)

        shop_hist = histories[state.shop_id]
        quorum_share, quorum_dropped, quorum_total = compute_street_quorum(histories, day_val)
        errors = list(state.errors)
        rain_failed = False

        try:
            weather_res = runtime.get_weather_for_day(day_val, lat, lon)
            rain_mm = weather_res.rain_mm
            rain_source = weather_res.source
            weather_live = weather_res.live
            decision_res = decide(
                shop=state.shop_id,
                day=day_val,
                street=histories,
                rain={day_val: rain_mm},
            )
            decision_str = decision_res.decision.value
            reason_str = decision_res.reason.value
            baseline_paise = decision_res.baseline_paise
            day_income_paise = decision_res.day_income_paise
            dropped = decision_res.dropped
            eligible = decision_res.eligible
            quorum_share_val = decision_res.quorum_share
            rules_ver = decision_res.rules_version
        except WeatherUnavailableError:
            rain_failed = True
            rain_mm = 0.0
            rain_source = "Open-Meteo unavailable"
            weather_live = False
            baseline_paise = compute_baseline_paise(shop_hist, day_val)
            day_income_paise = get_day_income_paise(shop_hist, day_val)
            dropped = is_day_dropped(day_income_paise, baseline_paise)
            eligible = is_eligible_before_event(shop_hist, day_val, baseline_paise=baseline_paise)
            quorum_share_val = quorum_share
            decision_str = DecisionOutcome.ASK.value if dropped else DecisionOutcome.NONE.value
            reason_str = "rain_unavailable" if dropped else "not_dropped"
            rules_ver = RULES_VERSION
            errors.append("rain_unavailable")

        detection_id = f"det_{state.day.replace('-', '')}_{state.shop_id}"
        with runtime.db.session() as sess:
            existing_det = sess.get(Detection, detection_id)
            if existing_det is None:
                det_row = Detection(
                    id=detection_id,
                    shop_id=state.shop_id,
                    day=day_val,
                    baseline_paise=baseline_paise,
                    day_income_paise=day_income_paise,
                    dropped=dropped,
                    eligible=eligible,
                    quorum_share=quorum_share_val,
                    rain_mm=rain_mm,
                    rain_source=rain_source,
                    decision=decision_str,
                    reason=reason_str,
                    rules_version=rules_ver,
                )
                sess.add(det_row)
            else:
                existing_det.baseline_paise = baseline_paise
                existing_det.day_income_paise = day_income_paise
                existing_det.dropped = dropped
                existing_det.eligible = eligible
                existing_det.quorum_share = quorum_share_val
                existing_det.rain_mm = rain_mm
                existing_det.rain_source = rain_source
                existing_det.decision = decision_str
                existing_det.reason = reason_str
                existing_det.rules_version = rules_ver

            sess.add(
                AuditLog(
                    actor="agent",
                    action="detector.decision",
                    payload={
                        "detection_id": detection_id,
                        "shop_id": state.shop_id,
                        "day": state.day,
                        "decision": decision_str,
                        "reason": reason_str,
                        "quorum_share": round(quorum_share_val, 4),
                        "rain_mm": round(rain_mm, 2),
                    },
                )
            )

        shop_status = "dropped" if dropped else "trading"
        runtime.bus.publish("shop.status", {"shop_id": state.shop_id, "status": shop_status})
        runtime.bus.publish(
            "detector.decision",
            {
                "shop_id": state.shop_id,
                "decision": decision_str,
                "reason": reason_str,
                "quorum_share": round(quorum_share_val, 4),
                "rain_mm": round(rain_mm, 2),
                "live": weather_live,
                "replay": offline or not weather_live,
            },
        )
        runtime.bus.publish(
            "agent.step",
            {
                "node": "confirm",
                "status": "error" if rain_failed else "ok",
                "detail": (
                    f"{state.shop_id} -> {decision_str} ({reason_str}), "
                    f"quorum={quorum_dropped}/{quorum_total}, rain={rain_mm:.1f}mm"
                ),
                "live": weather_live,
            },
        )

        return {
            "detection": {
                **state.detection,
                "detection_id": detection_id,
                "baseline_paise": baseline_paise,
                "day_income_paise": day_income_paise,
                "dropped": dropped,
                "eligible": eligible,
                "quorum_share": quorum_share_val,
                "quorum_dropped": quorum_dropped,
                "quorum_total": quorum_total,
                "rain_mm": rain_mm,
                "rain_source": rain_source,
                "decision": decision_str,
                "reason": reason_str,
                "rules_version": rules_ver,
            },
            "errors": errors,
            "live_flags": {**state.live_flags, "weather": weather_live},
            "trace": [*state.trace, "confirm"],
            "terminal_status": "none" if decision_str == DecisionOutcome.NONE.value else "",
        }

    def ask(state: ClaimState) -> dict[str, Any]:
        cfg = runtime.settings_getter()
        offline = is_offline(cfg)
        det = state.detection
        detection_id = str(det["detection_id"])
        decision_str = str(det["decision"])
        reason_str = str(det["reason"])
        quorum_dropped = int(det.get("quorum_dropped", 0))
        quorum_total = int(det.get("quorum_total", 12))

        with runtime.db.session() as sess:
            existing_ask = sess.scalar(select(Ask).where(Ask.detection_id == detection_id))
            if existing_ask is not None:
                ask_id = existing_ask.id
                ask_kind = existing_ask.ask_kind
                prompt_text_ta = existing_ask.prompt_text_ta
                prompt_audio_path = existing_ask.prompt_audio_path
                thread_id = existing_ask.thread_id
                tts_live = bool(state.live_flags.get("tts", False))
                created_new = False
            else:
                created_new = True
                ask_kind = "consent" if decision_str == DecisionOutcome.FILE.value else "voice"
                prompt_text_ta = (
                    build_consent_prompt_ta(quorum_dropped, quorum_total)
                    if ask_kind == "consent"
                    else build_voice_prompt_ta(reason_str)
                )
                ask_id = f"ask_{state.day.replace('-', '')}_{state.shop_id}_{uuid.uuid4().hex[:6]}"
                thread_id = f"thr_{ask_id}"

        errors = list(state.errors)
        if created_new:
            runtime.bus.publish(
                "agent.step",
                {
                    "node": "ask",
                    "status": "start",
                    "detail": f"Sending Tamil {ask_kind} ask to {state.shop_id}",
                    "live": not offline,
                },
            )
            prompt_audio_path = None
            tts_live = False
            tts_cache_dir = runtime.runs_dir / "tts_cache"
            try:
                tts_res = synthesize_tamil(
                    prompt_text_ta,
                    settings=cfg,
                    fixtures_dir=runtime.fixtures_dir,
                    cache_dir=tts_cache_dir,
                    health_callback=runtime.health.make_callback(ignore_down_when_offline=True),
                )
                if tts_res.audio_path is not None:
                    prompt_audio_path = str(tts_res.audio_path)
                elif tts_res.audio_bytes:
                    cached_wav = tts_cache_path(prompt_text_ta, cache_dir=tts_cache_dir)
                    cached_wav.parent.mkdir(parents=True, exist_ok=True)
                    cached_wav.write_bytes(tts_res.audio_bytes)
                    prompt_audio_path = str(cached_wav)
                tts_live = tts_res.live
            except SarvamUnavailableError:
                errors.append("tts_text_only_fallback")

            with runtime.db.session() as sess:
                ask_row = Ask(
                    id=ask_id,
                    detection_id=detection_id,
                    shop_id=state.shop_id,
                    thread_id=thread_id,
                    ask_kind=ask_kind,
                    prompt_text_ta=prompt_text_ta,
                    prompt_audio_path=prompt_audio_path,
                    status="pending",
                )
                sess.add(ask_row)
                sess.add(
                    AuditLog(
                        actor="agent",
                        action="ask.sent",
                        payload={
                            "ask_id": ask_id,
                            "shop_id": state.shop_id,
                            "ask_kind": ask_kind,
                            "has_audio": prompt_audio_path is not None,
                        },
                    )
                )

            runtime.bus.publish(
                "agent.step",
                {
                    "node": "ask",
                    "status": "ok",
                    "detail": f"Waiting on {state.shop_id} ({ask_kind} ask {ask_id})",
                    "live": tts_live,
                },
            )
            runtime.bus.publish(
                "ask.sent",
                {
                    "ask_id": ask_id,
                    "shop_id": state.shop_id,
                    "ask_kind": ask_kind,
                    "live": tts_live,
                    "replay": not tts_live,
                },
            )

        # Pause thread until POST /api/asks/{id}/consent or /voice resumes via Command(resume=...).
        answer = interrupt(
            {
                "ask_id": ask_id,
                "shop_id": state.shop_id,
                "ask_kind": ask_kind,
                "prompt_text_ta": prompt_text_ta,
            }
        )

        reply_type = str(answer["reply_type"])
        answered_at_iso = str(answer.get("answered_at") or now_ist().isoformat())
        answered_at_dt = to_ist(datetime.fromisoformat(answered_at_iso))
        simulated_label = answer.get("simulated_label")

        if reply_type == "tap":
            with runtime.db.session() as sess:
                ask_obj = sess.get(Ask, ask_id)
                if ask_obj is not None:
                    ask_obj.reply_type = "tap"
                    ask_obj.status = "answered"
                    ask_obj.answered_at = answered_at_dt
                    ask_obj.simulated_label = simulated_label
                sess.add(
                    AuditLog(
                        actor="merchant",
                        action="ask.consent",
                        payload={
                            "ask_id": ask_id,
                            "shop_id": state.shop_id,
                            "simulated_label": simulated_label,
                        },
                    )
                )

            runtime.bus.publish(
                "ask.answered",
                {
                    "ask_id": ask_id,
                    "reply_type": "tap",
                    "simulated_label": simulated_label,
                    "live": simulated_label is None,
                    "replay": simulated_label is not None,
                },
            )
            return {
                "ask": {
                    "ask_id": ask_id,
                    "thread_id": thread_id,
                    "ask_kind": ask_kind,
                    "prompt_text_ta": prompt_text_ta,
                    "prompt_audio_path": prompt_audio_path,
                    "reply_type": "tap",
                    "simulated_label": simulated_label,
                    "answered_at": answered_at_dt.isoformat(),
                },
                "errors": errors,
                "live_flags": {**state.live_flags, "tts": tts_live},
                "trace": [*state.trace, "ask"],
            }

        if reply_type == "decline":
            with runtime.db.session() as sess:
                ask_obj = sess.get(Ask, ask_id)
                if ask_obj is not None:
                    ask_obj.reply_type = "decline"
                    ask_obj.status = "declined"
                    ask_obj.answered_at = answered_at_dt
                    ask_obj.simulated_label = simulated_label
                sess.add(
                    AuditLog(
                        actor="merchant",
                        action="consent declined",
                        payload={
                            "ask_id": ask_id,
                            "shop_id": state.shop_id,
                            "simulated_label": simulated_label,
                        },
                    )
                )

            runtime.bus.publish(
                "ask.answered",
                {
                    "ask_id": ask_id,
                    "reply_type": "decline",
                    "simulated_label": simulated_label,
                    "live": simulated_label is None,
                    "replay": simulated_label is not None,
                },
            )
            return {
                "ask": {
                    "ask_id": ask_id,
                    "thread_id": thread_id,
                    "ask_kind": ask_kind,
                    "prompt_text_ta": prompt_text_ta,
                    "prompt_audio_path": prompt_audio_path,
                    "reply_type": "decline",
                    "cause_label": "consent_declined",
                    "simulated_label": simulated_label,
                    "answered_at": answered_at_dt.isoformat(),
                },
                "errors": errors,
                "live_flags": {**state.live_flags, "tts": tts_live},
                "trace": [*state.trace, "ask"],
            }

        return {
            "ask": {
                "ask_id": ask_id,
                "thread_id": thread_id,
                "ask_kind": ask_kind,
                "prompt_text_ta": prompt_text_ta,
                "prompt_audio_path": prompt_audio_path,
                "reply_type": "voice",
                "simulated_label": simulated_label,
                "answered_at": answered_at_dt.isoformat(),
            },
            "errors": errors,
            "live_flags": {**state.live_flags, "tts": tts_live},
            "trace": [*state.trace, "ask"],
        }

    def classify(state: ClaimState) -> dict[str, Any]:
        cfg = runtime.settings_getter()
        offline = is_offline(cfg)
        ask_info = dict(state.ask)
        ask_id = str(ask_info["ask_id"])
        simulated_label = ask_info.get("simulated_label")
        answered_at_iso = str(ask_info.get("answered_at") or now_ist().isoformat())
        answered_at_dt = to_ist(datetime.fromisoformat(answered_at_iso))
        errors = list(state.errors)

        runtime.bus.publish(
            "agent.step",
            {
                "node": "classify",
                "status": "start",
                "detail": f"Transcribing and classifying voice reply for {state.shop_id}",
                "live": not offline,
            },
        )

        blob = runtime.pop_voice_blob(ask_id)
        if blob is None:
            transcript = ""
            cause_label = CauseLabel.OTHER
            confidence = 0.0
            stt_live = False
            llm_live = False
            errors.append("missing_voice_payload")
        else:
            audio_bytes, filename, content_type = blob
            try:
                stt_res = transcribe_tamil(
                    audio_bytes,
                    filename=filename,
                    content_type=content_type,
                    settings=cfg,
                    fixtures_dir=runtime.fixtures_dir,
                    health_callback=runtime.health.make_callback(),
                )
                transcript = stt_res.transcript
                stt_live = stt_res.live
                cls_res = classify_reply(
                    transcript,
                    settings=cfg,
                    fixtures_dir=runtime.fixtures_dir,
                    health_callback=runtime.health.make_callback(),
                )
                cause_label = cls_res.cause_label
                confidence = cls_res.confidence
                llm_live = cls_res.live
            except SarvamUnavailableError:
                transcript = ""
                cause_label = CauseLabel.OTHER
                confidence = 0.0
                stt_live = False
                llm_live = False
                errors.append("stt_unavailable")

        with runtime.db.session() as sess:
            ask_obj = sess.get(Ask, ask_id)
            if ask_obj is not None:
                ask_obj.reply_type = "voice"
                ask_obj.transcript = transcript
                ask_obj.cause_label = cause_label.value
                ask_obj.confidence = confidence
                ask_obj.simulated_label = simulated_label
                ask_obj.status = "answered"
                ask_obj.answered_at = answered_at_dt
            sess.add(
                AuditLog(
                    actor="merchant",
                    action="ask.voice",
                    payload={
                        "ask_id": ask_id,
                        "shop_id": state.shop_id,
                        "cause_label": cause_label.value,
                        "confidence": round(confidence, 4),
                        "simulated_label": simulated_label,
                    },
                )
            )

        classify_live = stt_live and llm_live and simulated_label is None
        runtime.bus.publish(
            "ask.answered",
            {
                "ask_id": ask_id,
                "reply_type": "voice",
                "cause_label": cause_label.value,
                "simulated_label": simulated_label,
                "live": classify_live,
                "replay": offline or not (stt_live and llm_live),
            },
        )
        runtime.bus.publish(
            "agent.step",
            {
                "node": "classify",
                "status": "ok" if "stt_unavailable" not in errors else "error",
                "detail": f"{state.shop_id} classified as {cause_label.value} ({confidence:.2f})",
                "live": stt_live or llm_live,
            },
        )

        return {
            "ask": {
                **ask_info,
                "transcript": transcript,
                "cause_label": cause_label.value,
                "confidence": confidence,
            },
            "errors": errors,
            "live_flags": {**state.live_flags, "stt": stt_live, "llm": llm_live},
            "trace": [*state.trace, "classify"],
        }

    def file_claim(state: ClaimState) -> dict[str, Any]:
        cfg = runtime.settings_getter()
        det = state.detection
        ask_info = state.ask
        detection_id = str(det["detection_id"])
        day_val = date.fromisoformat(state.day)

        with runtime.db.session() as sess:
            existing_claim = sess.scalar(select(Claim).where(Claim.detection_id == detection_id))
            if existing_claim is not None:
                return {
                    "claim": {
                        "claim_id": existing_claim.id,
                        "status": existing_claim.status,
                        "evidence_pdf_path": existing_claim.evidence_pdf_path,
                    },
                    "trace": [*state.trace, "file"],
                    "terminal_status": "filed",
                }

            shop = sess.get(Shop, state.shop_id)
            street = sess.get(Street, state.street_id)
            ask_obj = sess.get(Ask, ask_info["ask_id"]) if ask_info.get("ask_id") else None
            histories = load_street_histories(sess, state.street_id, day_val)

            shop_hist = histories[state.shop_id]
            recent_days = tuple(
                (r.day.isoformat(), r.n_payments, r.amount_paise) for r in shop_hist.days[-7:]
            )

            shop_name = shop.name if shop is not None else state.shop_id
            owner = shop.owner if shop is not None else state.shop_id
            category = shop.category if shop is not None else "retail"
            street_name = street.name if street is not None else "Panagal Park Road (simulated)"

            claim_id = f"clm_{state.day.replace('-', '')}_{state.shop_id}_{uuid.uuid4().hex[:6]}"
            consent_dt = ask_obj.answered_at if ask_obj is not None else now_ist()
            simulated_label = ask_obj.simulated_label if ask_obj is not None else None
            cause_label = ask_obj.cause_label if ask_obj is not None else None

        runtime.bus.publish(
            "agent.step",
            {
                "claim_id": claim_id,
                "node": "file",
                "status": "start",
                "detail": f"Generating evidence PDF and filing claim {claim_id}",
                "live": True,
            },
        )

        summary_text = summarize_evidence(
            shop_name=shop_name,
            owner=owner,
            day_iso=state.day,
            baseline_paise=int(det["baseline_paise"]),
            day_income_paise=int(det["day_income_paise"]),
            quorum_dropped=int(det.get("quorum_dropped", 0)),
            quorum_total=int(det.get("quorum_total", 12)),
            rain_mm=float(det["rain_mm"]),
            rain_source=str(det["rain_source"]),
            cause_label=cause_label,
            settings=cfg,
        )

        pdf_path = runtime.runs_dir / "evidence" / f"{claim_id}.pdf"
        build_evidence_pdf(
            EvidencePackData(
                claim_id=claim_id,
                shop_id=state.shop_id,
                shop_name=shop_name,
                owner=owner,
                category=category,
                street_name=street_name,
                day_iso=state.day,
                baseline_paise=int(det["baseline_paise"]),
                day_income_paise=int(det["day_income_paise"]),
                quorum_dropped=int(det.get("quorum_dropped", 0)),
                quorum_total=int(det.get("quorum_total", 12)),
                quorum_share=float(det["quorum_share"]),
                rain_mm=float(det["rain_mm"]),
                rain_source=str(det["rain_source"]),
                consent_at=consent_dt,
                rules_version=str(det.get("rules_version", RULES_VERSION)),
                decision_reason=str(det["reason"]),
                simulated_label=simulated_label,
                cause_label=cause_label,
                summary_text=summary_text,
                recent_days=recent_days,
            ),
            pdf_path,
        )

        new_batch_id: str | None = None
        batch_claim_count: int = 0
        claim_batch_id: str | None = None

        with runtime.db.session() as sess:
            claim_row = Claim(
                id=claim_id,
                shop_id=state.shop_id,
                detection_id=detection_id,
                status="filed",
                summary_text=summary_text,
                consent_at=consent_dt,
                evidence_pdf_path=str(pdf_path),
                batch_id=None,
            )
            sess.add(claim_row)
            if ask_info.get("ask_id"):
                ask_row = sess.get(Ask, ask_info["ask_id"])
                if ask_row is not None:
                    ask_row.status = "filed"
            sess.add(
                AuditLog(
                    actor="agent",
                    action="claim.filed",
                    payload={
                        "claim_id": claim_id,
                        "shop_id": state.shop_id,
                        "detection_id": detection_id,
                        "simulated_label": simulated_label,
                    },
                )
            )
            sess.flush()
            new_batch_id, batch_claim_count = maybe_open_batch_for_day(
                sess=sess,
                day_val=day_val,
                day_iso=state.day,
                latest_claim=claim_row,
            )
            claim_batch_id = claim_row.batch_id

        runtime.bus.publish(
            "agent.step",
            {
                "claim_id": claim_id,
                "node": "file",
                "status": "ok",
                "detail": f"Filed claim {claim_id} for {shop_name}",
                "live": True,
            },
        )
        runtime.bus.publish(
            "claim.filed",
            {
                "claim_id": claim_id,
                "shop_id": state.shop_id,
                "batch_id": claim_batch_id,
                "simulated_label": simulated_label,
                "live": simulated_label is None,
                "replay": is_offline(cfg),
            },
        )
        if new_batch_id is not None:
            runtime.bus.publish(
                "batch.ready",
                {
                    "batch_id": new_batch_id,
                    "n": batch_claim_count,
                    "live": True,
                    "replay": is_offline(cfg),
                },
            )
            runtime.bus.publish(
                "agent.step",
                {
                    "node": "batch",
                    "status": "ok",
                    "detail": f"Batch {new_batch_id} ready ({batch_claim_count} claims)",
                    "live": True,
                },
            )
        return {
            "claim": {
                "claim_id": claim_id,
                "status": "filed",
                "batch_id": claim_batch_id,
                "evidence_pdf_path": str(pdf_path),
                "consent_at": consent_dt.isoformat() if consent_dt is not None else None,
            },
            "trace": [*state.trace, "file"],
            "terminal_status": "filed",
        }

    def close_ask(state: ClaimState) -> dict[str, Any]:
        cfg = runtime.settings_getter()
        ask_id = str(state.ask["ask_id"])
        reply_type = str(state.ask.get("reply_type") or "")
        ask_kind = str(state.ask.get("ask_kind") or "")
        cause_label = str(state.ask.get("cause_label") or "leave")
        day_val = date.fromisoformat(state.day)
        new_batch_id: str | None = None
        batch_claim_count: int = 0

        with runtime.db.session() as sess:
            ask_row = sess.get(Ask, ask_id)
            if ask_row is not None and reply_type != "decline":
                ask_row.status = "closed"
            sess.add(
                AuditLog(
                    actor="agent",
                    action="ask.closed",
                    payload={
                        "ask_id": ask_id,
                        "shop_id": state.shop_id,
                        "cause_label": cause_label,
                    },
                )
            )
            sess.flush()
            if ask_kind == "consent":
                new_batch_id, batch_claim_count = maybe_open_batch_for_day(
                    sess=sess,
                    day_val=day_val,
                    day_iso=state.day,
                    latest_claim=None,
                )

        runtime.bus.publish(
            "agent.step",
            {
                "node": "close",
                "status": "ok",
                "detail": f"Closed without filing claim ({cause_label}) for {state.shop_id}",
                "live": bool(state.live_flags.get("llm", False)),
            },
        )
        if new_batch_id is not None:
            runtime.bus.publish(
                "batch.ready",
                {
                    "batch_id": new_batch_id,
                    "n": batch_claim_count,
                    "live": True,
                    "replay": is_offline(cfg),
                },
            )
            runtime.bus.publish(
                "agent.step",
                {
                    "node": "batch",
                    "status": "ok",
                    "detail": f"Batch {new_batch_id} ready ({batch_claim_count} claims)",
                    "live": True,
                },
            )
        return {
            "trace": [*state.trace, "close"],
            "terminal_status": "declined" if reply_type == "decline" else "closed",
        }

    def human_review(state: ClaimState) -> dict[str, Any]:
        ask_id = str(state.ask["ask_id"])
        cause_label = str(state.ask.get("cause_label") or "other")
        with runtime.db.session() as sess:
            ask_row = sess.get(Ask, ask_id)
            if ask_row is not None:
                ask_row.status = "human_review"
            sess.add(
                AuditLog(
                    actor="agent",
                    action="ask.human_review",
                    payload={
                        "ask_id": ask_id,
                        "shop_id": state.shop_id,
                        "cause_label": cause_label,
                    },
                )
            )
        runtime.bus.publish(
            "agent.step",
            {
                "node": "human_review",
                "status": "ok",
                "detail": f"Queued {state.shop_id} for human review ({cause_label})",
                "live": bool(state.live_flags.get("llm", False)),
            },
        )
        return {
            "trace": [*state.trace, "human_review"],
            "terminal_status": "human_review",
        }

    return {
        "sense": sense,
        "confirm": confirm,
        "ask": ask,
        "classify": classify,
        "file": file_claim,
        "close": close_ask,
        "human_review": human_review,
    }


def _route_after_confirm(state: ClaimState) -> str:
    if state.detection.get("decision") == DecisionOutcome.NONE.value:
        return "end"
    return "ask"


def _route_after_ask(state: ClaimState) -> str:
    reply_type = state.ask.get("reply_type")
    if reply_type == "tap":
        return "file"
    if reply_type == "decline":
        return "close"
    return "classify"


def _route_after_classify(state: ClaimState) -> str:
    label = str(state.ask.get("cause_label") or CauseLabel.OTHER.value)
    if label == CauseLabel.FLOOD_CLOSURE.value:
        return "file"
    if label == CauseLabel.LEAVE.value:
        return "close"
    return "human_review"


def daily_shop_totals_map(
    session: Session,
    street_id: str,
    day_val: date,
) -> dict[str, tuple[int, int]]:
    """Compute {shop_id: (n_payments, amount_paise)} on `day_val` for display/reporting."""
    histories = load_street_histories(session, street_id, day_val)
    out: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    for sid, hist in histories.items():
        for rec in hist.days:
            if rec.day == day_val:
                out[sid] = (rec.n_payments, rec.amount_paise)
                break
    return dict(out)


def maybe_open_batch_for_day(
    sess: Session,
    day_val: date,
    day_iso: str,
    latest_claim: Claim | None = None,
) -> tuple[str | None, int]:
    """Attach claim to an open batch, or open a new batch once all consent asks are answered."""
    det_rows = list(sess.scalars(select(Detection).where(Detection.day == day_val)))
    if not det_rows:
        return None, 0

    all_det_ids = [d.id for d in det_rows]
    file_det_ids = [d.id for d in det_rows if d.decision == DecisionOutcome.FILE.value]

    open_batch = sess.scalar(
        select(Batch).where(Batch.status == "open").order_by(Batch.created_at.desc())
    )
    if open_batch is not None:
        if latest_claim is not None and latest_claim.batch_id is None:
            latest_claim.batch_id = open_batch.id
        return None, 0

    asks_for_day = list(sess.scalars(select(Ask).where(Ask.detection_id.in_(all_det_ids))))
    consent_asks = [a for a in asks_for_day if a.ask_kind == "consent"]
    pending_consent = [a for a in consent_asks if a.status == "pending"]

    if not consent_asks or len(consent_asks) < len(file_det_ids) or pending_consent:
        return None, 0

    claims_for_day = list(
        sess.scalars(
            select(Claim).where(Claim.detection_id.in_(all_det_ids)).order_by(Claim.shop_id)
        )
    )
    if not claims_for_day:
        return None, 0

    base_batch_id = f"batch_{day_iso.replace('-', '')}"
    batch_id = (
        base_batch_id
        if sess.get(Batch, base_batch_id) is None
        else f"{base_batch_id}_{uuid.uuid4().hex[:4]}"
    )
    batch_row = Batch(id=batch_id, status="open")
    sess.add(batch_row)
    sess.flush()

    attached_ids: list[str] = []
    for c in claims_for_day:
        if c.batch_id is None:
            c.batch_id = batch_id
        if c.batch_id == batch_id:
            attached_ids.append(c.id)

    sess.add(
        AuditLog(
            actor="agent",
            action="batch.ready",
            payload={
                "batch_id": batch_id,
                "n": len(attached_ids),
                "claim_ids": attached_ids,
            },
        )
    )
    return batch_id, len(attached_ids)


def _month_str_to_date(month_str: str, fallback: date) -> date:
    """Convert 'YYYY-MM' into a representative date in that calendar month."""
    try:
        year_s, month_s = month_str.split("-", 1)
        return date(int(year_s), int(month_s), 1)
    except (ValueError, TypeError):
        return fallback


async def execute_claim_payback(
    runtime: AgentRuntime,
    claim_id: str,
) -> dict[str, Any]:
    """Execute the deterministic Rs 35 plan-fee payback for one approved claim."""
    cfg = runtime.settings_getter()
    refund_id = build_refund_id(claim_id)

    if not cfg.payback_enabled:
        with runtime.db.session() as sess:
            claim_row = sess.get(Claim, claim_id)
            if claim_row is not None:
                claim_row.status = "Refunds paused"
        return {
            "claim_id": claim_id,
            "refund_id": refund_id,
            "amount_paise": 0,
            "status": "Refunds paused",
            "label": "Refunds paused",
            "live": False,
            "replay": is_offline(cfg),
        }

    with runtime.db.session() as sess:
        existing_refund = sess.scalar(
            select(Refund).where((Refund.refund_id == refund_id) | (Refund.claim_id == claim_id))
        )
        if existing_refund is not None:
            return {
                "claim_id": existing_refund.claim_id,
                "shop_id": existing_refund.shop_id,
                "refund_id": existing_refund.refund_id,
                "amount_paise": existing_refund.amount_paise,
                "status": existing_refund.status,
                "label": existing_refund.mode_label,
                "live": existing_refund.mode_label == "Live",
                "replay": is_offline(cfg),
                "idempotent": True,
            }

        claim_row = sess.get(Claim, claim_id)
        if claim_row is None:
            raise ValueError(f"Claim '{claim_id}' not found")

        shop_id = claim_row.shop_id
        det_row = sess.get(Detection, claim_row.detection_id)
        day_val = det_row.day if det_row is not None else now_ist().date()
        refund_month = day_val.strftime("%Y-%m")
        shop_row = sess.get(Shop, shop_id)
        staging_order_id = (shop_row.staging_order_id or "").strip() if shop_row is not None else ""
        if not staging_order_id and shop_id == "shop_01":
            staging_order_id = (cfg.paytm_demo_order_id or "").strip()

        prior_refunds = list(
            sess.scalars(
                select(Refund).where(
                    Refund.shop_id == shop_id,
                    Refund.refund_month == refund_month,
                    Refund.status != "refund_failed",
                )
            )
        )
        existing_dates = [_month_str_to_date(r.refund_month, day_val) for r in prior_refunds]
        cap_decision = check_payout_cap(shop_id, day_val, existing_dates)
        allowed = cap_decision.allowed
        cap_reason = cap_decision.reason
        if not allowed:
            claim_row.status = "monthly_cap_reached"
            sess.add(
                AuditLog(
                    actor="agent",
                    action="refund.skipped_cap",
                    payload={
                        "claim_id": claim_id,
                        "shop_id": shop_id,
                        "refund_month": refund_month,
                        "reason": cap_reason,
                    },
                )
            )

    if not allowed:
        runtime.bus.publish(
            "agent.step",
            {
                "claim_id": claim_id,
                "node": "payback",
                "status": "skipped",
                "detail": f"Skipped payback for {shop_id}: {cap_reason} ({refund_month})",
                "live": False,
            },
        )
        payload = {
            "claim_id": claim_id,
            "shop_id": shop_id,
            "refund_id": refund_id,
            "amount_paise": 0,
            "status": "monthly_cap_reached",
            "label": "Monthly cap reached",
            "live": False,
            "replay": is_offline(cfg),
        }
        runtime.bus.publish("refund.status", payload)
        return payload

    mode = cfg.paytm_mode.strip().lower()
    http_client: httpx.Client | None = getattr(runtime, "paytm_http_client", None)
    poll_interval_s = float(getattr(runtime, "refund_poll_interval_s", 1.0))
    secret_val = cfg.paytm_merchant_key.get_secret_value().strip()
    secrets_tuple = (secret_val,) if secret_val else ()
    health_cb = runtime.health.make_callback(ignore_down_when_offline=True)

    if mode == "pending":
        paytm_client = PaytmClient(settings=cfg, client=http_client)
        order_id = staging_order_id or f"ORD-PENDING-{shop_id.upper()}"
        txn_id = f"TXN-PENDING-{shop_id.upper()}"
        refund_res = paytm_client.refund_plan_fee(
            order_id=order_id,
            txn_id=txn_id,
            claim_id=claim_id,
        )
        status_res = paytm_client.get_refund_status(
            order_id=order_id,
            claim_id=claim_id,
        )
        refund_status = "SIMULATED"
        mode_label = PENDING_SIMULATED_LABEL
        claim_status = "paid_sim"
        live_call = False
        raw_payload = redact_paytm_payload(
            {
                "request": refund_res.redacted_request,
                "refund": refund_res.redacted_response,
                "refund_status": status_res.redacted_response,
            },
            secrets=secrets_tuple,
        )
        health_cb("paytm", "simulated")
    elif not staging_order_id:
        order_id = f"SIM-NO-ORDER-{shop_id.upper()}"
        mid = (cfg.paytm_mid or "").strip() or PENDING_DUMMY_MID
        key = secret_val or PENDING_DUMMY_KEY
        signed_req = build_refund_request(
            order_id=order_id,
            txn_id=f"SIM-TXN-{shop_id.upper()}",
            claim_id=claim_id,
            mid=mid,
            merchant_key=key,
        )
        refund_status = "SIMULATED"
        mode_label = "Simulated refund (no staging payment)"
        claim_status = "paid_sim"
        live_call = False
        raw_payload = redact_paytm_payload(
            {
                "request": signed_req.payload,
                "body": {
                    "resultInfo": {
                        "resultStatus": "SIMULATED",
                        "resultCode": "SIM_NO_STAGING_ORDER",
                        "resultMsg": mode_label,
                    },
                    "orderId": order_id,
                    "refId": refund_id,
                    "refundAmount": "35.00",
                },
            },
            secrets=secrets_tuple,
        )
    else:
        order_id = staging_order_id
        paytm_client = PaytmClient(settings=cfg, client=http_client)
        try:
            txn_status_res = paytm_client.get_transaction_status(order_id=order_id)
            txn_id = txn_status_res.txn_id or f"TXN-{order_id}"
            refund_res = paytm_client.refund_plan_fee(
                order_id=order_id,
                txn_id=txn_id,
                claim_id=claim_id,
            )
            status_res = None
            polls_taken = 0
            for attempt in range(3):
                polls_taken = attempt + 1
                status_res = paytm_client.get_refund_status(
                    order_id=order_id,
                    claim_id=claim_id,
                )
                st_upper = (status_res.status or "").upper()
                if st_upper not in {"PENDING", "TXN_PENDING", "INITIATED", "PROCESSING"}:
                    break
                if attempt < 2 and poll_interval_s > 0:
                    await asyncio.sleep(poll_interval_s)

            assert status_res is not None
            st_upper = (status_res.status or "").upper()
            live_call = not status_res.simulated
            if st_upper in {"TXN_SUCCESS", "SUCCESS"}:
                refund_status = "TXN_SUCCESS"
                mode_label = status_res.label
                claim_status = "approved"
            elif st_upper in {"PENDING", "TXN_PENDING", "INITIATED", "PROCESSING"}:
                refund_status = "Pending at Paytm"
                mode_label = "Pending at Paytm"
                claim_status = "approved"
            else:
                refund_status = "refund_failed"
                mode_label = status_res.label
                claim_status = "refund_failed"

            health_cb("paytm", "live" if live_call else "replay")
            raw_payload = redact_paytm_payload(
                {
                    "txn_status": txn_status_res.redacted_response,
                    "refund": refund_res.redacted_response,
                    "refund_status": status_res.redacted_response,
                    "polls": polls_taken,
                },
                secrets=secrets_tuple,
            )
        except (PaytmUnavailableError, httpx.HTTPError) as exc:
            logger.warning("Paytm staging refund failed for %s: %s", claim_id, exc)
            refund_status = "refund_failed"
            mode_label = "Paytm staging unavailable"
            claim_status = "refund_failed"
            live_call = False
            raw_payload = redact_paytm_payload(
                {
                    "error": str(exc),
                    "orderId": order_id,
                    "refId": refund_id,
                },
                secrets=secrets_tuple,
            )
            health_cb("paytm", "down")

    try:
        with runtime.db.session() as sess:
            existing_refund = sess.scalar(
                select(Refund).where(
                    (Refund.refund_id == refund_id) | (Refund.claim_id == claim_id)
                )
            )
            if existing_refund is not None:
                return {
                    "claim_id": existing_refund.claim_id,
                    "shop_id": existing_refund.shop_id,
                    "refund_id": existing_refund.refund_id,
                    "amount_paise": existing_refund.amount_paise,
                    "status": existing_refund.status,
                    "label": existing_refund.mode_label,
                    "live": existing_refund.mode_label == "Live",
                    "replay": is_offline(cfg),
                    "idempotent": True,
                }

            refund_row = Refund(
                id=f"rfd_{uuid.uuid4().hex[:10]}",
                claim_id=claim_id,
                shop_id=shop_id,
                refund_month=refund_month,
                paytm_order_id=order_id,
                refund_id=refund_id,
                amount_paise=PLAN_FEE_PAISE,
                status=refund_status,
                mode_label=mode_label,
                raw_response=redact_paytm_payload(raw_payload),
            )
            sess.add(refund_row)
            claim_row = sess.get(Claim, claim_id)
            if claim_row is not None:
                claim_row.status = claim_status
            sess.add(
                AuditLog(
                    actor="agent",
                    action="refund.processed",
                    payload={
                        "claim_id": claim_id,
                        "shop_id": shop_id,
                        "refund_id": refund_id,
                        "amount_paise": PLAN_FEE_PAISE,
                        "status": refund_status,
                        "label": mode_label,
                    },
                )
            )
    except IntegrityError:
        with runtime.db.session() as sess:
            claim_row = sess.get(Claim, claim_id)
            if claim_row is not None:
                claim_row.status = "monthly_cap_reached"
            sess.add(
                AuditLog(
                    actor="agent",
                    action="refund.skipped_cap",
                    payload={
                        "claim_id": claim_id,
                        "shop_id": shop_id,
                        "refund_month": refund_month,
                        "reason": "uq_refunds_shop_month",
                    },
                )
            )
        payload = {
            "claim_id": claim_id,
            "shop_id": shop_id,
            "refund_id": refund_id,
            "amount_paise": 0,
            "status": "monthly_cap_reached",
            "label": "Monthly cap reached",
            "live": False,
            "replay": is_offline(cfg),
        }
        runtime.bus.publish("refund.status", payload)
        return payload

    runtime.bus.publish(
        "agent.step",
        {
            "claim_id": claim_id,
            "node": "payback",
            "status": "ok" if refund_status != "refund_failed" else "error",
            "detail": f"Payback {refund_id} for {shop_id}: {refund_status} ({mode_label})",
            "live": live_call,
        },
    )
    payload = {
        "claim_id": claim_id,
        "shop_id": shop_id,
        "refund_id": refund_id,
        "amount_paise": PLAN_FEE_PAISE,
        "status": refund_status,
        "label": mode_label,
        "live": live_call,
        "replay": is_offline(cfg),
    }
    runtime.bus.publish("refund.status", payload)
    return payload


async def run_batch_payback(
    runtime: AgentRuntime,
    batch_id: str,
) -> list[dict[str, Any]]:
    """Run plan-fee payback sequentially for all claims in an approved batch."""
    cfg = runtime.settings_getter()
    if not cfg.payback_enabled:
        return []

    with runtime.db.session() as sess:
        batch_row = sess.get(Batch, batch_id)
        if batch_row is None or batch_row.status != "approved":
            return []
        claim_ids = [
            c.id
            for c in sess.scalars(
                select(Claim).where(Claim.batch_id == batch_id).order_by(Claim.shop_id)
            )
        ]

    results: list[dict[str, Any]] = []
    for cid in claim_ids:
        res = await execute_claim_payback(runtime, cid)
        results.append(res)
    return results
