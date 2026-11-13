"""Claims, merchant asks (consent, voice, audio), and evidence PDF routes."""

from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from app.container import enforce_rate_limit, get_container
from app.integrations.sarvam import MAX_AUDIO_BYTES
from app.models import Ask, Claim, Detection, Refund, Shop, now_ist

MAX_AUDIO_SECONDS = 60.0
ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset({".wav", ".mp3", ".ogg", ".webm", ".m4a"})

claims_router = APIRouter(prefix="/api", tags=["claims"])
asks_router = APIRouter(
    prefix="/api/asks",
    tags=["asks"],
    dependencies=[Depends(enforce_rate_limit)],
)


def _validate_audio_upload(
    raw_bytes: bytes,
    *,
    filename: str,
    content_type: str,
) -> None:
    """Validate audio-only, 2 MB max, and 60 s max constraints (docs/SECURITY.md)."""
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio upload must not be empty.",
        )
    if len(raw_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Audio exceeds the 2 MB upload limit.",
        )

    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only audio file extensions are accepted.",
        )

    is_audio_mime = ctype.startswith("audio/")
    has_known_magic = raw_bytes.startswith(
        (b"RIFF", b"ID3", b"OggS", b"\xff\xfb", b"\x1aE\xdf\xa3")
    )
    if not (is_audio_mime or has_known_magic):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only audio uploads are accepted.",
        )

    if raw_bytes.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(raw_bytes), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration_s = (frames / rate) if rate > 0 else 0.0
        except (wave.Error, EOFError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed WAV audio payload.",
            ) from exc
        if duration_s > MAX_AUDIO_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio duration exceeds the 60 second limit.",
            )


def _serialize_ask(ask: Ask) -> dict[str, Any]:
    return {
        "id": ask.id,
        "detection_id": ask.detection_id,
        "shop_id": ask.shop_id,
        "ask_kind": ask.ask_kind,
        "status": ask.status,
        "prompt_text_ta": ask.prompt_text_ta,
        "has_audio": ask.prompt_audio_path is not None,
        "audio_url": f"/api/asks/{ask.id}/audio" if ask.prompt_audio_path else None,
        "reply_type": ask.reply_type,
        "transcript": ask.transcript,
        "cause_label": ask.cause_label,
        "confidence": ask.confidence,
        "simulated_label": ask.simulated_label,
        "answered_at": ask.answered_at.isoformat() if ask.answered_at else None,
        "created_at": ask.created_at.isoformat(),
    }


@claims_router.get("/claims")
def list_claims(request: Request) -> dict[str, Any]:
    """List filed claims and active asks with evidence links."""
    container = get_container(request)
    with container.db.session() as sess:
        claims = list(sess.scalars(select(Claim).order_by(Claim.created_at, Claim.shop_id)))
        shops = {s.id: s for s in sess.scalars(select(Shop))}
        detections = {d.id: d for d in sess.scalars(select(Detection))}
        asks = list(sess.scalars(select(Ask).order_by(Ask.created_at, Ask.shop_id)))
        ask_by_detection = {a.detection_id: a for a in asks}
        refunds_by_claim = {r.claim_id: r for r in sess.scalars(select(Refund))}

    claim_items: list[dict[str, Any]] = []
    for c in claims:
        shop = shops.get(c.shop_id)
        det = detections.get(c.detection_id)
        ask = ask_by_detection.get(c.detection_id)
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
                "rules_version": det.rules_version if det else "",
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

    return {
        "claims": claim_items,
        "asks": [_serialize_ask(a) for a in asks],
    }


@asks_router.post("/{ask_id}/consent")
async def submit_ask_consent(ask_id: str, request: Request) -> dict[str, Any]:
    """Resume a paused consent ask thread from the merchant's one-tap confirmation."""
    container = get_container(request)
    with container.db.session() as sess:
        ask = sess.get(Ask, ask_id)
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ask '{ask_id}' not found.",
            )
        if ask.ask_kind != "consent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This ask requires a voice note reply instead of a consent tap.",
            )
        if ask.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ask '{ask_id}' was already answered ({ask.status}).",
            )

    result = await asyncio.to_thread(
        container.graph_runner.resume_consent,
        ask,
        answered_at=now_ist(),
        simulated_label=None,
    )
    claim_info = result.get("claim", {})
    with container.db.session() as sess:
        updated_ask = sess.get(Ask, ask_id)

    return {
        "status": result.get("terminal_status", "filed"),
        "ask": _serialize_ask(updated_ask) if updated_ask is not None else {"id": ask_id},
        "claim": {
            "id": claim_info.get("claim_id"),
            "status": claim_info.get("status"),
            "evidence_url": (
                f"/api/evidence/{claim_info['claim_id']}.pdf"
                if claim_info.get("claim_id")
                else None
            ),
        },
    }


@asks_router.post("/{ask_id}/decline")
async def decline_ask_consent(ask_id: str, request: Request) -> dict[str, Any]:
    """Decline a paused consent ask thread, log 'consent declined', file no claim, and form batch."""
    container = get_container(request)
    with container.db.session() as sess:
        ask = sess.get(Ask, ask_id)
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ask '{ask_id}' not found.",
            )
        if ask.ask_kind != "consent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only consent asks can be declined with this action.",
            )
        if ask.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ask '{ask_id}' was already answered ({ask.status}).",
            )

    result = await asyncio.to_thread(
        container.graph_runner.resume_decline,
        ask,
        answered_at=now_ist(),
        simulated_label=None,
    )
    with container.db.session() as sess:
        updated_ask = sess.get(Ask, ask_id)

    return {
        "status": result.get("terminal_status", "declined"),
        "ask": _serialize_ask(updated_ask) if updated_ask is not None else {"id": ask_id},
        "claim": None,
    }


@asks_router.post("/{ask_id}/voice")
async def submit_ask_voice(
    ask_id: str,
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    """Accept a Tamil merchant voice upload (<= 2 MB, <= 60 s), run STT + LLM, and resume graph."""
    container = get_container(request)
    with container.db.session() as sess:
        ask = sess.get(Ask, ask_id)
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ask '{ask_id}' not found.",
            )
        if ask.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ask '{ask_id}' was already answered ({ask.status}).",
            )

    raw_bytes = await file.read(MAX_AUDIO_BYTES + 1)
    _validate_audio_upload(
        raw_bytes,
        filename=file.filename or "reply.wav",
        content_type=file.content_type or "audio/wav",
    )

    result = await asyncio.to_thread(
        container.graph_runner.resume_voice,
        ask,
        audio_bytes=raw_bytes,
        filename=file.filename or "reply.wav",
        content_type=file.content_type or "audio/wav",
        answered_at=now_ist(),
        simulated_label=None,
    )
    with container.db.session() as sess:
        updated_ask = sess.get(Ask, ask_id)
    claim_info = result.get("claim", {})
    return {
        "status": result.get("terminal_status", ""),
        "ask": _serialize_ask(updated_ask) if updated_ask is not None else {"id": ask_id},
        "claim": (
            {
                "id": claim_info.get("claim_id"),
                "status": claim_info.get("status"),
                "evidence_url": f"/api/evidence/{claim_info['claim_id']}.pdf",
            }
            if claim_info.get("claim_id")
            else None
        ),
    }


@asks_router.get("/{ask_id}/audio")
def get_ask_audio(ask_id: str, request: Request) -> Response:
    """Serve the cached Tamil WAV prompt audio for `ask_id`."""
    container = get_container(request)
    with container.db.session() as sess:
        ask = sess.get(Ask, ask_id)
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ask '{ask_id}' not found.",
            )
        audio_path = Path(ask.prompt_audio_path) if ask.prompt_audio_path else None

    if audio_path is None or not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio prompt is unavailable for this ask.",
        )

    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename=f"{ask_id}.wav",
    )


@claims_router.get("/evidence/{claim_id}.pdf")
def download_evidence_pdf(claim_id: str, request: Request) -> Response:
    """Serve the generated ReportLab evidence pack PDF for `claim_id`."""
    container = get_container(request)
    with container.db.session() as sess:
        claim = sess.get(Claim, claim_id)
        if claim is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim '{claim_id}' not found.",
            )
        pdf_path = Path(claim.evidence_pdf_path) if claim.evidence_pdf_path else None

    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence PDF has not been generated for this claim.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{claim_id}.pdf",
        content_disposition_type="inline",
    )
