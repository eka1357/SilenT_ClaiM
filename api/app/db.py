"""SQLAlchemy 2 engine, session factory, and deterministic CSV seeding."""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, delete, event, func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import API_ROOT, Settings, get_settings, is_offline
from app.models import (
    Ask,
    AuditLog,
    Base,
    Batch,
    Claim,
    Detection,
    PaymentHourly,
    Refund,
    Shop,
    Street,
    now_ist,
    to_ist,
)

logger = logging.getLogger(__name__)

DATA_DIR: Path = API_ROOT / "data"
DEFAULT_LIVE_REFUNDS_ARCHIVE: Path = API_ROOT / "runs" / "live_refunds.jsonl"
STAGING_REFUND_MODE_LABELS: frozenset[str] = frozenset({"Live", "Pending at Paytm"})
DEFAULT_STREET_ID: str = "panagal_park_road"
DEFAULT_STREET_NAME: str = "Panagal Park Road (simulated)"


def resolve_database_url(settings: Settings | None = None) -> str:
    """Resolve SQLite in DEMO_OFFLINE=1 mode or Postgres DATABASE_URL when live."""
    cfg = settings or get_settings()
    sqlite_fallback = f"sqlite:///{(API_ROOT / 'silent_claim.db').as_posix()}"
    if is_offline(cfg):
        return sqlite_fallback
    configured = cfg.database_url.get_secret_value().strip()
    return configured or sqlite_fallback


def _configure_sqlite_pragmas(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create a configured SQLAlchemy 2 engine."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    _configure_sqlite_pragmas(engine)
    return engine


class DatabaseManager:
    """Manages SQLAlchemy engine, sessions, schema initialization, and CSV seeding."""

    def __init__(
        self,
        database_url: str,
        *,
        data_dir: Path = DATA_DIR,
        weather_lat: float = 13.04,
        weather_lon: float = 80.25,
        live_refunds_archive_path: Path = DEFAULT_LIVE_REFUNDS_ARCHIVE,
    ) -> None:
        self.database_url = database_url
        self.data_dir = data_dir
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.live_refunds_archive_path = live_refunds_archive_path
        self.engine = create_db_engine(database_url)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=Session,
        )

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional SQLAlchemy session."""
        sess = self.session_factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def init_schema(self) -> None:
        """Create tables if they do not exist yet."""
        Base.metadata.create_all(bind=self.engine)

    def seed(
        self,
        *,
        reset: bool = False,
        live_refunds_archive_path: Path | None = None,
    ) -> dict[str, int]:
        """Ensure seed data from shops.csv and street.csv is present; optionally reset state."""
        self.init_schema()
        archive_target = live_refunds_archive_path or self.live_refunds_archive_path
        with self.session() as sess:
            return seed_database(
                sess,
                data_dir=self.data_dir,
                weather_lat=self.weather_lat,
                weather_lon=self.weather_lon,
                reset=reset,
                live_refunds_archive_path=archive_target,
            )

    def dispose(self) -> None:
        """Dispose connection pools cleanly."""
        self.engine.dispose()


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_shops_csv(shops_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with shops_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "id": str(row["shop_id"]).strip(),
                    "name": str(row["name"]).strip(),
                    "owner": str(row["owner"]).strip(),
                    "category": str(row["category"]).strip(),
                    "street_id": DEFAULT_STREET_ID,
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "plan_active": _parse_bool(str(row["plan_active"])),
                    "staging_order_id": str(row["staging_order_id"]).strip(),
                }
            )
    return rows


def _load_street_csv(street_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with street_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ts_hour = to_ist(datetime.fromisoformat(str(row["ts_hour"]).strip()))
            rows.append(
                {
                    "shop_id": str(row["shop_id"]).strip(),
                    "ts_hour": ts_hour,
                    "n_payments": int(row["n_payments"]),
                    "amount_paise": int(row["amount_paise"]),
                }
            )
    return rows


def _archive_staging_refunds(session: Session, archive_path: Path) -> int:
    """Append refunds sent to Paytm staging to archive_path as JSONL (never writing raw_response)."""
    stmt = (
        select(Refund)
        .where(Refund.mode_label.in_(STAGING_REFUND_MODE_LABELS))
        .order_by(Refund.created_at, Refund.id)
    )
    rows = list(session.scalars(stmt))
    if not rows:
        return 0

    archived_at_iso = now_ist().isoformat()
    lines = [
        json.dumps(
            {
                "refund_id": r.refund_id,
                "paytm_order_id": r.paytm_order_id,
                "shop_id": r.shop_id,
                "refund_month": r.refund_month,
                "amount_paise": r.amount_paise,
                "status": r.status,
                "mode_label": r.mode_label,
                "archived_at": archived_at_iso,
            },
            ensure_ascii=False,
        )
        for r in rows
    ]
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with archive_path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    except Exception:
        logger.warning(
            "Failed to archive staging refunds to %s; continuing reset",
            archive_path,
            exc_info=True,
        )
    return len(rows)


def seed_database(
    session: Session,
    *,
    data_dir: Path = DATA_DIR,
    weather_lat: float = 13.04,
    weather_lon: float = 80.25,
    reset: bool = False,
    live_refunds_archive_path: Path = DEFAULT_LIVE_REFUNDS_ARCHIVE,
) -> dict[str, int]:
    """Populate streets, shops, and payments_hourly from CSV; clear run artifacts when resetting."""
    if reset:
        _archive_staging_refunds(session, live_refunds_archive_path)
        session.execute(delete(Refund))
        session.execute(delete(Ask))
        session.execute(delete(Claim))
        session.execute(delete(Batch))
        session.execute(delete(Detection))
        session.execute(delete(AuditLog))

    street = session.get(Street, DEFAULT_STREET_ID)
    if street is None:
        session.add(
            Street(
                id=DEFAULT_STREET_ID,
                name=DEFAULT_STREET_NAME,
                lat=weather_lat,
                lon=weather_lon,
            )
        )
        session.flush()

    shop_rows = _load_shops_csv(data_dir / "shops.csv")
    for spec in shop_rows:
        existing_shop = session.get(Shop, spec["id"])
        if existing_shop is None:
            session.add(Shop(**spec))
        elif reset:
            existing_shop.name = spec["name"]
            existing_shop.owner = spec["owner"]
            existing_shop.category = spec["category"]
            existing_shop.street_id = spec["street_id"]
            existing_shop.lat = spec["lat"]
            existing_shop.lon = spec["lon"]
            existing_shop.plan_active = spec["plan_active"]
            existing_shop.staging_order_id = spec["staging_order_id"]
    session.flush()

    payment_rows = _load_street_csv(data_dir / "street.csv")
    existing_count = session.scalar(select(func.count(PaymentHourly.id))) or 0
    if reset or existing_count != len(payment_rows):
        if existing_count:
            session.execute(delete(PaymentHourly))
            session.flush()
        session.execute(insert(PaymentHourly), payment_rows)

    if reset:
        session.add(
            AuditLog(
                actor="system",
                action="scenario.reset",
                payload={"shops": len(shop_rows), "payments_hourly": len(payment_rows)},
            )
        )

    return {"shops": len(shop_rows), "payments_hourly": len(payment_rows)}
