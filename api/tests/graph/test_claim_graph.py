"""LangGraph path tests (docs/TESTING.md Graph layer) with DEMO_OFFLINE=1 and no network.

Required paths:
- Selvi -> ask(consent) -> tap -> file (+ PDF generated, Claim created)
- Meena -> ask(voice) -> leave -> close (no claim filed)
- Kavya -> ask(voice) -> qr_switch -> human_review (no claim filed)
- Voice flood_closure -> ask(voice) -> flood_closure -> file
- Weather unavailable -> ask with reason rain_unavailable
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.agents.graph import ClaimGraphRunner
from app.agents.nodes import AgentRuntime
from app.config import Settings
from app.db import DATA_DIR, DatabaseManager
from app.detector.config import RULES_VERSION
from app.events import EventBus, IntegrationHealthTracker
from app.integrations.replay import FIXTURES_DIR
from app.models import Ask, Claim, Detection

API_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = API_ROOT / "samples"
FLOOD_DAY = "2026-10-21"


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid(*args: object, **kwargs: object) -> httpx.Response:
        msg = "Graph tests must never make live network calls"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbid)
    monkeypatch.setenv("DEMO_OFFLINE", "1")


def _make_runner(
    tmp_path: Path,
    *,
    fixtures_dir: Path = FIXTURES_DIR,
) -> tuple[ClaimGraphRunner, DatabaseManager, EventBus]:
    settings = Settings(
        demo_mode=True,
        demo_offline=True,
        paytm_mode="pending",
        paytm_host="https://securestage.paytmpayments.com",
    )
    db_path = tmp_path / "graph_test.db"
    db = DatabaseManager(f"sqlite:///{db_path.as_posix()}", data_dir=DATA_DIR)
    db.seed(reset=True)
    bus = EventBus()
    health = IntegrationHealthTracker(bus=bus, settings_getter=lambda: settings)
    runtime = AgentRuntime(
        db=db,
        bus=bus,
        health=health,
        settings_getter=lambda: settings,
        fixtures_dir=fixtures_dir,
        runs_dir=tmp_path / "runs",
    )
    return ClaimGraphRunner(runtime), db, bus


def test_selvi_flood_interrupts_and_consent_tap_files_claim(tmp_path: Path) -> None:
    runner, db, bus = _make_runner(tmp_path)
    try:
        paused = runner.run_shop_day(shop_id="shop_01", day_iso=FLOOD_DAY)
        assert "__interrupt__" in paused
        assert paused["detection"]["decision"] == "file"
        assert paused["detection"]["reason"] == "flood_quorum_and_rain"

        with db.session() as sess:
            ask = sess.scalar(select(Ask).where(Ask.shop_id == "shop_01"))
            assert ask is not None
            assert ask.ask_kind == "consent"
            assert ask.status == "pending"
            assert ask.prompt_audio_path is not None
            assert Path(ask.prompt_audio_path).exists()
            assert sess.scalar(select(Claim).where(Claim.shop_id == "shop_01")) is None

        resumed = runner.resume_consent(ask, simulated_label=None)
        assert resumed["terminal_status"] == "filed"
        assert resumed["trace"] == ["sense", "confirm", "ask", "file"]

        with db.session() as sess:
            claim = sess.scalar(select(Claim).where(Claim.shop_id == "shop_01"))
            updated_ask = sess.get(Ask, ask.id)
            assert claim is not None
            assert claim.status == "filed"
            assert claim.consent_at is not None
            assert claim.consent_at.tzinfo is not None
            assert claim.evidence_pdf_path is not None
            pdf_file = Path(claim.evidence_pdf_path)
            assert pdf_file.exists()
            assert pdf_file.read_bytes().startswith(b"%PDF-")
            assert updated_ask is not None
            assert updated_ask.status == "filed"
            assert updated_ask.reply_type == "tap"
            assert updated_ask.simulated_label is None

        event_names = [e.event for e in bus.events]
        assert event_names.count("ask.sent") == 1  # No duplicate ask.sent on resume
        assert "ask.answered" in event_names
        assert "claim.filed" in event_names
    finally:
        db.dispose()


def test_meena_inactive_before_flood_goes_ask_leave_close(tmp_path: Path) -> None:
    runner, db, bus = _make_runner(tmp_path)
    try:
        paused = runner.run_shop_day(shop_id="shop_10", day_iso=FLOOD_DAY)
        assert "__interrupt__" in paused
        assert paused["detection"]["decision"] == "ask"
        assert paused["detection"]["reason"] == "inactive_before_event"

        with db.session() as sess:
            ask = sess.scalar(select(Ask).where(Ask.shop_id == "shop_10"))
            assert ask is not None
            assert ask.ask_kind == "voice"
            assert ask.status == "pending"

        leave_wav = (SAMPLES_DIR / "tts_leave.wav").read_bytes()
        resumed = runner.resume_voice(
            ask,
            audio_bytes=leave_wav,
            filename="tts_leave.wav",
            simulated_label="Simulated reply",
        )
        assert resumed["terminal_status"] == "closed"
        assert resumed["trace"] == ["sense", "confirm", "ask", "classify", "close"]

        with db.session() as sess:
            updated = sess.get(Ask, ask.id)
            assert updated is not None
            assert updated.cause_label == "leave"
            assert updated.status == "closed"
            assert updated.reply_type == "voice"
            assert updated.simulated_label == "Simulated reply"
            assert sess.scalar(select(Claim).where(Claim.shop_id == "shop_10")) is None

        answered = [e for e in bus.events if e.event == "ask.answered"]
        assert len(answered) == 1
        assert answered[0].data["cause_label"] == "leave"
    finally:
        db.dispose()


def test_kavya_qr_switch_goes_ask_qr_switch_human_review(tmp_path: Path) -> None:
    runner, db, bus = _make_runner(tmp_path)
    try:
        paused = runner.run_shop_day(shop_id="shop_12", day_iso=FLOOD_DAY)
        assert "__interrupt__" in paused
        assert paused["detection"]["decision"] == "ask"

        with db.session() as sess:
            ask = sess.scalar(select(Ask).where(Ask.shop_id == "shop_12"))
            assert ask is not None

        qr_wav = (SAMPLES_DIR / "tts_qr_switch.wav").read_bytes()
        resumed = runner.resume_voice(
            ask,
            audio_bytes=qr_wav,
            filename="tts_qr_switch.wav",
            simulated_label="Simulated reply",
        )
        assert resumed["terminal_status"] == "human_review"
        assert resumed["trace"] == ["sense", "confirm", "ask", "classify", "human_review"]

        with db.session() as sess:
            updated = sess.get(Ask, ask.id)
            assert updated is not None
            assert updated.cause_label == "qr_switch"
            assert updated.status == "human_review"
            assert sess.scalar(select(Claim).where(Claim.shop_id == "shop_12")) is None

        answered = [e for e in bus.events if e.event == "ask.answered"]
        assert len(answered) == 1
        assert answered[0].data["cause_label"] == "qr_switch"
    finally:
        db.dispose()


def test_ravi_still_trading_completes_without_ask_or_claim(tmp_path: Path) -> None:
    runner, db, _ = _make_runner(tmp_path)
    try:
        done = runner.run_shop_day(shop_id="shop_03", day_iso=FLOOD_DAY)
        assert "__interrupt__" not in done
        assert done["detection"]["decision"] == "none"
        assert done["terminal_status"] == "none"
        assert done["trace"] == ["sense", "confirm"]

        with db.session() as sess:
            det = sess.scalar(
                select(Detection).where(
                    Detection.shop_id == "shop_03",
                    Detection.day == date(2026, 10, 21),
                )
            )
            assert det is not None
            assert det.rules_version == RULES_VERSION
            assert sess.scalar(select(Ask).where(Ask.shop_id == "shop_03")) is None
            assert sess.scalar(select(Claim).where(Claim.shop_id == "shop_03")) is None
    finally:
        db.dispose()


def test_voice_flood_reply_routes_classify_to_file(tmp_path: Path) -> None:
    runner, db, _ = _make_runner(tmp_path)
    try:
        paused = runner.run_shop_day(shop_id="shop_10", day_iso=FLOOD_DAY)
        assert "__interrupt__" in paused
        with db.session() as sess:
            ask = sess.scalar(select(Ask).where(Ask.shop_id == "shop_10"))
            assert ask is not None

        flood_wav = (SAMPLES_DIR / "tts_flood.wav").read_bytes()
        resumed = runner.resume_voice(
            ask,
            audio_bytes=flood_wav,
            filename="tts_flood.wav",
            simulated_label="Simulated reply",
        )
        assert resumed["terminal_status"] == "filed"
        assert resumed["trace"] == ["sense", "confirm", "ask", "classify", "file"]

        with db.session() as sess:
            claim = sess.scalar(select(Claim).where(Claim.shop_id == "shop_10"))
            assert claim is not None
            assert claim.status == "filed"
    finally:
        db.dispose()


def test_missing_weather_fixture_falls_back_to_ask_rain_unavailable(tmp_path: Path) -> None:
    empty_fixtures = tmp_path / "empty_fixtures"
    empty_fixtures.mkdir(parents=True, exist_ok=True)
    runner, db, bus = _make_runner(tmp_path, fixtures_dir=empty_fixtures)
    try:
        paused = runner.run_shop_day(shop_id="shop_01", day_iso=FLOOD_DAY)
        assert "__interrupt__" in paused
        assert paused["detection"]["decision"] == "ask"
        assert paused["detection"]["reason"] == "rain_unavailable"
        assert "rain_unavailable" in paused["errors"]
        assert any(
            e.event == "integration.health"
            and e.data["name"] == "weather"
            and e.data["mode"] == "down"
            for e in bus.events
        )
    finally:
        db.dispose()
