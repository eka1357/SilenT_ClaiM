"""Paytm Payment Gateway staging client, checksum signing, redaction, and guards.

Written directly from Paytm's official developer docs (https://www.paytmpayments.com/docs):
- Initiate Transaction: POST https://securestage.paytmpayments.com/theia/api/v1/initiateTransaction
- Transaction Status (v3): POST https://securegw-stage.paytmpayments.in/v3/order/status
- Refund Apply: POST https://securegw-stage.paytmpayments.in/refund/apply
- Refund Status (v2): POST https://securegw-stage.paytmpayments.in/v2/refund/status

Money safety rules (docs/SECURITY.md, .agents/rules/money-safety.md):
- Startup guard permits PAYTM_MODE in {"pending", "staging"} and ONLY Paytm's two documented
  staging hosts (never production).
- In `pending` mode, every request is built and signed with `paytmchecksum` (using a fixed dummy
  key if PAYTM_MERCHANT_KEY is empty) and NEVER sent; responses are labelled
  "Simulated: keys pending".
- Amount is fixed exclusively from detector.config.PLAN_FEE_PAISE (3500 -> "35.00" INR).
- Refund refId is deterministically SC-{claim_id}; client tracks seen refunds for idempotency.
- Keys, checksums, and signatures are stripped before logging or persisting payloads.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
import paytmchecksum

from app.config import Settings, get_settings, is_offline
from app.detector.config import PLAN_FEE_PAISE
from app.integrations.replay import (
    FIXTURES_DIR,
    HealthCallback,
    load_paytm_fixture,
)

logger = logging.getLogger(__name__)

PaytmMode = Literal["pending", "staging"]
PaytmResultMode = Literal["simulated", "live", "replay"]

PAYTM_PRIMARY_HOST = "securestage.paytmpayments.com"
PAYTM_GW_STAGE_HOST = "securegw-stage.paytmpayments.in"
ALLOWED_PAYTM_STAGING_HOSTS: frozenset[str] = frozenset({PAYTM_PRIMARY_HOST, PAYTM_GW_STAGE_HOST})

INITIATE_TRANSACTION_PATH = "/theia/api/v1/initiateTransaction"
TRANSACTION_STATUS_PATH = "/v3/order/status"
REFUND_APPLY_PATH = "/refund/apply"
REFUND_STATUS_PATH = "/v2/refund/status"

DOCUMENTED_API_HOSTS: dict[str, str] = {
    INITIATE_TRANSACTION_PATH: PAYTM_PRIMARY_HOST,
    TRANSACTION_STATUS_PATH: PAYTM_GW_STAGE_HOST,
    REFUND_APPLY_PATH: PAYTM_GW_STAGE_HOST,
    REFUND_STATUS_PATH: PAYTM_GW_STAGE_HOST,
}

PENDING_SIMULATED_LABEL = "Simulated: keys pending"
LIVE_LABEL = "Live"
REPLAY_LABEL = "Replay"

PENDING_DUMMY_MID = "PENDING_STAGING_MID"
# AES-128-CBC inside paytmchecksum requires a 16-, 24-, or 32-byte UTF-8 key.
PENDING_DUMMY_KEY = "PENDING_DUMMY_16"

_SENSITIVE_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "key",
        "apikey",
        "api_key",
        "merchantkey",
        "merchant_key",
        "paytmmerchantkey",
        "paytm_merchant_key",
        "secret",
        "secretkey",
        "secret_key",
        "signature",
        "checksum",
        "checksumhash",
        "paytmchecksum",
        "xsignature",
        "x_signature",
        "authorization",
    }
)


class PaytmConfigError(ValueError):
    """Raised when Paytm mode or host violates the staging-only safety guard."""


class PaytmUnavailableError(RuntimeError):
    """Raised when a staging call or offline fixture cannot complete."""


@dataclass(frozen=True, slots=True)
class PaytmSignedRequest:
    """Built and signed Paytm API request payload prior to transport."""

    operation: str
    host: str
    path: str
    url: str
    payload: dict[str, Any]
    body_json: str
    signature: str
    amount_paise: int


@dataclass(frozen=True, slots=True)
class PaytmCallResult:
    """Normalized outcome from initiate, status, refund, or refund-status calls."""

    operation: str
    mode: PaytmResultMode
    live: bool
    simulated: bool
    label: str
    host: str
    url: str
    order_id: str
    refund_id: str | None
    txn_id: str | None
    txn_token: str | None
    amount_paise: int
    status: str
    result_code: str | None
    result_msg: str | None
    http_status: int | None
    retried_on_alternate_host: bool
    deduplicated: bool
    signature_present: bool
    redacted_request: dict[str, Any]
    redacted_response: dict[str, Any]
    latency_ms: int


@dataclass(frozen=True, slots=True)
class PaytmProbeEntry:
    """Single-target result from probing Paytm staging paths."""

    host: str
    path: str
    url: str
    reachable: bool
    http_status: int | None
    paytm_json: bool
    error: str | None
    redacted_response: dict[str, Any] | None
    latency_ms: int


def plan_fee_rupees_str() -> str:
    """Return the fixed plan-fee INR string formatted strictly from PLAN_FEE_PAISE."""
    return f"{PLAN_FEE_PAISE / 100:.2f}"


def validate_paytm_host(host_or_url: str) -> str:
    """Validate that a Paytm URL uses HTTPS on one of the two staging hosts only."""
    candidate = host_or_url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.hostname not in ALLOWED_PAYTM_STAGING_HOSTS
    ):
        allowed = ", ".join(sorted(ALLOWED_PAYTM_STAGING_HOSTS))
        msg = (
            "Refusing non-staging Paytm host; PAYTM_HOST must use https on one of "
            f"[{allowed}], got {host_or_url!r}"
        )
        raise PaytmConfigError(msg)
    return parsed.hostname


def validate_paytm_config(settings: Settings | None = None) -> tuple[PaytmMode, str]:
    """Startup guard: enforce pending/staging mode and staging-only hostnames."""
    cfg = settings or get_settings()
    mode = cfg.paytm_mode.strip()
    if mode not in {"pending", "staging"}:
        msg = f"Invalid PAYTM_MODE={cfg.paytm_mode!r}; expected 'pending' or 'staging'"
        raise PaytmConfigError(msg)
    host = validate_paytm_host(cfg.paytm_host)
    return mode, host  # type: ignore[return-value]


def _alternate_staging_host(host: str) -> str:
    validate_paytm_host(host)
    return PAYTM_GW_STAGE_HOST if host == PAYTM_PRIMARY_HOST else PAYTM_PRIMARY_HOST


def build_refund_id(claim_id: str | int) -> str:
    """Return deterministic idempotency refund reference SC-{claim_id}."""
    clean_id = str(claim_id).strip()
    if not clean_id:
        msg = "claim_id must not be empty"
        raise ValueError(msg)
    refund_id = clean_id if clean_id.startswith("SC-") else f"SC-{clean_id}"
    if len(refund_id) > 50:
        msg = f"Paytm refId exceeds 50 chars: {refund_id!r}"
        raise ValueError(msg)
    return refund_id


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return normalized.endswith(
        ("_key", "checksum", "checksumhash", "signature")
    ) and normalized not in {"paymentmode"}


def redact_paytm_payload(
    value: Any,
    *,
    secrets: Iterable[str] = (),
) -> Any:
    """Recursively remove keys, checksums, and signatures from dicts/lists/strings."""
    non_empty_secrets = [s for s in secrets if s]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            if _is_sensitive_key(str(k)):
                continue
            cleaned[k] = redact_paytm_payload(v, secrets=non_empty_secrets)
        return cleaned
    if isinstance(value, list):
        return [redact_paytm_payload(item, secrets=non_empty_secrets) for item in value]
    if isinstance(value, str):
        sanitized = value
        for secret in non_empty_secrets:
            if secret in sanitized:
                sanitized = sanitized.replace(secret, "[REDACTED]")
        return sanitized
    return value


def _build_endpoint_url(
    *,
    host: str,
    path: str,
    query: dict[str, str] | None = None,
) -> str:
    verified_host = validate_paytm_host(host)
    base = f"https://{verified_host}{path}"
    if query:
        req = httpx.Request("POST", base, params=query)
        return str(req.url)
    return base


def _sign_body(body: dict[str, Any], merchant_key: str) -> tuple[str, str]:
    body_json = json.dumps(body)
    signature = str(paytmchecksum.generateSignature(body_json, merchant_key))
    return body_json, signature


def build_initiate_transaction_request(
    *,
    order_id: str,
    cust_id: str,
    mid: str,
    merchant_key: str,
    website_name: str = "WEBSTAGING",
    callback_url: str | None = None,
    host: str = PAYTM_PRIMARY_HOST,
) -> PaytmSignedRequest:
    """Build and sign Initiate Transaction API request for fixed Rs 35 plan fee."""
    clean_order_id = order_id.strip()
    clean_cust_id = cust_id.strip()
    if not clean_order_id or not clean_cust_id:
        msg = "order_id and cust_id must be non-empty"
        raise ValueError(msg)
    verified_host = validate_paytm_host(host)
    body: dict[str, Any] = {
        "requestType": "Payment",
        "mid": mid,
        "websiteName": website_name,
        "orderId": clean_order_id,
        "callbackUrl": callback_url
        or f"https://{PAYTM_PRIMARY_HOST}/theia/paytmCallback?ORDER_ID={clean_order_id}",
        "txnAmount": {
            "value": plan_fee_rupees_str(),
            "currency": "INR",
        },
        "userInfo": {
            "custId": clean_cust_id,
        },
    }
    body_json, signature = _sign_body(body, merchant_key)
    payload: dict[str, Any] = {
        "body": body,
        "head": {"signature": signature},
    }
    url = _build_endpoint_url(
        host=verified_host,
        path=INITIATE_TRANSACTION_PATH,
        query={"mid": mid, "orderId": clean_order_id},
    )
    return PaytmSignedRequest(
        operation="initiate_transaction",
        host=verified_host,
        path=INITIATE_TRANSACTION_PATH,
        url=url,
        payload=payload,
        body_json=body_json,
        signature=signature,
        amount_paise=PLAN_FEE_PAISE,
    )


def build_transaction_status_request(
    *,
    order_id: str,
    mid: str,
    merchant_key: str,
    host: str = PAYTM_GW_STAGE_HOST,
) -> PaytmSignedRequest:
    """Build and sign Paytm Transaction Status API (v3/order/status) request."""
    clean_order_id = order_id.strip()
    if not clean_order_id:
        msg = "order_id must be non-empty"
        raise ValueError(msg)
    verified_host = validate_paytm_host(host)
    body: dict[str, Any] = {
        "mid": mid,
        "orderId": clean_order_id,
    }
    body_json, signature = _sign_body(body, merchant_key)
    payload: dict[str, Any] = {
        "body": body,
        "head": {"signature": signature},
    }
    url = _build_endpoint_url(host=verified_host, path=TRANSACTION_STATUS_PATH)
    return PaytmSignedRequest(
        operation="transaction_status",
        host=verified_host,
        path=TRANSACTION_STATUS_PATH,
        url=url,
        payload=payload,
        body_json=body_json,
        signature=signature,
        amount_paise=PLAN_FEE_PAISE,
    )


def build_refund_request(
    *,
    order_id: str,
    txn_id: str,
    claim_id: str | int,
    mid: str,
    merchant_key: str,
    host: str = PAYTM_GW_STAGE_HOST,
) -> PaytmSignedRequest:
    """Build and sign Paytm Refund API (/refund/apply) for Rs 35 and SC-{claim_id}."""
    clean_order_id = order_id.strip()
    clean_txn_id = txn_id.strip()
    if not clean_order_id or not clean_txn_id:
        msg = "order_id and txn_id must be non-empty"
        raise ValueError(msg)
    verified_host = validate_paytm_host(host)
    refund_id = build_refund_id(claim_id)
    body: dict[str, Any] = {
        "mid": mid,
        "txnType": "REFUND",
        "orderId": clean_order_id,
        "txnId": clean_txn_id,
        "refId": refund_id,
        "refundAmount": plan_fee_rupees_str(),
    }
    body_json, signature = _sign_body(body, merchant_key)
    payload: dict[str, Any] = {
        "body": body,
        "head": {"signature": signature},
    }
    url = _build_endpoint_url(host=verified_host, path=REFUND_APPLY_PATH)
    return PaytmSignedRequest(
        operation="refund",
        host=verified_host,
        path=REFUND_APPLY_PATH,
        url=url,
        payload=payload,
        body_json=body_json,
        signature=signature,
        amount_paise=PLAN_FEE_PAISE,
    )


def build_refund_status_request(
    *,
    order_id: str,
    claim_id: str | int,
    mid: str,
    merchant_key: str,
    host: str = PAYTM_GW_STAGE_HOST,
) -> PaytmSignedRequest:
    """Build and sign Paytm Refund Status API (v2/refund/status) for SC-{claim_id}."""
    clean_order_id = order_id.strip()
    if not clean_order_id:
        msg = "order_id must be non-empty"
        raise ValueError(msg)
    verified_host = validate_paytm_host(host)
    refund_id = build_refund_id(claim_id)
    body: dict[str, Any] = {
        "mid": mid,
        "orderId": clean_order_id,
        "refId": refund_id,
    }
    body_json, signature = _sign_body(body, merchant_key)
    payload: dict[str, Any] = {
        "body": body,
        "head": {"signature": signature},
    }
    url = _build_endpoint_url(host=verified_host, path=REFUND_STATUS_PATH)
    return PaytmSignedRequest(
        operation="refund_status",
        host=verified_host,
        path=REFUND_STATUS_PATH,
        url=url,
        payload=payload,
        body_json=body_json,
        signature=signature,
        amount_paise=PLAN_FEE_PAISE,
    )


def verify_paytm_signature(
    params_or_body: dict[str, Any] | str,
    merchant_key: str,
    signature: str | None = None,
) -> bool:
    """Verify a Paytm callback dict (with CHECKSUMHASH) or JSON body signature."""
    if isinstance(params_or_body, dict):
        # Copy before calling paytmchecksum.verifySignature because it mutates CHECKSUMHASH.
        params_copy = dict(params_or_body)
        if signature is None and "CHECKSUMHASH" in params_copy:
            checksum = str(params_copy.pop("CHECKSUMHASH"))
        elif signature is not None:
            checksum = signature
            params_copy.pop("CHECKSUMHASH", None)
        else:
            return False
        return bool(paytmchecksum.verifySignature(params_copy, merchant_key, checksum))
    if not signature:
        return False
    return bool(paytmchecksum.verifySignature(params_or_body, merchant_key, signature))


def _resolve_signing_credentials(settings: Settings, mode: PaytmMode) -> tuple[str, str]:
    mid = settings.paytm_mid.strip()
    key = settings.paytm_merchant_key.get_secret_value().strip()
    if mode == "pending":
        return mid or PENDING_DUMMY_MID, key or PENDING_DUMMY_KEY
    if not mid or not key:
        msg = "PAYTM_MID and PAYTM_MERCHANT_KEY must be set in PAYTM_MODE=staging"
        raise PaytmUnavailableError(msg)
    return mid, key


def _emit_health(callback: HealthCallback | None, mode: Literal["live", "replay", "down"]) -> None:
    if callback is not None:
        callback("paytm", mode)


def _extract_response_fields(
    payload: dict[str, Any],
) -> tuple[str, str | None, str | None, str | None, str | None, bool]:
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
    result_info = body.get("resultInfo") if isinstance(body.get("resultInfo"), dict) else {}
    status = str(result_info.get("resultStatus") or body.get("status") or "UNKNOWN")
    code = str(result_info["resultCode"]) if result_info.get("resultCode") is not None else None
    msg = str(result_info["resultMsg"]) if result_info.get("resultMsg") is not None else None
    txn_id = str(body["txnId"]) if body.get("txnId") else None
    txn_token = str(body["txnToken"]) if body.get("txnToken") else None
    sig_present = bool(head.get("signature"))
    return status, code, msg, txn_id, txn_token, sig_present


def _simulated_pending_response(
    signed_req: PaytmSignedRequest,
    *,
    order_id: str,
    refund_id: str | None,
    txn_id: str | None,
    merchant_key: str,
) -> PaytmCallResult:
    op = signed_req.operation
    body: dict[str, Any] = {
        "mid": signed_req.payload["body"]["mid"],
        "orderId": order_id,
        "resultInfo": {
            "resultStatus": "SIMULATED",
            "resultCode": "PENDING_KEYS",
            "resultMsg": PENDING_SIMULATED_LABEL,
        },
        "simulated": True,
        "label": PENDING_SIMULATED_LABEL,
    }
    txn_token: str | None = None
    out_txn_id: str | None = txn_id
    if op == "initiate_transaction":
        txn_token = f"SIM_TXN_TOKEN_{order_id}"
        body["txnToken"] = txn_token
        body["txnAmount"] = plan_fee_rupees_str()
    elif op == "transaction_status":
        out_txn_id = f"SIM_TXN_{order_id}"
        body["txnId"] = out_txn_id
        body["txnAmount"] = plan_fee_rupees_str()
    elif op in {"refund", "refund_status"}:
        out_txn_id = txn_id or f"SIM_TXN_{order_id}"
        body["txnId"] = out_txn_id
        body["refId"] = refund_id
        body["refundId"] = f"SIM_PAYTM_{refund_id}"
        body["refundAmount"] = plan_fee_rupees_str()

    raw_response: dict[str, Any] = {
        "head": {"version": "v1", "signature": signed_req.signature},
        "body": body,
    }
    return PaytmCallResult(
        operation=op,
        mode="simulated",
        live=False,
        simulated=True,
        label=PENDING_SIMULATED_LABEL,
        host=signed_req.host,
        url=signed_req.url,
        order_id=order_id,
        refund_id=refund_id,
        txn_id=out_txn_id,
        txn_token=txn_token,
        amount_paise=PLAN_FEE_PAISE,
        status="SIMULATED",
        result_code="PENDING_KEYS",
        result_msg=PENDING_SIMULATED_LABEL,
        http_status=None,
        retried_on_alternate_host=False,
        deduplicated=False,
        signature_present=bool(signed_req.signature),
        redacted_request=redact_paytm_payload(signed_req.payload, secrets=(merchant_key,)),
        redacted_response=redact_paytm_payload(raw_response, secrets=(merchant_key,)),
        latency_ms=0,
    )


def _with_deduplicated_flag(result: PaytmCallResult) -> PaytmCallResult:
    return PaytmCallResult(
        operation=result.operation,
        mode=result.mode,
        live=result.live,
        simulated=result.simulated,
        label=result.label,
        host=result.host,
        url=result.url,
        order_id=result.order_id,
        refund_id=result.refund_id,
        txn_id=result.txn_id,
        txn_token=result.txn_token,
        amount_paise=result.amount_paise,
        status=result.status,
        result_code=result.result_code,
        result_msg=result.result_msg,
        http_status=result.http_status,
        retried_on_alternate_host=result.retried_on_alternate_host,
        deduplicated=True,
        signature_present=result.signature_present,
        redacted_request=result.redacted_request,
        redacted_response=result.redacted_response,
        latency_ms=result.latency_ms,
    )


def _replay_paytm_result(
    signed_req: PaytmSignedRequest,
    *,
    order_id: str,
    refund_id: str | None,
    txn_id: str | None,
    merchant_key: str,
    fixtures_dir: Any,
    health_callback: HealthCallback | None,
) -> PaytmCallResult | None:
    fixture = load_paytm_fixture(
        signed_req.operation,
        order_id=order_id,
        refund_id=refund_id,
        fixtures_dir=fixtures_dir,
    )
    if fixture is None:
        return None
    status, code, msg, parsed_txn_id, txn_token, sig_present = _extract_response_fields(fixture)
    _emit_health(health_callback, "replay")
    return PaytmCallResult(
        operation=signed_req.operation,
        mode="replay",
        live=False,
        simulated=False,
        label=REPLAY_LABEL,
        host=signed_req.host,
        url=signed_req.url,
        order_id=order_id,
        refund_id=refund_id,
        txn_id=parsed_txn_id or txn_id,
        txn_token=txn_token,
        amount_paise=PLAN_FEE_PAISE,
        status=status,
        result_code=code,
        result_msg=msg,
        http_status=200,
        retried_on_alternate_host=False,
        deduplicated=False,
        signature_present=sig_present,
        redacted_request=redact_paytm_payload(signed_req.payload, secrets=(merchant_key,)),
        redacted_response=redact_paytm_payload(fixture, secrets=(merchant_key,)),
        latency_ms=0,
    )


@dataclass(slots=True)
class PaytmClient:
    """Paytm Payment Gateway staging client with client-level refund idempotency."""

    settings: Settings | None = None
    client: httpx.Client | None = None
    fixtures_dir: Any = FIXTURES_DIR
    health_callback: HealthCallback | None = None
    _seen_refunds: dict[str, PaytmCallResult] = field(default_factory=dict)

    def _effective_settings(self) -> Settings:
        return self.settings or get_settings()

    def _execute(
        self,
        builder_fn: Any,
        *,
        primary_host: str,
        order_id: str,
        refund_id: str | None = None,
        txn_id: str | None = None,
    ) -> PaytmCallResult:
        cfg = self._effective_settings()
        mode, _ = validate_paytm_config(cfg)
        mid, merchant_key = _resolve_signing_credentials(cfg, mode)
        signed_req: PaytmSignedRequest = builder_fn(primary_host, mid, merchant_key)

        if mode == "pending":
            logger.info(
                "paytm call: op=%s mode=pending host=%s order_id=%s refund_id=%s label=%s",
                signed_req.operation,
                signed_req.host,
                order_id,
                refund_id or "-",
                PENDING_SIMULATED_LABEL,
            )
            return _simulated_pending_response(
                signed_req,
                order_id=order_id,
                refund_id=refund_id,
                txn_id=txn_id,
                merchant_key=merchant_key,
            )

        if is_offline(cfg):
            replayed = _replay_paytm_result(
                signed_req,
                order_id=order_id,
                refund_id=refund_id,
                txn_id=txn_id,
                merchant_key=merchant_key,
                fixtures_dir=self.fixtures_dir,
                health_callback=self.health_callback,
            )
            if replayed is not None:
                return replayed
            msg = f"DEMO_OFFLINE=1 and no Paytm fixture recorded for {signed_req.operation}"
            raise PaytmUnavailableError(msg)

        t0 = time.perf_counter()
        alt_host = _alternate_staging_host(signed_req.host)
        hosts_to_try = [signed_req.host, alt_host]
        retried = False
        last_exc: Exception | None = None
        last_404_resp: httpx.Response | None = None

        own_client = self.client is None
        http = self.client or httpx.Client(timeout=cfg.request_timeout_s)
        try:
            for attempt_idx, host in enumerate(hosts_to_try):
                req_obj = signed_req if attempt_idx == 0 else builder_fn(host, mid, merchant_key)
                validate_paytm_host(req_obj.url)
                logger.info(
                    "paytm call: op=%s mode=staging attempt=%d host=%s order_id=%s refund_id=%s",
                    req_obj.operation,
                    attempt_idx + 1,
                    req_obj.host,
                    order_id,
                    refund_id or "-",
                )
                try:
                    resp = http.post(
                        req_obj.url,
                        content=json.dumps(req_obj.payload),
                        headers={"Content-Type": "application/json"},
                    )
                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                    last_exc = exc
                    if attempt_idx == 0:
                        retried = True
                        logger.warning(
                            "paytm transport error (%s) on host=%s; retrying on host=%s",
                            type(exc).__name__,
                            req_obj.host,
                            alt_host,
                        )
                        continue
                    _emit_health(self.health_callback, "down")
                    msg = f"Paytm {req_obj.operation} failed on both staging hosts: {exc}"
                    raise PaytmUnavailableError(msg) from exc
                except httpx.HTTPError as exc:
                    _emit_health(self.health_callback, "down")
                    msg = f"Paytm {req_obj.operation} HTTP error on {req_obj.host}: {exc}"
                    raise PaytmUnavailableError(msg) from exc

                if resp.status_code == 404 and attempt_idx == 0:
                    last_404_resp = resp
                    retried = True
                    logger.warning(
                        "paytm HTTP 404 on host=%s for op=%s; retrying on host=%s",
                        req_obj.host,
                        req_obj.operation,
                        alt_host,
                    )
                    continue

                if resp.status_code >= 400:
                    _emit_health(self.health_callback, "down")
                    msg = (
                        f"Paytm {req_obj.operation} returned HTTP {resp.status_code} "
                        f"from {req_obj.host}"
                    )
                    raise PaytmUnavailableError(msg)

                raw_json = resp.json()
                status, code, msg_txt, parsed_txn_id, txn_token, sig_present = (
                    _extract_response_fields(raw_json)
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                _emit_health(self.health_callback, "live")
                return PaytmCallResult(
                    operation=req_obj.operation,
                    mode="live",
                    live=True,
                    simulated=False,
                    label=LIVE_LABEL,
                    host=req_obj.host,
                    url=req_obj.url,
                    order_id=order_id,
                    refund_id=refund_id,
                    txn_id=parsed_txn_id or txn_id,
                    txn_token=txn_token,
                    amount_paise=PLAN_FEE_PAISE,
                    status=status,
                    result_code=code,
                    result_msg=msg_txt,
                    http_status=resp.status_code,
                    retried_on_alternate_host=retried,
                    deduplicated=False,
                    signature_present=sig_present,
                    redacted_request=redact_paytm_payload(req_obj.payload, secrets=(merchant_key,)),
                    redacted_response=redact_paytm_payload(raw_json, secrets=(merchant_key,)),
                    latency_ms=latency_ms,
                )
        finally:
            if own_client:
                http.close()

        _emit_health(self.health_callback, "down")
        if last_404_resp is not None:
            msg = f"Paytm {signed_req.operation} returned HTTP 404 on both staging hosts"
            raise PaytmUnavailableError(msg)
        msg = f"Paytm {signed_req.operation} failed: {last_exc}"
        raise PaytmUnavailableError(msg)

    def initiate_plan_fee_payment(
        self,
        *,
        order_id: str,
        cust_id: str,
        callback_url: str | None = None,
    ) -> PaytmCallResult:
        """Initiate a Rs 35 plan-fee payment transaction on Paytm staging."""
        cfg = self._effective_settings()
        return self._execute(
            lambda host, mid, key: build_initiate_transaction_request(
                order_id=order_id,
                cust_id=cust_id,
                mid=mid,
                merchant_key=key,
                website_name=cfg.paytm_website,
                callback_url=callback_url,
                host=host,
            ),
            primary_host=DOCUMENTED_API_HOSTS[INITIATE_TRANSACTION_PATH],
            order_id=order_id.strip(),
        )

    def get_transaction_status(self, *, order_id: str) -> PaytmCallResult:
        """Fetch Paytm transaction status (v3/order/status) for an order."""
        return self._execute(
            lambda host, mid, key: build_transaction_status_request(
                order_id=order_id,
                mid=mid,
                merchant_key=key,
                host=host,
            ),
            primary_host=DOCUMENTED_API_HOSTS[TRANSACTION_STATUS_PATH],
            order_id=order_id.strip(),
        )

    def refund_plan_fee(
        self,
        *,
        order_id: str,
        txn_id: str,
        claim_id: str | int,
    ) -> PaytmCallResult:
        """Issue an idempotent Rs 35 plan-fee refund for SC-{claim_id}."""
        validate_paytm_config(self._effective_settings())
        refund_id = build_refund_id(claim_id)
        if refund_id in self._seen_refunds:
            logger.info(
                "paytm refund deduplicated at client: refund_id=%s order_id=%s",
                refund_id,
                order_id.strip(),
            )
            return _with_deduplicated_flag(self._seen_refunds[refund_id])

        result = self._execute(
            lambda host, mid, key: build_refund_request(
                order_id=order_id,
                txn_id=txn_id,
                claim_id=claim_id,
                mid=mid,
                merchant_key=key,
                host=host,
            ),
            primary_host=DOCUMENTED_API_HOSTS[REFUND_APPLY_PATH],
            order_id=order_id.strip(),
            refund_id=refund_id,
            txn_id=txn_id.strip(),
        )
        self._seen_refunds[refund_id] = result
        return result

    def get_refund_status(
        self,
        *,
        order_id: str,
        claim_id: str | int,
    ) -> PaytmCallResult:
        """Poll Paytm refund status (v2/refund/status) for SC-{claim_id}."""
        refund_id = build_refund_id(claim_id)
        return self._execute(
            lambda host, mid, key: build_refund_status_request(
                order_id=order_id,
                claim_id=claim_id,
                mid=mid,
                merchant_key=key,
                host=host,
            ),
            primary_host=DOCUMENTED_API_HOSTS[REFUND_STATUS_PATH],
            order_id=order_id.strip(),
            refund_id=refund_id,
        )


def probe_staging_endpoints(
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[PaytmProbeEntry]:
    """POST `{}` to all four documented Paytm paths across both staging hosts.

    Always guarded to ALLOWED_PAYTM_STAGING_HOSTS only, never production.
    """
    cfg = settings or get_settings()
    validate_paytm_config(cfg)
    secret = cfg.paytm_merchant_key.get_secret_value().strip()
    targets: list[tuple[str, str]] = [
        (host, path)
        for path in DOCUMENTED_API_HOSTS
        for host in (PAYTM_PRIMARY_HOST, PAYTM_GW_STAGE_HOST)
    ]

    entries: list[PaytmProbeEntry] = []
    own_client = client is None
    http = client or httpx.Client(timeout=cfg.request_timeout_s)
    try:
        for host, path in targets:
            url = _build_endpoint_url(host=host, path=path)
            logger.info("paytm probe: host=%s path=%s", host, path)
            t0 = time.perf_counter()
            try:
                resp = http.post(url, json={}, headers={"Content-Type": "application/json"})
                latency_ms = int((time.perf_counter() - t0) * 1000)
                parsed_json: dict[str, Any] | None = None
                paytm_json = False
                try:
                    raw = resp.json()
                    if isinstance(raw, dict):
                        parsed_json = redact_paytm_payload(raw, secrets=(secret,))
                        paytm_json = any(k in raw for k in ("head", "body", "resultInfo", "status"))
                except ValueError:
                    parsed_json = None
                entries.append(
                    PaytmProbeEntry(
                        host=host,
                        path=path,
                        url=url,
                        reachable=True,
                        http_status=resp.status_code,
                        paytm_json=paytm_json,
                        error=None,
                        redacted_response=parsed_json,
                        latency_ms=latency_ms,
                    )
                )
            except httpx.HTTPError as exc:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                entries.append(
                    PaytmProbeEntry(
                        host=host,
                        path=path,
                        url=url,
                        reachable=False,
                        http_status=None,
                        paytm_json=False,
                        error=f"{type(exc).__name__}: {exc}",
                        redacted_response=None,
                        latency_ms=latency_ms,
                    )
                )
    finally:
        if own_client:
            http.close()
    return entries


__all__ = [
    "ALLOWED_PAYTM_STAGING_HOSTS",
    "DOCUMENTED_API_HOSTS",
    "INITIATE_TRANSACTION_PATH",
    "LIVE_LABEL",
    "PAYTM_GW_STAGE_HOST",
    "PAYTM_PRIMARY_HOST",
    "PENDING_DUMMY_KEY",
    "PENDING_DUMMY_MID",
    "PENDING_SIMULATED_LABEL",
    "REFUND_APPLY_PATH",
    "REFUND_STATUS_PATH",
    "REPLAY_LABEL",
    "TRANSACTION_STATUS_PATH",
    "PaytmCallResult",
    "PaytmClient",
    "PaytmConfigError",
    "PaytmMode",
    "PaytmProbeEntry",
    "PaytmResultMode",
    "PaytmSignedRequest",
    "PaytmUnavailableError",
    "build_initiate_transaction_request",
    "build_refund_id",
    "build_refund_request",
    "build_refund_status_request",
    "build_transaction_status_request",
    "plan_fee_rupees_str",
    "probe_staging_endpoints",
    "redact_paytm_payload",
    "validate_paytm_config",
    "validate_paytm_host",
    "verify_paytm_signature",
]
