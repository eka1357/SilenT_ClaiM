"""Unit and integration tests for Task D2: adjuster batch approval, payback, and metrics."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.nodes import execute_claim_payback
from app.config import Settings
from app.detector.config import PLAN_FEE_PAISE, RULES_VERSION
from app.integrations.paytm import PENDING_SIMULATED_LABEL, build_refund_id
from app.main import create_app
from app.models import AuditLog, Claim, Detection, Refund


def _make_settings(
    *,
    demo_offline: bool = True,
    paytm_mode: str = "pending",
    payback_enabled: bool = True,
    paytm_mid: str = "",
    paytm_merchant_key: str = "",
) -> Settings:
    return Settings(
        demo_mode=True,
        demo_offline=demo_offline,
        paytm_mode=paytm_mode,
        paytm_mid=paytm_mid,
        paytm_merchant_key=paytm_merchant_key,
        paytm_base_url="https://securestage.paytmpayments.com",
        paytm_order_base_url="https://securegw-stage.paytmpayments.in",
        payback_enabled=payback_enabled,
        rate_limit_per_minute=200,
    )


def _create_test_app(
    tmp_path: Path,
    *,
    settings: Settings | None = None,
) -> Any:
    cfg = settings or _make_settings()
    db_file = tmp_path / "test_d2.db"
    runs_dir = tmp_path / "runs"
    app = create_app(
        settings=cfg,
        database_url=f"sqlite:///{db_file.as_posix()}",
        runs_dir=runs_dir,
    )
    app.state.container.db.seed(reset=True)
    app.state.container.runtime.refund_poll_interval_s = 0.0
    return app


async def _run_oct21_and_tap_selvi(
    app: Any,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    run_resp = await client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 0})
    assert run_resp.status_code == 200
    if app.state.container.scenario._active_task is not None:
        await app.state.container.scenario._active_task

    street_resp = await client.get("/api/street/panagal_park_road")
    assert street_resp.status_code == 200
    shops = {s["shop_id"]: s for s in street_resp.json()["shops"]}
    selvi_ask_id = shops["shop_01"]["ask"]["id"]

    consent_resp = await client.post(f"/api/asks/{selvi_ask_id}/consent")
    assert consent_resp.status_code == 200
    return consent_resp.json()


@pytest.mark.anyio
async def test_d2_checkpoint_batch_ready_approve_and_seven_simulated_refunds(
    tmp_path: Path,
) -> None:
    """D2 checkpoint: 7 claims batched on Selvi consent; approve emits 7 'Simulated: keys pending' refunds."""
    app = _create_test_app(tmp_path)
    container = app.state.container

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Before Selvi taps consent, 6 claims are filed and no batch is open yet.
        await client.post("/api/scenario/run", json={"day": "2026-10-21", "speed": 0})
        if container.scenario._active_task is not None:
            await container.scenario._active_task

        pre_batch = (await client.get("/api/batches/current")).json()
        assert pre_batch["batch"] is None

        street = (await client.get("/api/street/panagal_park_road")).json()
        selvi_ask_id = next(s["ask"]["id"] for s in street["shops"] if s["shop_id"] == "shop_01")

        # Selvi's tap completes the 7th consent ask -> creates batch and emits batch.ready
        consent_res = await client.post(f"/api/asks/{selvi_ask_id}/consent")
        assert consent_res.status_code == 200

        cur_batch = (await client.get("/api/batches/current")).json()
        assert cur_batch["id"] == "batch_20261021"
        assert cur_batch["status"] == "open"
        assert cur_batch["claims_count"] == 7
        assert len(cur_batch["claims"]) == 7

        events_so_far = container.bus.events
        batch_ready_events = [e for e in events_so_far if e.event == "batch.ready"]
        assert len(batch_ready_events) == 1
        assert batch_ready_events[0].data["batch_id"] == "batch_20261021"
        assert batch_ready_events[0].data["n"] == 7

        # Approve batch -> returns immediately and runs payback in background
        approve_res = await client.post("/api/batches/batch_20261021/approve")
        assert approve_res.status_code == 200
        approve_body = approve_res.json()
        assert approve_body["status"] == "approved"
        assert approve_body["approved_by"] == "adjuster"
        assert approve_body["already_approved"] is False
        assert approve_body["payback_scheduled"] is True

        # Wait for background payback task to finish
        payback_items = await container.scenario.wait_for_payback("batch_20261021")
        assert len(payback_items) == 7

        # Verify all 7 refunds are Rs 35 (3500 paise) and labelled "Simulated: keys pending"
        after_batch = (await client.get("/api/batches/current")).json()
        assert after_batch["status"] == "approved"
        refunds = [c["refund"] for c in after_batch["claims"]]
        assert all(r is not None for r in refunds)
        for c in after_batch["claims"]:
            r = c["refund"]
            assert r["refund_id"] == f"SC-{c['id']}"
            assert r["amount_paise"] == PLAN_FEE_PAISE == 3500
            assert r["status"] == "SIMULATED"
            assert r["label"] == PENDING_SIMULATED_LABEL
            assert c["status"] == "paid_sim"

        all_events = container.bus.events
        batch_approved_events = [e for e in all_events if e.event == "batch.approved"]
        refund_status_events = [e for e in all_events if e.event == "refund.status"]
        assert len(batch_approved_events) == 1
        assert len(refund_status_events) == 7
        assert all(e.data["label"] == PENDING_SIMULATED_LABEL for e in refund_status_events)

        # Second approval of the same batch sends nothing
        second_approve = await client.post("/api/batches/batch_20261021/approve")
        assert second_approve.status_code == 200
        second_body = second_approve.json()
        assert second_body["already_approved"] is True
        assert second_body["payback_scheduled"] is False
        assert len([e for e in container.bus.events if e.event == "refund.status"]) == 7


@pytest.mark.anyio
async def test_case_11_monthly_payout_cap_enforced_in_db_and_payback(
    tmp_path: Path,
) -> None:
    """TESTING.md Case 11: at most 1 refund per shop per calendar month (rules + DB unique constraint)."""
    app = _create_test_app(tmp_path)
    container = app.state.container

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _run_oct21_and_tap_selvi(app, client)
        await client.post("/api/batches/batch_20261021/approve")
        await container.scenario.wait_for_payback("batch_20261021")

    # Insert a second detection + claim for shop_01 in the same calendar month (2026-10)
    second_det_id = "det_20261028_shop_01"
    second_claim_id = "clm_20261028_shop_01_cap"
    with container.db.session() as sess:
        sess.add(
            Detection(
                id=second_det_id,
                shop_id="shop_01",
                day=date(2026, 10, 28),
                baseline_paise=420000,
                day_income_paise=0,
                dropped=True,
                eligible=True,
                quorum_share=0.75,
                rain_mm=85.0,
                rain_source="replay:open-meteo",
                decision="file",
                reason="flood_quorum_met",
                rules_version=RULES_VERSION,
            )
        )
        sess.flush()
        sess.add(
            Claim(
                id=second_claim_id,
                shop_id="shop_01",
                detection_id=second_det_id,
                status="approved",
                summary_text="Second claim in October.",
            )
        )

    res = await execute_claim_payback(container.runtime, second_claim_id)
    assert res["status"] == "monthly_cap_reached"
    assert res["amount_paise"] == 0

    with container.db.session() as sess:
        second_claim = sess.get(Claim, second_claim_id)
        assert second_claim is not None
        assert second_claim.status == "monthly_cap_reached"
        oct_shop01_refunds = list(
            sess.scalars(
                select(Refund).where(
                    Refund.shop_id == "shop_01",
                    Refund.refund_month == "2026-10",
                )
            )
        )
        assert len(oct_shop01_refunds) == 1

    # Also verify the raw database unique constraint uq_refunds_shop_month directly
    with pytest.raises(IntegrityError), container.db.session() as sess:
        sess.add(
            Refund(
                id="rfd_dup_month",
                claim_id=second_claim_id,
                shop_id="shop_01",
                refund_month="2026-10",
                paytm_order_id="ORD-DUP",
                refund_id=build_refund_id(second_claim_id),
                amount_paise=PLAN_FEE_PAISE,
                status="SIMULATED",
                mode_label=PENDING_SIMULATED_LABEL,
                raw_response={},
            )
        )


@pytest.mark.anyio
async def test_case_12_refund_idempotency_never_sends_second_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TESTING.md Case 12: calling payback twice for the same claim reuses SC-<claim_id> and makes 0 extra calls."""
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    call_log: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        call_log.append(str(request.url.path))
        if request.url.path.endswith("/v3/order/status"):
            return httpx.Response(
                200,
                json={
                    "body": {
                        "resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "01"},
                        "orderId": "ORD-STG-SHOP-01",
                        "txnId": "TXN-STG-001",
                        "txnAmount": "35.00",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "body": {
                    "resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "10"},
                    "orderId": "ORD-STG-SHOP-01",
                    "refId": "SC-clm",
                    "refundId": "PAYTM-RFD-01",
                    "refundAmount": "35.00",
                }
            },
        )

    settings = _make_settings(
        demo_offline=False,
        paytm_mode="staging",
        paytm_mid="STAGE_MID_123",
        paytm_merchant_key="0123456789abcdef",
    )
    app = _create_test_app(tmp_path, settings=settings)
    container = app.state.container
    container.runtime.paytm_http_client = httpx.Client(transport=httpx.MockTransport(_handler))

    # Create a single claim for shop_01 (which has staging_order_id="ORD-STG-SHOP-01")
    claim_id = "clm_20261021_shop_01_idem"
    with container.db.session() as sess:
        sess.add(
            Detection(
                id="det_20261021_shop_01_idem",
                shop_id="shop_01",
                day=date(2026, 10, 21),
                baseline_paise=420000,
                day_income_paise=0,
                dropped=True,
                eligible=True,
                quorum_share=0.75,
                rain_mm=85.0,
                rain_source="replay:open-meteo",
                decision="file",
                reason="flood_quorum_met",
                rules_version=RULES_VERSION,
            )
        )
        sess.flush()
        sess.add(
            Claim(
                id=claim_id,
                shop_id="shop_01",
                detection_id="det_20261021_shop_01_idem",
                status="approved",
                summary_text="Idempotency test claim.",
            )
        )

    first = await execute_claim_payback(container.runtime, claim_id)
    assert first["refund_id"] == f"SC-{claim_id}"
    assert first["status"] == "TXN_SUCCESS"
    calls_after_first = len(call_log)
    assert calls_after_first == 3  # txn status + refund apply + refund status

    # Second call for the same claim must not hit Paytm again
    second = await execute_claim_payback(container.runtime, claim_id)
    assert second["refund_id"] == f"SC-{claim_id}"
    assert second.get("idempotent") is True
    assert len(call_log) == calls_after_first


@pytest.mark.anyio
async def test_case_13_payback_disabled_approves_batch_and_pauses_refunds(
    tmp_path: Path,
) -> None:
    """TESTING.md Case 13: PAYBACK_ENABLED=0 approves the batch, sends no refund, and marks 'Refunds paused'."""
    settings = _make_settings(payback_enabled=False)
    app = _create_test_app(tmp_path, settings=settings)
    container = app.state.container

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _run_oct21_and_tap_selvi(app, client)

        approve_res = await client.post("/api/batches/batch_20261021/approve")
        assert approve_res.status_code == 200
        body = approve_res.json()
        assert body["status"] == "approved"
        assert body["payback_scheduled"] is False
        assert all(c["status"] == "Refunds paused" for c in body["claims"])
        assert all(c["refund"] is None for c in body["claims"])

    with container.db.session() as sess:
        refund_rows = list(sess.scalars(select(Refund)))
        assert refund_rows == []
        audit_actions = [a.action for a in sess.scalars(select(AuditLog))]
        assert "batch.approved" in audit_actions
        assert "payback.paused" in audit_actions


@pytest.mark.anyio
async def test_mixed_batch_staging_mode_one_live_order_and_six_simulated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mixed batch in PAYTM_MODE=staging: shop_01 hits Paytm staging; 6 shops get 'Simulated refund (no staging payment)'."""
    paytm_requests: list[tuple[str, dict[str, Any]]] = []

    def _staging_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        paytm_requests.append((request.url.path, payload))
        order_id = payload.get("body", {}).get("orderId", "")
        if request.url.path.endswith("/v3/order/status"):
            return httpx.Response(
                200,
                json={
                    "head": {"version": "v1", "signature": "SECRET_RESP_SIG_999"},
                    "body": {
                        "resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "01"},
                        "orderId": order_id,
                        "txnId": "TXN-SELVI-LIVE-01",
                        "txnAmount": "35.00",
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "head": {"version": "v1", "signature": "SECRET_RESP_SIG_999"},
                "body": {
                    "resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "10"},
                    "orderId": order_id,
                    "refId": payload.get("body", {}).get("refId", ""),
                    "refundId": "PAYTM-LIVE-RFD-01",
                    "refundAmount": "35.00",
                },
            },
        )

    # Use DEMO_OFFLINE=1 for weather/STT/LLM during scenario run, then switch to staging for approval
    app = _create_test_app(tmp_path)
    container = app.state.container

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _run_oct21_and_tap_selvi(app, client)

        # Switch settings to PAYTM_MODE=staging (live HTTP transport) before approving
        monkeypatch.setenv("DEMO_OFFLINE", "0")
        staging_settings = _make_settings(
            demo_offline=False,
            paytm_mode="staging",
            paytm_mid="STAGE_MID_123",
            paytm_merchant_key="0123456789abcdef",
        )
        container.settings_getter = lambda: staging_settings
        container.runtime.settings_getter = lambda: staging_settings
        container.runtime.paytm_http_client = httpx.Client(
            transport=httpx.MockTransport(_staging_handler)
        )

        approve_res = await client.post("/api/batches/batch_20261021/approve")
        assert approve_res.status_code == 200
        await container.scenario.wait_for_payback("batch_20261021")

        batch_data = (await client.get("/api/batches/current")).json()
        claims_by_shop = {c["shop_id"]: c for c in batch_data["claims"]}
        assert len(claims_by_shop) == 7

        # shop_01 (Selvi) has staging_order_id="ORD-STG-SHOP-01" -> live staging refund
        selvi_claim = claims_by_shop["shop_01"]
        assert selvi_claim["status"] == "approved"
        assert selvi_claim["refund"]["status"] == "TXN_SUCCESS"
        assert selvi_claim["refund"]["label"] == "Live"
        assert selvi_claim["refund"]["paytm_order_id"] == "ORD-STG-SHOP-01"
        assert selvi_claim["refund"]["amount_paise"] == 3500

        # The other 6 shops have no staging_order_id -> "Simulated refund (no staging payment)"
        other_shops = [sid for sid in claims_by_shop if sid != "shop_01"]
        assert len(other_shops) == 6
        for sid in other_shops:
            c = claims_by_shop[sid]
            assert c["status"] == "paid_sim"
            assert c["refund"]["status"] == "SIMULATED"
            assert c["refund"]["label"] == "Simulated refund (no staging payment)"
            assert c["refund"]["amount_paise"] == 3500

        # Paytm HTTP transport was called ONLY for shop_01 (3 calls: txn status, refund apply, refund status)
        assert len(paytm_requests) == 3
        assert all(req[1]["body"]["orderId"] == "ORD-STG-SHOP-01" for req in paytm_requests)

    # Verify raw_response in DB is redacted for all 7 refunds (no checksum/signature/merchant_key)
    with container.db.session() as sess:
        for r in sess.scalars(select(Refund)):
            serialized = json.dumps(r.raw_response)
            assert "0123456789abcdef" not in serialized
            assert "SECRET_RESP_SIG_999" not in serialized
            assert '"signature"' not in serialized


@pytest.mark.anyio
async def test_staging_polls_three_times_then_marks_pending_at_paytm_and_handles_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll refund status up to 3 times; if still PENDING after 3 polls, record 'Pending at Paytm' (not an error)."""
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    status_polls = 0

    def _pending_handler(request: httpx.Request) -> httpx.Response:
        nonlocal status_polls
        if request.url.path.endswith("/v3/order/status"):
            return httpx.Response(
                200,
                json={
                    "body": {
                        "resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "01"},
                        "orderId": "ORD-STG-SHOP-01",
                        "txnId": "TXN-PENDING-POLL",
                        "txnAmount": "35.00",
                    }
                },
            )
        if request.url.path.endswith("/refund/apply"):
            return httpx.Response(
                200,
                json={
                    "body": {
                        "resultInfo": {"resultStatus": "PENDING", "resultCode": "601"},
                        "orderId": "ORD-STG-SHOP-01",
                        "refId": "SC-clm",
                        "refundId": "PAYTM-RFD-PEND",
                        "refundAmount": "35.00",
                    }
                },
            )
        status_polls += 1
        return httpx.Response(
            200,
            json={
                "body": {
                    "resultInfo": {"resultStatus": "PENDING", "resultCode": "601"},
                    "orderId": "ORD-STG-SHOP-01",
                    "refId": "SC-clm",
                    "refundId": "PAYTM-RFD-PEND",
                    "refundAmount": "35.00",
                }
            },
        )

    settings = _make_settings(
        demo_offline=False,
        paytm_mode="staging",
        paytm_mid="STAGE_MID_123",
        paytm_merchant_key="0123456789abcdef",
    )
    app = _create_test_app(tmp_path, settings=settings)
    container = app.state.container
    container.runtime.paytm_http_client = httpx.Client(
        transport=httpx.MockTransport(_pending_handler)
    )

    claim_id = "clm_20261021_shop_01_pend"
    with container.db.session() as sess:
        sess.add(
            Detection(
                id="det_20261021_shop_01_pend",
                shop_id="shop_01",
                day=date(2026, 10, 21),
                baseline_paise=420000,
                day_income_paise=0,
                dropped=True,
                eligible=True,
                quorum_share=0.75,
                rain_mm=85.0,
                rain_source="replay:open-meteo",
                decision="file",
                reason="flood_quorum_met",
                rules_version=RULES_VERSION,
            )
        )
        sess.flush()
        sess.add(
            Claim(
                id=claim_id,
                shop_id="shop_01",
                detection_id="det_20261021_shop_01_pend",
                status="approved",
                summary_text="Pending poll test.",
            )
        )

    res = await execute_claim_payback(container.runtime, claim_id)
    assert status_polls == 3
    assert res["status"] == "Pending at Paytm"
    assert res["label"] == "Pending at Paytm"

    with container.db.session() as sess:
        c_row = sess.get(Claim, claim_id)
        assert c_row is not None
        assert c_row.status == "approved"

    # Now test Paytm failure in a different month (2026-11) -> marks refund_failed, does not crash batch
    def _error_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    container.runtime.paytm_http_client = httpx.Client(
        transport=httpx.MockTransport(_error_handler)
    )
    fail_claim_id = "clm_20261105_shop_01_fail"
    with container.db.session() as sess:
        sess.add(
            Detection(
                id="det_20261105_shop_01_fail",
                shop_id="shop_01",
                day=date(2026, 11, 5),
                baseline_paise=420000,
                day_income_paise=0,
                dropped=True,
                eligible=True,
                quorum_share=0.75,
                rain_mm=85.0,
                rain_source="replay:open-meteo",
                decision="file",
                reason="flood_quorum_met",
                rules_version=RULES_VERSION,
            )
        )
        sess.flush()
        sess.add(
            Claim(
                id=fail_claim_id,
                shop_id="shop_01",
                detection_id="det_20261105_shop_01_fail",
                status="approved",
                summary_text="Failure test.",
            )
        )

    fail_res = await execute_claim_payback(container.runtime, fail_claim_id)
    assert fail_res["status"] == "refund_failed"
    assert fail_res["label"] == "Paytm staging unavailable"


@pytest.mark.anyio
async def test_metrics_endpoint_returns_receipt_and_eval_numbers(
    tmp_path: Path,
) -> None:
    """GET /api/metrics returns 0 forms, taps, time-to-file per claim, and Simulated eval metrics."""
    app = _create_test_app(tmp_path)
    container = app.state.container

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _run_oct21_and_tap_selvi(app, client)
        await client.post("/api/batches/batch_20261021/approve")
        await container.scenario.wait_for_payback("batch_20261021")

        metrics_res = await client.get("/api/metrics")
        assert metrics_res.status_code == 200
        m = metrics_res.json()

        assert m["forms_filled"] == 0
        assert m["taps"] == 7
        assert m["merchant_taps"] == 1
        assert m["adjuster_taps"] == 1
        assert m["claims_filed_in_run"] == 7
        assert len(m["time_to_file_by_claim"]) == 7
        assert all(item["seconds"] >= 0.0 for item in m["time_to_file_by_claim"])

        assert m["refunds"]["count"] == 7
        assert m["refunds"]["total_amount_paise"] == 7 * 3500

        eval_block = m["eval"]
        assert eval_block["label"] == "Simulated eval"
        assert eval_block["rules_version"] == RULES_VERSION
        assert eval_block["claims_filed"] == 18
        assert eval_block["claims_right"] == 17
        assert eval_block["closures_missed"] == 1
        assert eval_block["total_closures"] == 18
