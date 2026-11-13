"""Application dependency container and request guards for Silent Claim API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request, status

from app.agents.graph import ClaimGraphRunner
from app.agents.nodes import AgentRuntime
from app.config import API_ROOT, Settings, get_settings
from app.db import DATA_DIR, DatabaseManager, resolve_database_url
from app.events import EventBus, IntegrationHealthTracker, SlidingWindowRateLimiter
from app.integrations.paytm import validate_paytm_config
from app.integrations.replay import FIXTURES_DIR
from app.scenario import SAMPLES_DIR, ScenarioRunner

RUNS_DIR: Path = API_ROOT / "runs"


@dataclass
class AppContainer:
    """Owns all stateful runtime services attached to FastAPI app.state."""

    settings_getter: Callable[[], Settings]
    db: DatabaseManager
    bus: EventBus
    health: IntegrationHealthTracker
    runtime: AgentRuntime
    graph_runner: ClaimGraphRunner
    scenario: ScenarioRunner
    rate_limiter: SlidingWindowRateLimiter


def build_container(
    *,
    settings: Settings | None = None,
    database_url: str | None = None,
    data_dir: Path = DATA_DIR,
    fixtures_dir: Path = FIXTURES_DIR,
    runs_dir: Path = RUNS_DIR,
    samples_dir: Path = SAMPLES_DIR,
) -> AppContainer:
    """Instantiate and wire the full backend service container."""
    settings_getter = (lambda: settings) if settings is not None else get_settings
    cfg = settings_getter()

    # Startup safety guard: enforce staging-only Paytm configuration before serving traffic.
    validate_paytm_config(cfg)

    db_url = database_url or resolve_database_url(cfg)
    db = DatabaseManager(
        db_url,
        data_dir=data_dir,
        weather_lat=cfg.weather_lat,
        weather_lon=cfg.weather_lon,
    )
    bus = EventBus()
    health = IntegrationHealthTracker(bus=bus, settings_getter=settings_getter)
    runtime = AgentRuntime(
        db=db,
        bus=bus,
        health=health,
        settings_getter=settings_getter,
        fixtures_dir=fixtures_dir,
        runs_dir=runs_dir,
    )
    graph_runner = ClaimGraphRunner(runtime)
    scenario = ScenarioRunner(graph_runner=graph_runner, samples_dir=samples_dir)
    rate_limiter = SlidingWindowRateLimiter(limit_per_minute=cfg.rate_limit_per_minute)
    return AppContainer(
        settings_getter=settings_getter,
        db=db,
        bus=bus,
        health=health,
        runtime=runtime,
        graph_runner=graph_runner,
        scenario=scenario,
        rate_limiter=rate_limiter,
    )


def get_container(request: Request) -> AppContainer:
    """FastAPI dependency returning the app's service container."""
    return request.app.state.container


def enforce_rate_limit(request: Request) -> None:
    """Enforce per-IP rate limit on cost-incurring endpoints (/api/asks/* and /api/scenario/*)."""
    container = get_container(request)
    client_ip = request.client.host if request.client else "unknown"
    if not container.rate_limiter.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded; please wait before retrying.",
        )


def require_demo_mode(request: Request) -> None:
    """Enforce DEMO_MODE=1 on scenario simulation endpoints."""
    container = get_container(request)
    cfg = container.settings_getter()
    if not cfg.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scenario endpoints are disabled when DEMO_MODE=0.",
        )
