"""Adjuster batch review, one-click approval, payback trigger, and console metrics routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import is_offline
from app.container import get_container
from app.db import DATA_DIR
from app.detector.config import RULES_VERSION
from app.models import Ask, AuditLog, Batch, Claim, Detection, Refund, Shop, now_ist, to_ist

adjuster_router = APIRouter(prefix="/api", tags=["adjuster"])


def _serialize_batch(
    batch: Batch,
    claims: list[Claim],
    shops: dict[str, Shop],
    detections: dict[str, Detection],
    asks_by_det: dict[str, Ask],
    refunds_by_claim: dict[str, Refund],
) -> dict[str, Any]:
    claim_items: list[dict[str, Any]] = []
    for c in claims:
        shop = shops.get(c.shop_id)
        det = detections.get(c.detection_id)
        ask = asks_by_det.get(c.detection_id)
        refund = refunds_by_claim.get(c.id)
        claim_items.append(
            {
                "id": c.id,
                "shop_id": c.shop_id,
                "shop_name": shop.name if shop else c.shop_id,
                "owner": shop.owner if shop else c.shop_id,
                "detection_id": c.detection_id,
                "batch_id": c.batch_id,
                "day": det.day.isoformat() if det else None,
                "baseline_paise": det.baseline_paise if det else 0,
                "day_income_paise": det.day_income_paise if det else 0,
                "quorum_share": det.quorum_share if det else 0.0,
                "rain_mm": det.rain_mm if det else 0.0,
                "rain_source": det.rain_source if det else "",
                "rules_version": det.rules_version if det else RULES_VERSION,
                "status": c.status,
                "summary_text": c.summary_text,
                "consent_at": c.consent_at.isoformat() if c.consent_at else None,
                "simulated_label": ask.simulated_label if ask else None,
                "cause_label": ask.cause_label if ask else None,
                "evidence_url": f"/api/evidence/{c.id}.pdf",
                "refund": (
                    {
                        "id": refund.id,
                        "refund_id": refund.refund_id,
                        "paytm_order_id": refund.paytm_order_id,
                        "refund_month": refund.refund_month,
                        "amount_paise": refund.amount_paise,
                        "status": refund.status,
                        "label": refund.mode_label,
                    }
                    if refund is not None
                    else None
                ),
            }
        )

    batch_dict = {
        "id": batch.id,
        "status": batch.status,
        "approved_by": batch.approved_by,
        "approved_at": batch.approved_at.isoformat() if batch.approved_at else None,
        "created_at": batch.created_at.isoformat(),
        "claims_count": len(claim_items),
        "claims": claim_items,
    }
    return {
        **batch_dict,
        "batch": batch_dict,
    }


@adjuster_router.get("/batches/current")
def get_current_batch(request: Request) -> dict[str, Any]:
    """Return the latest claim batch with its claims, evidence links, and refund statuses."""
    container = get_container(request)
    with container.db.session() as sess:
        batch = sess.scalar(select(Batch).order_by(Batch.created_at.desc()))
        if batch is None:
            return {"batch": None, "id": None, "status": None, "claims": []}

        claims = list(
            sess.scalars(select(Claim).where(Claim.batch_id == batch.id).order_by(Claim.shop_id))
        )
        shops = {s.id: s for s in sess.scalars(select(Shop))}
        detections = {d.id: d for d in sess.scalars(select(Detection))}
        asks_by_det = {a.detection_id: a for a in sess.scalars(select(Ask))}
        refunds_by_claim = {r.claim_id: r for r in sess.scalars(select(Refund))}
        return _serialize_batch(
            batch=batch,
            claims=claims,
            shops=shops,
            detections=detections,
            asks_by_det=asks_by_det,
            refunds_by_claim=refunds_by_claim,
        )


@adjuster_router.post("/batches/{batch_id}/approve")
async def approve_batch(batch_id: str, request: Request) -> dict[str, Any]:
    """Approve an open claim batch and trigger background plan-fee payback."""
    container = get_container(request)
    cfg = container.settings_getter()
    already_approved = False

    with container.db.session() as sess:
        batch = sess.get(Batch, batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch '{batch_id}' not found.",
            )

        claims = list(
            sess.scalars(select(Claim).where(Claim.batch_id == batch_id).order_by(Claim.shop_id))
        )
        if batch.status == "approved":
            already_approved = True
        else:
            batch.status = "approved"
            batch.approved_by = "adjuster"
            batch.approved_at = now_ist()
            claim_ids = [c.id for c in claims]
            sess.add(
                AuditLog(
                    actor="adjuster",
                    action="batch.approved",
                    payload={
                        "batch_id": batch_id,
                        "claim_ids": claim_ids,
                        "payback_enabled": cfg.payback_enabled,
                    },
                )
            )
            if not cfg.payback_enabled:
                for c in claims:
                    c.status = "Refunds paused"
                sess.add(
                    AuditLog(
                        actor="agent",
                        action="payback.paused",
                        payload={"batch_id": batch_id, "claim_ids": claim_ids},
                    )
                )
            else:
                for c in claims:
                    if c.status == "filed":
                        c.status = "approved"
            sess.flush()

        shops = {s.id: s for s in sess.scalars(select(Shop))}
        detections = {d.id: d for d in sess.scalars(select(Detection))}
        asks_by_det = {a.detection_id: a for a in sess.scalars(select(Ask))}
        refunds_by_claim = {r.claim_id: r for r in sess.scalars(select(Refund))}
        response_payload = _serialize_batch(
            batch=batch,
            claims=claims,
            shops=shops,
            detections=detections,
            asks_by_det=asks_by_det,
            refunds_by_claim=refunds_by_claim,
        )

    if already_approved:
        return {
            **response_payload,
            "already_approved": True,
            "payback_scheduled": False,
        }

    container.bus.publish(
        "batch.approved",
        {
            "batch_id": batch_id,
            "approved_by": "adjuster",
            "payback_enabled": cfg.payback_enabled,
            "live": True,
            "replay": is_offline(cfg),
        },
    )
    if cfg.payback_enabled:
        container.scenario.start_batch_payback(batch_id)
    else:
        container.bus.publish(
            "agent.step",
            {
                "node": "payback",
                "status": "paused",
                "detail": "Refunds paused (PAYBACK_ENABLED=0)",
                "live": False,
            },
        )

    return {
        **response_payload,
        "already_approved": False,
        "payback_scheduled": bool(cfg.payback_enabled),
    }


def _load_eval_results(data_dir: Path) -> dict[str, Any]:
    """Load held-out evaluation metrics from data/eval_results.json."""
    for candidate in (data_dir / "eval_results.json", DATA_DIR / "eval_results.json"):
        if candidate.exists():
            raw = json.loads(candidate.read_text(encoding="utf-8"))
            return {
                "label": raw.get("label", "Simulated eval"),
                "rules_version": raw.get("rules_version", RULES_VERSION),
                "split": raw.get("split", "held_out"),
                "total_cases": int(raw.get("total_cases", 60)),
                "claims_filed": int(raw.get("claims_filed", 0)),
                "claims_right": int(raw.get("claims_right", 0)),
                "wrong_claims": int(raw.get("wrong_claims", 0)),
                "wrong_claim_share": float(raw.get("wrong_claim_share", 0.0)),
                "false_positive_rate": float(raw.get("false_positive_rate", 0.0)),
                "closures_missed": int(raw.get("closures_missed", 0)),
                "total_closures": int(raw.get("total_closures", 0)),
                "missed_claim_rate": float(raw.get("missed_claim_rate", 0.0)),
            }
    return {
        "label": "Simulated eval",
        "rules_version": RULES_VERSION,
        "split": "held_out",
        "total_cases": 0,
        "claims_filed": 0,
        "claims_right": 0,
        "wrong_claims": 0,
        "wrong_claim_share": 0.0,
        "false_positive_rate": 0.0,
        "closures_missed": 0,
        "total_closures": 0,
        "missed_claim_rate": 0.0,
    }


@adjuster_router.get("/metrics")
def get_metrics(request: Request) -> dict[str, Any]:
    """Return console receipt metrics: 0 forms, taps, time-to-file, refunds, and eval numbers."""
    container = get_container(request)
    cfg = container.settings_getter()

    with container.db.session() as sess:
        claims = list(sess.scalars(select(Claim).order_by(Claim.shop_id)))
        detections = {d.id: d for d in sess.scalars(select(Detection))}
        asks = list(sess.scalars(select(Ask)))
        batches = list(sess.scalars(select(Batch)))
        refunds = list(sess.scalars(select(Refund).order_by(Refund.shop_id)))

    tap_asks = [a for a in asks if a.reply_type == "tap"]
    human_tap_asks = [a for a in tap_asks if a.simulated_label is None]
    approved_batches = [b for b in batches if b.status == "approved"]

    time_to_file_by_claim: list[dict[str, Any]] = []
    for c in claims:
        det = detections.get(c.detection_id)
        decision_at = to_ist(det.created_at) if det is not None else None
        filed_at = to_ist(c.consent_at) if c.consent_at is not None else to_ist(c.created_at)
        seconds = (
            max(0.0, round((filed_at - decision_at).total_seconds(), 3))
            if decision_at is not None and filed_at is not None
            else 0.0
        )
        time_to_file_by_claim.append(
            {
                "claim_id": c.id,
                "shop_id": c.shop_id,
                "decision_at": decision_at.isoformat() if decision_at else None,
                "filed_at": filed_at.isoformat() if filed_at else None,
                "seconds": seconds,
            }
        )

    durations = [item["seconds"] for item in time_to_file_by_claim]
    avg_seconds = round(sum(durations) / len(durations), 3) if durations else 0.0
    max_seconds = round(max(durations), 3) if durations else 0.0

    refund_items = [
        {
            "claim_id": r.claim_id,
            "shop_id": r.shop_id,
            "refund_id": r.refund_id,
            "amount_paise": r.amount_paise,
            "status": r.status,
            "label": r.mode_label,
        }
        for r in refunds
    ]

    eval_metrics = _load_eval_results(container.db.data_dir)
    return {
        "forms_filled": 0,
        "taps": len(tap_asks),
        "merchant_taps": len(human_tap_asks),
        "adjuster_taps": len(approved_batches),
        "claims_filed_in_run": len(claims),
        "avg_time_to_file_seconds": avg_seconds,
        "max_time_to_file_seconds": max_seconds,
        "time_to_file_by_claim": time_to_file_by_claim,
        "refunds": {
            "count": len(refund_items),
            "total_amount_paise": sum(r.amount_paise for r in refunds),
            "payback_enabled": cfg.payback_enabled,
            "items": refund_items,
        },
        "eval": eval_metrics,
        "integrations": container.health.snapshot(),
    }
