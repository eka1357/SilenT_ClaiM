"""FastAPI D1 backend spine tests: checkpoint flow, personas, rate limiting, and guards."""

from __future__ import annotations

import asyncio
import base64
import time
import zlib
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.detector.config import RULES_VERSION
from app.integrations.paytm import PENDING_SIMULATED_LABEL, PaytmConfigError
from app.integrations.replay import FIXTURES_DIR
from app.main import create_app

API_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = API_ROOT / "samples"


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid(*args: object, **kwargs: object) -> httpx.Response:
        msg = "API unit tests must never perform outbound HTTP requests"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbid)
    monkeypatch.setenv("DEMO_OFFLINE", "1")


def _build_test_client(
    tmp_path: Path,
    *,
    settings: Settings | None = None,
) -> TestClient:
    cfg = settings or Settings(
        demo_mode=True,
        demo_offline=True,
        paytm_mode="pending",
        paytm_host="https://securestage.paytmpayments.com",
        rate_limit_per_minute=30,
    )
    app = create_app(
        settings=cfg,
        database_url=f"sqlite:///{(tmp_path / 'api_d1.db').as_posix()}",
        fixtures_dir=FIXTURES_DIR,
        runs_dir=tmp_path / "runs",
        samples_dir=SAMPLES_DIR,
    )
    return TestClient(app)


def _extract_pdf_text_streams(pdf_bytes: bytes) -> str:
    """Decode uncompressed and ASCII85/Flate-compressed PDF content streams for assertions."""
    chunks: list[str] = [pdf_bytes.decode("latin-1", errors="ignore")]
    cursor = 0
    while True:
        start = pdf_bytes.find(b"stream", cursor)
        if start == -1:
            break
        nl = pdf_bytes.find(b"\n", start)
        if nl == -1:
            break
        end = pdf_bytes.find(b"endstream", nl)
        if end == -1:
            break
        raw_stream = pdf_bytes[nl + 1 : end].strip(b"\r\n")
        for candidate in (
            raw_stream,
            _safe_a85_decode(raw_stream),
        ):
            if candidate is None:
                continue
            try:
                chunks.append(zlib.decompress(candidate).decode("latin-1", errors="ignore"))
                break
            except zlib.error:
                pass
        cursor = end + len(b"endstream")
    joined = "\n".join(chunks).replace(r"\(", "(").replace(r"\)", ")")
    return joined.replace(") Tj T* (", " ")


def _safe_a85_decode(data: bytes) -> bytes | None:
    try:
        return base64.a85decode(data, adobe=True)
    except ValueError:
        try:
            return base64.a85decode(data, adobe=False)
        except ValueError:
            return None


def test_startup_guard_refuses_non_staging_paytm_host(tmp_path: Path) -> None:
    bad_settings = Settings(
        demo_mode=True,
        demo_offline=True,
        paytm_mode="staging",
        paytm_host="https://securegw.paytm.in",
    )
    with pytest.raises(PaytmConfigError):
        create_app(
            settings=bad_settings,
            database_url=f"sqlite:///{(tmp_path / 'bad.db').as_posix()}",
        )


def test_offline_oct21_checkpoint_end_to_end(tmp_path: Path) -> None:
    """D1 checkpoint (speed=0 for instant replay): 9 drops, 7 consent asks, Selvi tap -> PDF."""
    with _build_test_client(tmp_path) as client:
        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        assert health["demo_offline"] is True
        assert health["integrations"]["weather"]["mode"] == "replay"
        assert health["integrations"]["sarvam"]["mode"] == "replay"
        assert health["integrations"]["llm"]["mode"] == "replay"
        assert health["integrations"]["paytm"]["mode"] == "simulated"
        assert health["integrations"]["paytm"]["label"] == PENDING_SIMULATED_LABEL

        reset_resp = client.post("/api/scenario/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["seeded"]["shops"] == 12

        run_resp = client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 0})
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "completed"
        assert run_data["shops_evaluated"] == 12
        assert run_data["pending_asks"] == 9

        street_resp = client.get("/api/street/panagal_park_road")
        assert street_resp.status_code == 200
        street_data = street_resp.json()
        shops = {s["shop_id"]: s for s in street_data["shops"]}
        assert len(shops) == 12
        dropped_ids = {sid for sid, s in shops.items() if s["status"] == "dropped"}
        assert dropped_ids == {
            "shop_01",
            "shop_02",
            "shop_04",
            "shop_05",
            "shop_06",
            "shop_08",
            "shop_09",
            "shop_10",
            "shop_12",
        }
        for trading_sid in ("shop_03", "shop_07", "shop_11"):
            assert shops[trading_sid]["status"] == "trading"
            assert shops[trading_sid]["detection"]["decision"] == "none"

        claims_before = client.get("/api/claims").json()
        asks_before = {a["shop_id"]: a for a in claims_before["asks"]}
        consent_shop_ids = {sid for sid, a in asks_before.items() if a["ask_kind"] == "consent"}
        assert consent_shop_ids == {
            "shop_01",
            "shop_02",
            "shop_04",
            "shop_05",
            "shop_06",
            "shop_08",
            "shop_09",
        }

        # Only Selvi stays pending until her real tap; the other six auto-consent as simulated.
        assert asks_before["shop_01"]["status"] == "pending"
        assert asks_before["shop_01"]["reply_type"] is None
        for auto_sid in ("shop_02", "shop_04", "shop_05", "shop_06", "shop_08", "shop_09"):
            assert asks_before[auto_sid]["status"] == "filed"
            assert asks_before[auto_sid]["reply_type"] == "tap"
            assert asks_before[auto_sid]["simulated_label"] == "Simulated consent"

        # Meena and Kavya were asked and resolved automatically via simulated Tamil voice notes.
        assert asks_before["shop_10"]["ask_kind"] == "voice"
        assert asks_before["shop_10"]["cause_label"] == "leave"
        assert asks_before["shop_10"]["status"] == "closed"
        assert asks_before["shop_10"]["simulated_label"] == "Simulated reply"

        assert asks_before["shop_12"]["ask_kind"] == "voice"
        assert asks_before["shop_12"]["cause_label"] == "qr_switch"
        assert asks_before["shop_12"]["status"] == "human_review"
        assert asks_before["shop_12"]["simulated_label"] == "Simulated reply"

        # Selvi's Tamil prompt audio plays offline via recorded replay fixture.
        selvi_ask_id = asks_before["shop_01"]["id"]
        audio_resp = client.get(f"/api/asks/{selvi_ask_id}/audio")
        assert audio_resp.status_code == 200
        assert audio_resp.headers["content-type"].startswith("audio/wav")
        assert audio_resp.content[:4] == b"RIFF"

        # Selvi taps consent -> files the 7th claim (not marked simulated).
        consent_resp = client.post(f"/api/asks/{selvi_ask_id}/consent")
        assert consent_resp.status_code == 200
        consent_data = consent_resp.json()
        assert consent_data["status"] == "filed"
        selvi_claim_id = consent_data["claim"]["id"]
        assert consent_data["ask"]["simulated_label"] is None

        claims_after = client.get("/api/claims").json()
        filed_shops = {c["shop_id"] for c in claims_after["claims"]}
        assert filed_shops == consent_shop_ids

        # Evidence pack PDF downloads cleanly with mandatory fields and synthetic disclaimer.
        pdf_resp = client.get(f"/api/evidence/{selvi_claim_id}.pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content.startswith(b"%PDF-")
        pdf_text = _extract_pdf_text_streams(pdf_resp.content)
        assert "/Count 1" in pdf_text
        assert "Synthetic data for demonstration" in pdf_text
        assert RULES_VERSION in pdf_text
        assert (
            "Selvi's flower stall took Rs. 0 on 21 Oct 2026 against a usual Rs. 3,201: "
            "9 of 12 shops on the street shut, 27.7 mm of rain."
        ) in pdf_text
        assert "Summary (written by AI from the numbers above; it sets no amount)" in pdf_text
        assert "Cosmetic Note" not in pdf_text
        assert "Transactions" not in pdf_text
        assert pdf_text.count("(Replay)") == 1

        # SSE bus recorded the required events with monotonically increasing IDs.
        bus_events = client.app.state.container.bus.events  # type: ignore[attr-defined]
        assert [e.id for e in bus_events] == sorted(e.id for e in bus_events)
        seen_names = {e.event for e in bus_events}
        for required_event in (
            "clock.tick",
            "shop.status",
            "detector.decision",
            "agent.step",
            "ask.sent",
            "ask.answered",
            "claim.filed",
            "integration.health",
        ):
            assert required_event in seen_names


def test_thirty_first_request_in_minute_to_asks_returns_429(tmp_path: Path) -> None:
    """Case 15 (docs/TESTING.md): 31st request in a minute to /api/asks/* returns 429."""
    with _build_test_client(tmp_path) as client:
        for _ in range(30):
            resp = client.get("/api/asks/nonexistent/audio")
            assert resp.status_code == 404
        blocked = client.get("/api/asks/nonexistent/audio")
        assert blocked.status_code == 429


def test_scenario_endpoints_enforce_demo_mode_and_rate_limit(tmp_path: Path) -> None:
    disabled_settings = Settings(
        demo_mode=False,
        demo_offline=True,
        paytm_mode="pending",
        paytm_host="https://securestage.paytmpayments.com",
    )
    with _build_test_client(tmp_path, settings=disabled_settings) as client:
        assert client.post("/api/scenario/reset").status_code == 403
        assert (
            client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 0}).status_code
            == 403
        )


def test_voice_upload_rejects_oversize_and_non_audio_payloads(tmp_path: Path) -> None:
    with _build_test_client(tmp_path) as client:
        client.post("/api/scenario/reset")
        client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 0})
        claims_data = client.get("/api/claims").json()
        selvi_ask_id = next(a["id"] for a in claims_data["asks"] if a["shop_id"] == "shop_01")

        non_audio = client.post(
            f"/api/asks/{selvi_ask_id}/voice",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert non_audio.status_code == 400

        oversize = client.post(
            f"/api/asks/{selvi_ask_id}/voice",
            files={"file": ("big.wav", b"RIFF" + b"0" * (2 * 1024 * 1024 + 10), "audio/wav")},
        )
        assert oversize.status_code == 413


def test_normal_day_intraday_quiet_hours_do_not_trigger_drop(tmp_path: Path) -> None:
    """Clarification 3(a): quiet hours during a normal trading day never feed decide()."""
    with _build_test_client(tmp_path) as client:
        run_resp = client.post("/api/scenario/run", json={"day": "2026-10-15", "speed": 0})
        assert run_resp.status_code == 200
        claims_data = client.get("/api/claims").json()
        assert claims_data["claims"] == []
        assert claims_data["asks"] == []


def test_async_background_run_with_positive_speed(tmp_path: Path) -> None:
    """Verify speed > 0 background task path (used at speed=60 in demo) completes cleanly."""
    with _build_test_client(tmp_path) as client:
        start_resp = client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 3600})
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "started"

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            street_data = client.get("/api/street/panagal_park_road").json()
            if (
                not street_data["clock"]["running"]
                and street_data["clock"]["hours_completed"] == 16
            ):
                break
            time.sleep(0.05)
        else:
            pytest.fail("Background scenario run did not complete within 8s")

        claims_data = client.get("/api/claims").json()
        assert len(claims_data["claims"]) == 6
        pending = [a for a in claims_data["asks"] if a["status"] == "pending"]
        assert len(pending) == 1
        assert pending[0]["shop_id"] == "shop_01"


def test_sse_stream_replays_from_last_event_id(tmp_path: Path) -> None:
    """GET /api/stream emits SSE frames with monotonic event IDs and supports Last-Event-ID."""
    cfg = Settings(
        demo_mode=True,
        demo_offline=True,
        paytm_mode="pending",
        paytm_host="https://securestage.paytmpayments.com",
    )
    app = create_app(
        settings=cfg,
        database_url=f"sqlite:///{(tmp_path / 'sse.db').as_posix()}",
        fixtures_dir=FIXTURES_DIR,
        runs_dir=tmp_path / "runs",
        samples_dir=SAMPLES_DIR,
    )
    container = app.state.container
    container.db.seed(reset=False)
    e1 = container.bus.publish("clock.tick", {"ts": "2026-10-21T07:00:00+05:30"})
    e2 = container.bus.publish("shop.status", {"shop_id": "shop_01", "status": "trading"})
    e3: dict[str, Any] = {}

    async def _exercise_sse_asgi() -> tuple[int, dict[bytes, bytes], str]:
        response_status = 0
        response_headers: dict[bytes, bytes] = {}
        body_chunks: list[bytes] = []
        disconnected = asyncio.Event()
        live_pushed = False

        async def _receive() -> dict[str, Any]:
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def _send(message: dict[str, Any]) -> None:
            nonlocal response_status, response_headers, live_pushed
            if message["type"] == "http.response.start":
                response_status = int(message["status"])
                response_headers = dict(message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)
                joined = b"".join(body_chunks).decode("utf-8", errors="ignore")
                if not live_pushed and f"id: {e2.id}" in joined:
                    live_pushed = True
                    published = container.bus.publish(
                        "claim.filed",
                        {"claim_id": "clm_demo", "live": False, "replay": True},
                    )
                    e3["id"] = published.id
                elif '"claim_id": "clm_demo"' in joined:
                    disconnected.set()
                    container.bus.close_all()

        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/stream",
            "raw_path": b"/api/stream",
            "query_string": b"",
            "headers": [(b"last-event-id", str(e1.id).encode("ascii"))],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        await asyncio.wait_for(app(scope, _receive, _send), timeout=5.0)
        return response_status, response_headers, b"".join(body_chunks).decode("utf-8")

    status_code, resp_headers, body = asyncio.run(_exercise_sse_asgi())
    assert status_code == 200
    assert resp_headers[b"content-type"].startswith(b"text/event-stream")
    assert f"id: {e1.id}" not in body
    assert f"id: {e2.id}\nevent: shop.status" in body
    assert f"id: {e3['id']}\nevent: claim.filed" in body
    container.db.dispose()
