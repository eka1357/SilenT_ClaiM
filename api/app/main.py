"""FastAPI application entrypoint, startup guards, CORS, and routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.container import RUNS_DIR, AppContainer, build_container
from app.db import DATA_DIR
from app.integrations.replay import FIXTURES_DIR
from app.routes.adjuster import adjuster_router
from app.routes.claims import asks_router, claims_router
from app.routes.scenario import router as scenario_router
from app.routes.shops import router as shops_router
from app.routes.stream import router as stream_router
from app.scenario import SAMPLES_DIR


def _parse_cors_origins(web_origin: str) -> list[str]:
    origins = [item.strip() for item in web_origin.split(",") if item.strip()]
    return [o for o in origins if o != "*"] or ["http://localhost:5173"]


def create_app(
    *,
    settings: Settings | None = None,
    database_url: str | None = None,
    data_dir: Path = DATA_DIR,
    fixtures_dir: Path = FIXTURES_DIR,
    runs_dir: Path = RUNS_DIR,
    samples_dir: Path = SAMPLES_DIR,
) -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    container: AppContainer = build_container(
        settings=settings,
        database_url=database_url,
        data_dir=data_dir,
        fixtures_dir=fixtures_dir,
        runs_dir=runs_dir,
        samples_dir=samples_dir,
    )
    cfg = container.settings_getter()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.container = container
        container.db.seed(reset=False)
        yield
        await container.scenario.cancel_background()
        container.bus.close_all()
        container.db.dispose()

    application = FastAPI(
        title="Silent Claim API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.container = container

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(cfg.web_origin),
        allow_origin_regex=(
            r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"
            if cfg.demo_mode
            else None
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def _http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

    @application.exception_handler(Exception)
    async def _unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )

    application.include_router(scenario_router)
    application.include_router(shops_router)
    application.include_router(claims_router)
    application.include_router(asks_router)
    application.include_router(adjuster_router)
    application.include_router(stream_router)
    return application


def _default_app() -> FastAPI:
    return create_app(settings=get_settings())


app = _default_app()
