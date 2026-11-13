"""Unit tests for Paytm staging client, guards, signing, idempotency, and redaction.

All tests run with zero network access. Covers Task C plus TESTING.md cases 12 and 14.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import paytmchecksum
import pytest

from app.config import Settings
from app.detector.config import PLAN_FEE_PAISE
from app.integrations.paytm import (
    INITIATE_TRANSACTION_PATH,
    PAYTM_GW_STAGE_HOST,
    PAYTM_PRIMARY_HOST,
    PENDING_DUMMY_KEY,
    PENDING_SIMULATED_LABEL,
    REFUND_APPLY_PATH,
    REFUND_STATUS_PATH,
    TRANSACTION_STATUS_PATH,
    PaytmClient,
    PaytmConfigError,
    PaytmUnavailableError,
    build_initiate_transaction_request,
    build_refund_id,
    build_refund_request,
    build_refund_status_request,
    build_transaction_status_request,
    plan_fee_rupees_str,
    probe_staging_endpoints,
    redact_paytm_payload,
    validate_paytm_config,
    validate_paytm_host,
    verify_paytm_signature,
)
from scripts.spikes import paytm_spike


@pytest.fixture(autouse=True)
def _forbid_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee no real socket / HTTP transport executes during unit tests."""

    def _blocked(*args: object, **kwargs: object) -> httpx.Response:
        msg = "Unit tests must never call the network"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)


def _staging_settings(
    *,
    host: str = f"https://{PAYTM_PRIMARY_HOST}",
    mid: str = "INTEGR_STAGE_MID",
    key: str = "STAGE_SECRET_16B",
) -> Settings:
    return Settings(
        demo_offline=False,
        paytm_mode="staging",
        paytm_host=host,
        paytm_mid=mid,
        paytm_merchant_key=key,
        paytm_website="WEBSTAGING",
    )


def _pending_settings(*, mid: str = "", key: str = "") -> Settings:
    return Settings(
        demo_offline=False,
        paytm_mode="pending",
        paytm_host=f"https://{PAYTM_PRIMARY_HOST}",
        paytm_mid=mid,
        paytm_merchant_key=key,
        paytm_website="WEBSTAGING",
    )


# --- Startup guard tests ---


@pytest.mark.parametrize(
    ("mode", "host"),
    [
        ("pending", f"https://{PAYTM_PRIMARY_HOST}"),
        ("pending", f"https://{PAYTM_GW_STAGE_HOST}"),
        ("staging", f"https://{PAYTM_PRIMARY_HOST}"),
        ("staging", f"https://{PAYTM_GW_STAGE_HOST}"),
    ],
)
def test_startup_guard_accepts_pending_or_staging_on_allowed_hosts(
    mode: str,
    host: str,
) -> None:
    settings = Settings(paytm_mode=mode, paytm_host=host)
    parsed_mode, parsed_host = validate_paytm_config(settings)
    assert parsed_mode == mode
    assert host.endswith(parsed_host)


@pytest.mark.parametrize("bad_mode", ["production", "prod", "live", "sandbox", "", "STAGING"])
def test_startup_guard_rejects_invalid_paytm_mode(bad_mode: str) -> None:
    settings = Settings(paytm_mode=bad_mode, paytm_host=f"https://{PAYTM_PRIMARY_HOST}")
    with pytest.raises(PaytmConfigError):
        validate_paytm_config(settings)


@pytest.mark.parametrize(
    "bad_host",
    [
        "https://secure.paytmpayments.com",
        "https://securegw.paytm.in",
        "https://securegw.paytmpayments.in",
        "http://securestage.paytmpayments.com",
        "https://securestage.paytmpayments.com:8443",
        "https://secure.paytmpayments.com@securestage.paytmpayments.com",
        "https://evil.example.com",
        "",
    ],
)
@pytest.mark.parametrize("mode", ["pending", "staging"])
def test_startup_guard_rejects_production_and_non_staging_hosts(
    mode: str,
    bad_host: str,
) -> None:
    settings = Settings(paytm_mode=mode, paytm_host=bad_host)
    with pytest.raises(PaytmConfigError):
        validate_paytm_config(settings)


# --- Request builders, signing, and fixed PLAN_FEE_PAISE amount ---


def test_request_builders_always_use_plan_fee_paise_and_valid_checksums() -> None:
    key = "STAGE_KEY_16BYTE"
    mid = "INTEGR_STAGE_MID"

    assert PLAN_FEE_PAISE == 3500
    assert plan_fee_rupees_str() == "35.00"

    init_req = build_initiate_transaction_request(
        order_id="ORD_FEE_01",
        cust_id="shop_01",
        mid=mid,
        merchant_key=key,
    )
    assert init_req.host == PAYTM_PRIMARY_HOST
    assert init_req.url.startswith(f"https://{PAYTM_PRIMARY_HOST}{INITIATE_TRANSACTION_PATH}")
    assert init_req.amount_paise == PLAN_FEE_PAISE
    assert init_req.payload["body"]["txnAmount"] == {"value": "35.00", "currency": "INR"}
    assert verify_paytm_signature(init_req.body_json, key, init_req.signature)

    status_req = build_transaction_status_request(order_id="ORD_FEE_01", mid=mid, merchant_key=key)
    assert status_req.host == PAYTM_GW_STAGE_HOST
    assert status_req.url == f"https://{PAYTM_GW_STAGE_HOST}{TRANSACTION_STATUS_PATH}"
    assert verify_paytm_signature(status_req.body_json, key, status_req.signature)

    refund_req = build_refund_request(
        order_id="ORD_FEE_01",
        txn_id="TXN_999",
        claim_id="clm_01",
        mid=mid,
        merchant_key=key,
    )
    assert refund_req.host == PAYTM_GW_STAGE_HOST
    assert refund_req.url == f"https://{PAYTM_GW_STAGE_HOST}{REFUND_APPLY_PATH}"
    assert refund_req.amount_paise == PLAN_FEE_PAISE
    assert refund_req.payload["body"]["txnType"] == "REFUND"
    assert refund_req.payload["body"]["refId"] == "SC-clm_01"
    assert refund_req.payload["body"]["refundAmount"] == "35.00"
    assert verify_paytm_signature(refund_req.body_json, key, refund_req.signature)

    ref_status_req = build_refund_status_request(
        order_id="ORD_FEE_01",
        claim_id="clm_01",
        mid=mid,
        merchant_key=key,
    )
    assert ref_status_req.host == PAYTM_GW_STAGE_HOST
    assert ref_status_req.url == f"https://{PAYTM_GW_STAGE_HOST}{REFUND_STATUS_PATH}"
    assert ref_status_req.payload["body"]["refId"] == "SC-clm_01"
    assert verify_paytm_signature(ref_status_req.body_json, key, ref_status_req.signature)


# --- Pending mode never sends HTTP, signs with dummy key, labels simulated ---


def test_pending_mode_signs_with_dummy_key_makes_zero_http_calls_and_labels_simulated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    http_calls: list[httpx.Request] = []

    def _unexpected_send(request: httpx.Request) -> httpx.Response:
        http_calls.append(request)
        msg = "Pending mode must never issue an HTTP call"
        raise AssertionError(msg)

    with httpx.Client(transport=httpx.MockTransport(_unexpected_send)) as mock_client:
        client = PaytmClient(settings=_pending_settings(), client=mock_client)

        r1 = client.initiate_plan_fee_payment(order_id="ORD_PEND_1", cust_id="shop_01")
        r2 = client.get_transaction_status(order_id="ORD_PEND_1")
        r3 = client.refund_plan_fee(
            order_id="ORD_PEND_1",
            txn_id=r2.txn_id or "TXN_1",
            claim_id="clm_pend",
        )
        r4 = client.get_refund_status(order_id="ORD_PEND_1", claim_id="clm_pend")

    assert http_calls == []
    for res in (r1, r2, r3, r4):
        assert res.simulated is True
        assert res.live is False
        assert res.mode == "simulated"
        assert res.label == PENDING_SIMULATED_LABEL
        assert res.amount_paise == PLAN_FEE_PAISE
        assert res.signature_present is True
        assert "signature" not in res.redacted_request.get("head", {})
        assert "signature" not in res.redacted_response.get("head", {})

    # Explicitly check dummy key produces a valid paytmchecksum signature when PAYTM_MERCHANT_KEY=""
    signed_req = build_refund_request(
        order_id="ORD_PEND_1",
        txn_id="TXN_1",
        claim_id="clm_pend",
        mid="PENDING_STAGING_MID",
        merchant_key=PENDING_DUMMY_KEY,
    )
    assert paytmchecksum.verifySignature(
        signed_req.body_json,
        PENDING_DUMMY_KEY,
        signed_req.signature,
    )


# --- Case 12: Refund ID idempotency at client level ---


def test_calling_refund_twice_for_one_claim_sends_one_refund_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    refund_posts: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        refund_posts.append(body)
        assert body["body"]["refId"] == "SC-clm_12"
        assert body["body"]["refundAmount"] == "35.00"
        return httpx.Response(
            200,
            json={
                "head": {"version": "v1", "signature": "SECRET_PAYTM_RESP_SIG"},
                "body": {
                    "mid": "INTEGR_STAGE_MID",
                    "orderId": "ORD_STAGE_12",
                    "txnId": "TXN_STAGE_12",
                    "refId": "SC-clm_12",
                    "refundId": "12345PAYTMREF",
                    "refundAmount": "35.00",
                    "resultInfo": {
                        "resultStatus": "PENDING",
                        "resultCode": "601",
                        "resultMsg": "Refund request was raised for this transaction.",
                    },
                },
            },
        )

    assert build_refund_id("clm_12") == "SC-clm_12"
    assert build_refund_id("SC-clm_12") == "SC-clm_12"
    assert build_refund_id(12) == "SC-12"

    with httpx.Client(transport=httpx.MockTransport(_handler)) as mock_client:
        client = PaytmClient(settings=_staging_settings(), client=mock_client)
        first = client.refund_plan_fee(
            order_id="ORD_STAGE_12",
            txn_id="TXN_STAGE_12",
            claim_id="clm_12",
        )
        second = client.refund_plan_fee(
            order_id="ORD_STAGE_12",
            txn_id="TXN_STAGE_12",
            claim_id="clm_12",
        )

    assert len(refund_posts) == 1
    assert first.deduplicated is False
    assert second.deduplicated is True
    assert first.refund_id == "SC-clm_12"
    assert second.refund_id == "SC-clm_12"
    assert first.amount_paise == PLAN_FEE_PAISE
    assert second.amount_paise == PLAN_FEE_PAISE


# --- Case 14: Redaction removes keys, checksums, and signatures ---


def test_redaction_removes_keys_checksums_and_signatures() -> None:
    secret_key = "SUPER_SECRET_16B"
    recorded_response = {
        "head": {
            "clientId": "C11",
            "responseTimestamp": "1567421120859",
            "signature": "WaFdplm36GmfBtZ6jPIFClLSEffhAk9fTpJ6i8WpgqiZvtUNl53mLL7mu4=",
            "version": "v1",
        },
        "body": {
            "mid": "INTEGR_STAGE_MID",
            "orderId": "ORD_35_01",
            "txnId": "202610210001",
            "refId": "SC-clm_14",
            "refundId": "PAYTM_REF_14",
            "refundAmount": "35.00",
            "CHECKSUMHASH": "CHECKSUM_HASH_SHOULD_VANISH",
            "merchantKey": secret_key,
            "nested": [
                {"checksum": "INNER_CHECKSUM", "api_key": "INNER_KEY", "ok": True},
            ],
            "debugNote": f"leaked key {secret_key} in text",
            "resultInfo": {
                "resultStatus": "TXN_SUCCESS",
                "resultCode": "10",
                "resultMsg": "Refund Successfull",
            },
        },
    }

    cleaned = redact_paytm_payload(recorded_response, secrets=(secret_key,))
    dumped = json.dumps(cleaned)

    assert "signature" not in cleaned["head"]
    assert "CHECKSUMHASH" not in cleaned["body"]
    assert "merchantKey" not in cleaned["body"]
    assert "checksum" not in cleaned["body"]["nested"][0]
    assert "api_key" not in cleaned["body"]["nested"][0]
    assert cleaned["body"]["nested"][0]["ok"] is True
    assert "WaFdplm36GmfBtZ6jPIFClLSEffhAk9fTpJ6i8WpgqiZvtUNl53mLL7mu4=" not in dumped
    assert "CHECKSUM_HASH_SHOULD_VANISH" not in dumped
    assert "INNER_CHECKSUM" not in dumped
    assert "INNER_KEY" not in dumped
    assert secret_key not in dumped
    assert cleaned["body"]["orderId"] == "ORD_35_01"
    assert cleaned["body"]["refId"] == "SC-clm_14"
    assert cleaned["body"]["refundAmount"] == "35.00"


# --- Alternate staging host retry & host logging ---


def test_staging_call_logs_host_and_retries_once_on_alternate_staging_host_on_404_or_connect_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    caplog.set_level(logging.INFO, logger="app.integrations.paytm")
    hosts_hit: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        hosts_hit.append(request.url.host)
        if request.url.host == PAYTM_GW_STAGE_HOST:
            return httpx.Response(404, json={"message": "Not found on gw-stage"})
        return httpx.Response(
            200,
            json={
                "head": {"version": "v1", "signature": "SIGN_TO_REDACT"},
                "body": {
                    "mid": "INTEGR_STAGE_MID",
                    "orderId": "ORD_RETRY_1",
                    "txnId": "TXN_RETRY_1",
                    "txnAmount": "35.00",
                    "resultInfo": {
                        "resultStatus": "TXN_SUCCESS",
                        "resultCode": "01",
                        "resultMsg": "Txn Success",
                    },
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(_handler)) as mock_client:
        client = PaytmClient(settings=_staging_settings(), client=mock_client)
        res = client.get_transaction_status(order_id="ORD_RETRY_1")

    assert hosts_hit == [PAYTM_GW_STAGE_HOST, PAYTM_PRIMARY_HOST]
    assert res.retried_on_alternate_host is True
    assert res.host == PAYTM_PRIMARY_HOST
    assert res.txn_id == "TXN_RETRY_1"
    assert res.live is True
    assert PAYTM_GW_STAGE_HOST in caplog.text
    assert PAYTM_PRIMARY_HOST in caplog.text
    assert "STAGE_SECRET_16B" not in caplog.text
    assert "SIGN_TO_REDACT" not in caplog.text


def test_staging_call_retries_once_on_connect_error_and_raises_if_both_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_OFFLINE", "0")
    hosts_hit: list[str] = []

    def _connect_error(request: httpx.Request) -> httpx.Response:
        hosts_hit.append(request.url.host)
        raise httpx.ConnectError("DNS lookup failed", request=request)

    with httpx.Client(transport=httpx.MockTransport(_connect_error)) as mock_client:
        client = PaytmClient(settings=_staging_settings(), client=mock_client)
        with pytest.raises(PaytmUnavailableError):
            client.get_transaction_status(order_id="ORD_FAIL_BOTH")

    assert hosts_hit == [PAYTM_GW_STAGE_HOST, PAYTM_PRIMARY_HOST]


# --- Probe and spike pending CLI checks ---


def test_probe_staging_endpoints_posts_empty_json_to_both_hosts() -> None:
    seen: list[tuple[str, str, bytes]] = []

    def _probe_handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.url.path, request.content))
        if request.url.path == TRANSACTION_STATUS_PATH:
            return httpx.Response(
                200,
                json={"head": {"version": "v1"}, "body": {"resultInfo": {"resultStatus": "F"}}},
            )
        return httpx.Response(404, text="<html>Not found</html>")

    with httpx.Client(transport=httpx.MockTransport(_probe_handler)) as mock_client:
        entries = probe_staging_endpoints(settings=_pending_settings(), client=mock_client)

    assert len(entries) == 8
    assert all(content == b"{}" for _, _, content in seen)
    status_entries = [e for e in entries if e.path == TRANSACTION_STATUS_PATH]
    assert len(status_entries) == 2
    assert all(e.paytm_json and e.http_status == 200 for e in status_entries)


def test_paytm_spike_pending_mode_prints_message_saves_redacted_json_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(paytm_spike, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(paytm_spike, "get_settings", _pending_settings)

    rc = paytm_spike.main([])
    captured = capsys.readouterr()

    assert rc == 0
    assert "pending: keys not set" in captured.out
    saved = json.loads((tmp_path / "paytm_spike.json").read_text(encoding="utf-8"))
    assert saved["label"] == PENDING_SIMULATED_LABEL
    assert len(saved["steps"]) == 4
    dumped = json.dumps(saved)
    assert PENDING_DUMMY_KEY not in dumped
    assert "CHECKSUMHASH" not in dumped
    for step in saved["steps"]:
        result = step["result"]
        assert result["signature_present"] is True
        assert result["amount_paise"] == PLAN_FEE_PAISE
        assert "signature" not in result["redacted_request"].get("head", {})
        assert "signature" not in result["redacted_response"].get("head", {})


def test_paytm_spike_create_pending_and_staging_html(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(paytm_spike, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(paytm_spike, "get_settings", _pending_settings)

    rc = paytm_spike.main(["--create", "--order-id", "SC_FEE_PEND"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "pending: keys not set" in captured.out
    create_json = json.loads((tmp_path / "paytm_create.json").read_text(encoding="utf-8"))
    assert create_json["result"]["order_id"] == "SC_FEE_PEND"
    assert create_json["result"]["amount_paise"] == PLAN_FEE_PAISE
    assert "signature" not in create_json["result"]["redacted_request"].get("head", {})


def test_js_checkout_html_uses_staging_script_and_contains_no_secret_key(tmp_path: Path) -> None:
    out = paytm_spike._write_js_checkout_html(
        path=tmp_path / "paytm_checkout.html",
        mid="INTEGR_STAGE_MID",
        order_id="SC_FEE_1",
        txn_token="TXN_TOK_ABC",
    )
    html_text = out.read_text(encoding="utf-8")
    assert (
        f"https://{PAYTM_PRIMARY_HOST}/merchantpgpui/checkoutjs/merchants/INTEGR_STAGE_MID.js"
        in html_text
    )
    assert '"amount": "35.00"' in html_text
    assert '"token": "TXN_TOK_ABC"' in html_text
    assert PENDING_DUMMY_KEY not in html_text


def test_validate_paytm_host_rejects_production_even_on_probe() -> None:
    with pytest.raises(PaytmConfigError):
        validate_paytm_host("https://secure.paytmpayments.com")
