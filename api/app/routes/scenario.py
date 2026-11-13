"""Scenario control endpoints (/api/scenario/reset and /api/scenario/run)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.container import enforce_rate_limit, get_container, require_demo_mode

router = APIRouter(
    prefix="/api/scenario",
    tags=["scenario"],
    dependencies=[Depends(enforce_rate_limit), Depends(require_demo_mode)],
)


class ScenarioRunRequest(BaseModel):
    """Request body for POST /api/scenario/run."""

    day: date = Field(default=date(2026, 10, 21))
    speed: float = Field(default=60.0, ge=0.0, le=3600.0)


@router.post("/reset")
async def reset_scenario(request: Request) -> dict[str, Any]:
    """Reload CSV seed data and clear detections, asks, and claims (preserving live refunds)."""
    container = get_container(request)
    counts = await container.scenario.reset()
    return {"status": "reset", "seeded": counts}


@router.post("/run")
async def run_scenario(body: ScenarioRunRequest, request: Request) -> dict[str, Any]:
    """Replay the simulated street day and run end-of-day detector + agent graph."""
    container = get_container(request)
    return await container.scenario.start_run(body.day, speed=body.speed)
