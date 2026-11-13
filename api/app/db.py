"""SQLAlchemy 2 engine, session factory, and deterministic CSV seeding."""

from __future__ import annotations

import csv
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, delete, event, func, insert, select, update
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
    to_ist,
)

DATA_DIR: Path = API_ROOT / "data"
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
    ) -> None:
        self.database_url = database_url
        self.data_dir = data_dir
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
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

    def seed(self, *, reset: bool = False) -> dict[str, int]:
        """Ensure seed data from shops.csv and street.csv is present; optionally reset state."""
        self.init_schema()
        with self.session() as sess:
            return seed_database(
                sess,
                data_dir=self.data_dir,
                weather_lat=self.weather_lat,
                weather_lon=self.weather_lon,
                reset=reset,
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


def seed_database(
    session: Session,
    *,
    data_dir: Path = DATA_DIR,
    weather_lat: float = 13.04,
    weather_lon: float = 80.25,
    reset: bool = False,
) -> dict[str, int]:
    """Populate streets, shops, and payments_hourly from CSV; clear run artifacts when resetting."""
    if reset:
        # Preserve any live staging refunds per docs/ARCHITECTURE.md, clearing claim_id FK safely.
        session.execute(update(Refund).where(Refund.mode_label == "Live").values(claim_id=None))
        session.execute(delete(Refund).where(Refund.mode_label != "Live"))
        session.execute(delete(Refund).where(Refund.mode_label.is_(None)))
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
