"""Street view and integration health endpoints (/api/street/{id}, /api/health)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import is_offline
from app.container import get_container

router = APIRouter(prefix="/api", tags=["street"])


@router.get("/street/{street_id}")
def get_street_state(
    street_id: str,
    request: Request,
    day: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    """Return the street's shops with display status, revealed hourly series, and baseline."""
    container = get_container(request)
    payload = container.scenario.build_street_view(street_id, target_day=day)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Street '{street_id}' not found.",
        )
    return payload


@router.get("/health")
def get_health(request: Request) -> dict[str, Any]:
    """Return integration modes (live, replay, simulated, down) and kill-switch states."""
    container = get_container(request)
    cfg = container.settings_getter()
    return {
        "status": "ok",
        "demo_mode": cfg.demo_mode,
        "demo_offline": is_offline(cfg),
        "payback_enabled": cfg.payback_enabled,
        "paytm_mode": cfg.paytm_mode.strip().lower(),
        "integrations": container.health.snapshot(),
    }
