"""Paytm staging payment, status, refund, refund-status, create, and probe spike.

Modes:
- Default: runs through payment -> status -> refund -> refund status.
  * In `pending` mode: builds & checksum-signs all 4 requests, makes zero HTTP calls,
    saves redacted JSON to `api/runs/paytm_spike.json`, prints `"pending: keys not set"`,
    and exits 0.
  * In `staging` mode: takes `--order-id` for a completed Rs 35 staging payment, fetches
    `txnId` via v3 Transaction Status, issues idempotent refund `SC-{claim_id}`, polls
    v2 Refund Status, prints PASS/FAIL per step, and saves redacted JSON to `api/runs/`.
- `--create`: calls Initiate Transaction API for Rs 35, prints `orderId` and `txnToken`,
  and (in staging) writes a minimal JS Checkout page at `api/runs/paytm_checkout.html`.
- `--probe`: POSTs `{}` to all four documented paths on both staging hosts
  (`securestage.paytmpayments.com` and `securegw-stage.paytmpayments.in`) to confirm live routing.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import Settings, get_settings
from app.detector.config import PLAN_FEE_PAISE
from app.integrations.paytm import (
    PAYTM_PRIMARY_HOST,
    PaytmCallResult,
    PaytmClient,
    PaytmUnavailableError,
    plan_fee_rupees_str,
    probe_staging_endpoints,
    redact_paytm_payload,
    validate_paytm_config,
)

RUNS_DIR = API_ROOT / "runs"


def _configure_io_and_logging() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _save_redacted_json(path: Path, payload: dict[str, Any], settings: Settings) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = settings.paytm_merchant_key.get_secret_value().strip()
    cleaned = redact_paytm_payload(payload, secrets=(secret,))
    path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _write_js_checkout_html(
    *,
    path: Path,
    mid: str,
    order_id: str,
    txn_token: str,
) -> Path:
    """Write minimal Paytm staging JS Checkout page from Paytm's JS Checkout snippets doc."""
    amount = plan_fee_rupees_str()
    script_src = f"https://{PAYTM_PRIMARY_HOST}/merchantpgpui/checkoutjs/merchants/{html.escape(mid, quote=True)}.js"
    config_json = json.dumps(
        {
            "root": "",
            "flow": "DEFAULT",
            "data": {
                "orderId": order_id,
                "token": txn_token,
                "tokenType": "TXN_TOKEN",
                "amount": amount,
            },
        }
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Paytm Staging JS Checkout - Rs {html.escape(amount)}</title>
</head>
<body>
  <div id="paytm-checkoutjs"></div>
  <h1>Silent Claim Rs {html.escape(amount)} Staging Checkout</h1>
  <p>Order ID: <code>{html.escape(order_id)}</code></p>
  <p>Test UPI: <code>7777777777@paytm</code> (Paytm Test App)</p>
  <button id="pay-btn" type="button" onclick="openCheckout()">Pay Rs {html.escape(amount)}</button>
  <pre id="status"></pre>
  <script>
    var checkoutConfig = {config_json};
    checkoutConfig.handler = {{
      notifyMerchant: function(eventName, data) {{
        var el = document.getElementById("status");
        el.textContent += eventName + ": " + JSON.stringify(data) + "\\n";
      }}
    }};
    function openCheckout() {{
      if (window.Paytm && window.Paytm.CheckoutJS) {{
        window.Paytm.CheckoutJS.onLoad(function() {{
          window.Paytm.CheckoutJS.init(checkoutConfig).then(function() {{
            window.Paytm.CheckoutJS.invoke();
          }}).catch(function(err) {{
            document.getElementById("status").textContent += "ERROR: " + err + "\\n";
          }});
        }});
      }}
    }}
    function onScriptLoad() {{
      openCheckout();
    }}
  </script>
  <script type="application/javascript" src="{script_src}" onload="onScriptLoad();" crossorigin="anonymous"></script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path


def _run_probe(settings: Settings) -> int:
    entries = probe_staging_endpoints(settings=settings)
    print(f"{'Host':<35} {'Path':<34} {'HTTP':<6} {'PaytmJSON':<10} {'Latency'}")
    print("-" * 100)
    for e in entries:
        http_col = str(e.http_status) if e.http_status is not None else "ERR"
        json_col = "YES" if e.paytm_json else "NO"
        print(f"{e.host:<35} {e.path:<34} {http_col:<6} {json_col:<10} {e.latency_ms}ms")
        if e.error:
            print(f"  error: {e.error}")

    report = {
        "mode": settings.paytm_mode,
        "probed_at_epoch": int(time.time()),
        "results": [dataclasses.asdict(e) for e in entries],
    }
    out_path = _save_redacted_json(RUNS_DIR / "paytm_probe.json", report, settings)
    print(f"Saved redacted probe report to {out_path}")
    return 0


def _run_create(settings: Settings, *, order_id: str | None, cust_id: str) -> int:
    mode, _ = validate_paytm_config(settings)
    target_order_id = (order_id or f"SC_FEE_{int(time.time())}").strip()
    client = PaytmClient(settings=settings)
    res = client.initiate_plan_fee_payment(order_id=target_order_id, cust_id=cust_id)
    passed = bool(res.txn_token) or mode == "pending"
    step_state = "PASS" if passed else "FAIL"
    print(
        f"create [{step_state}] label={res.label!r} host={res.host} "
        f"orderId={res.order_id} txnToken={res.txn_token} amount_paise={PLAN_FEE_PAISE}"
    )

    html_path: str | None = None
    if mode == "staging" and res.txn_token:
        checkout_file = _write_js_checkout_html(
            path=RUNS_DIR / "paytm_checkout.html",
            mid=settings.paytm_mid.strip(),
            order_id=res.order_id,
            txn_token=res.txn_token,
        )
        html_path = str(checkout_file)
        print(f"Checkout HTML written to {checkout_file}")
        print(f"After paying Rs {plan_fee_rupees_str()}, run:")
        print(f"  uv run python scripts/spikes/paytm_spike.py --order-id {res.order_id}")

    report = {
        "mode": mode,
        "label": res.label,
        "step": "create",
        "passed": passed,
        "checkout_html": html_path,
        "result": dataclasses.asdict(res),
    }
    out_path = _save_redacted_json(RUNS_DIR / "paytm_create.json", report, settings)
    print(f"Saved redacted JSON to {out_path}")

    if mode == "pending":
        print("pending: keys not set")
        return 0
    return 0 if passed else 1


def _record_step(
    steps: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    result: PaytmCallResult | None,
    detail: str,
) -> None:
    tag = "PASS" if passed else "FAIL"
    label = result.label if result is not None else "n/a"
    host = result.host if result is not None else "-"
    print(f"{name:<15} {tag:<5} label={label!r} host={host} {detail}")
    steps.append(
        {
            "step": name,
            "verdict": tag,
            "passed": passed,
            "detail": detail,
            "result": dataclasses.asdict(result) if result is not None else None,
        }
    )


def _run_main_spike(settings: Settings, *, order_id: str | None, claim_id: str) -> int:
    mode, _ = validate_paytm_config(settings)
    client = PaytmClient(settings=settings)
    steps: list[dict[str, Any]] = []

    if mode == "pending":
        target_order_id = (order_id or "SC_PENDING_ORDER_01").strip()
        init_res = client.initiate_plan_fee_payment(order_id=target_order_id, cust_id="shop_01")
        _record_step(
            steps,
            name="payment",
            passed=init_res.simulated and init_res.signature_present,
            result=init_res,
            detail=f"orderId={init_res.order_id} amount_paise={init_res.amount_paise}",
        )
        status_res = client.get_transaction_status(order_id=target_order_id)
        _record_step(
            steps,
            name="status",
            passed=status_res.simulated and status_res.signature_present,
            result=status_res,
            detail=f"status={status_res.status} txnId={status_res.txn_id}",
        )
        refund_res = client.refund_plan_fee(
            order_id=target_order_id,
            txn_id=status_res.txn_id or f"SIM_TXN_{target_order_id}",
            claim_id=claim_id,
        )
        _record_step(
            steps,
            name="refund",
            passed=refund_res.simulated and refund_res.signature_present,
            result=refund_res,
            detail=f"refundId={refund_res.refund_id} amount_paise={refund_res.amount_paise}",
        )
        refund_status_res = client.get_refund_status(order_id=target_order_id, claim_id=claim_id)
        _record_step(
            steps,
            name="refund_status",
            passed=refund_status_res.simulated and refund_status_res.signature_present,
            result=refund_status_res,
            detail=f"refundId={refund_status_res.refund_id} status={refund_status_res.status}",
        )

        out_path = _save_redacted_json(
            RUNS_DIR / "paytm_spike.json",
            {
                "mode": mode,
                "label": init_res.label,
                "order_id": target_order_id,
                "claim_id": claim_id,
                "steps": steps,
            },
            settings,
        )
        print(f"Saved redacted JSON to {out_path}")
        print("pending: keys not set")
        return 0

    if not order_id:
        print(
            "FAIL: PAYTM_MODE=staging requires --order-id for a paid Rs 35 order "
            "(run --create first to initiate and pay one)."
        )
        return 1

    target_order_id = order_id.strip()
    try:
        status_res = client.get_transaction_status(order_id=target_order_id)
    except PaytmUnavailableError as exc:
        print(f"payment         FAIL  {exc}")
        return 1

    payment_body = status_res.redacted_response.get("body", {})
    paid_amount = str(payment_body.get("txnAmount") or "")
    payment_ok = (
        status_res.status == "TXN_SUCCESS"
        and bool(status_res.txn_id)
        and paid_amount in {plan_fee_rupees_str(), "35", "35.0"}
    )
    _record_step(
        steps,
        name="payment",
        passed=payment_ok,
        result=status_res,
        detail=f"orderId={target_order_id} txnAmount={paid_amount or '-'} status={status_res.status}",
    )
    _record_step(
        steps,
        name="status",
        passed=status_res.status == "TXN_SUCCESS" and bool(status_res.txn_id),
        result=status_res,
        detail=f"txnId={status_res.txn_id or '-'} code={status_res.result_code or '-'}",
    )

    if not status_res.txn_id:
        _record_step(
            steps,
            name="refund",
            passed=False,
            result=None,
            detail="skipped: txnId not returned by order status",
        )
        _record_step(
            steps,
            name="refund_status",
            passed=False,
            result=None,
            detail="skipped: refund not executed",
        )
        out_path = _save_redacted_json(
            RUNS_DIR / "paytm_spike.json",
            {
                "mode": mode,
                "order_id": target_order_id,
                "claim_id": claim_id,
                "steps": steps,
            },
            settings,
        )
        print(f"Saved redacted JSON to {out_path}")
        return 1

    try:
        refund_res = client.refund_plan_fee(
            order_id=target_order_id,
            txn_id=status_res.txn_id,
            claim_id=claim_id,
        )
        refund_ok = refund_res.status in {"PENDING", "TXN_SUCCESS"}
        _record_step(
            steps,
            name="refund",
            passed=refund_ok,
            result=refund_res,
            detail=(
                f"refId={refund_res.refund_id} status={refund_res.status} "
                f"code={refund_res.result_code or '-'}"
            ),
        )
    except PaytmUnavailableError as exc:
        refund_ok = False
        _record_step(steps, name="refund", passed=False, result=None, detail=str(exc))

    try:
        refund_status_res = client.get_refund_status(order_id=target_order_id, claim_id=claim_id)
        refund_status_ok = refund_status_res.status in {"PENDING", "TXN_SUCCESS"}
        _record_step(
            steps,
            name="refund_status",
            passed=refund_status_ok,
            result=refund_status_res,
            detail=(
                f"refId={refund_status_res.refund_id} status={refund_status_res.status} "
                f"code={refund_status_res.result_code or '-'}"
            ),
        )
    except PaytmUnavailableError as exc:
        refund_status_ok = False
        _record_step(steps, name="refund_status", passed=False, result=None, detail=str(exc))

    all_passed = all(step["passed"] for step in steps)
    out_path = _save_redacted_json(
        RUNS_DIR / "paytm_spike.json",
        {
            "mode": mode,
            "order_id": target_order_id,
            "claim_id": claim_id,
            "all_passed": all_passed,
            "steps": steps,
        },
        settings,
    )
    print(f"Saved redacted JSON to {out_path}")
    return 0 if all_passed else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Paytm staging spike."""
    parser = argparse.ArgumentParser(description="Paytm staging integration spike")
    parser.add_argument(
        "--order-id",
        help="Paid Rs 35 Paytm staging orderId (for main spike) or custom orderId for --create",
    )
    parser.add_argument(
        "--claim-id",
        default="spike_01",
        help="Claim identifier used to build idempotent refId SC-{claim_id}",
    )
    parser.add_argument(
        "--cust-id",
        default="shop_01",
        help="Customer / shop ID used in --create userInfo.custId",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Call initiateTransaction for Rs 35 and write api/runs/paytm_checkout.html",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="POST {} to all four Paytm paths on both staging hosts",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for Paytm spike modes."""
    _configure_io_and_logging()
    args = parse_args(argv)
    settings = get_settings()
    validate_paytm_config(settings)

    if args.probe:
        return _run_probe(settings)
    if args.create:
        return _run_create(settings, order_id=args.order_id, cust_id=args.cust_id)
    return _run_main_spike(settings, order_id=args.order_id, claim_id=args.claim_id)


if __name__ == "__main__":
    raise SystemExit(main())
