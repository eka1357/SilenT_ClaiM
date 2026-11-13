"""Unit tests for POST /api/lab/decide across all seven presets."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Ask, Claim, Refund


def _build_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "lab_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    settings = Settings(
        PAYTM_MODE="pending",
        DEMO_MODE=True,
        DEMO_OFFLINE=True,
        DATABASE_URL=db_url,
    )
    app = create_app(
        settings=settings,
        database_url=db_url,
        runs_dir=tmp_path / "runs",
    )
    return TestClient(app)


def test_lab_decide_all_seven_presets_and_zero_side_effects(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        # Preset 1: Flooded street -> file
        r1 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 9,
                "rain_mm": 28,
                "sales_today_pct": 0,
                "days_traded_before": 3,
                "regular_weekly_holiday": "none",
            },
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["decision"] == "file"
        assert body1["decision_label"] == "Files the claim"
        assert body1["reason"] == "flood_quorum_and_rain"

        # Preset 2: One shop alone on a dry day -> ask
        r2 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 1,
                "rain_mm": 0,
                "sales_today_pct": 0,
                "days_traded_before": 3,
                "regular_weekly_holiday": "none",
            },
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["decision"] == "ask"
        assert body2["decision_label"] == "Asks first"
        assert body2["reason"] == "lone_drop"
        assert body2["next_step"] == "asks in Tamil and pays nothing until answered"

        # Preset 3: On leave since 3 days before -> ask
        r3 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 9,
                "rain_mm": 28,
                "sales_today_pct": 0,
                "days_traded_before": 0,
                "regular_weekly_holiday": "none",
            },
        )
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["decision"] == "ask"
        assert body3["decision_label"] == "Asks first"
        assert body3["reason"] == "inactive_before_event"

        # Preset 4: Street shut with no rain such as a strike -> ask
        r4 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 9,
                "rain_mm": 2,
                "sales_today_pct": 0,
                "days_traded_before": 3,
                "regular_weekly_holiday": "none",
            },
        )
        assert r4.status_code == 200
        body4 = r4.json()
        assert body4["decision"] == "ask"
        assert body4["decision_label"] == "Asks first"
        assert body4["reason"] == "no_rain_signal"

        # Preset 5: Closed today for its weekly holiday -> none
        r5 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 1,
                "rain_mm": 0,
                "sales_today_pct": 0,
                "days_traded_before": 3,
                "regular_weekly_holiday": "today",
            },
        )
        assert r5.status_code == 200
        body5 = r5.json()
        assert body5["decision"] == "none"
        assert body5["decision_label"] == "No action"
        assert body5["reason"] == "weekly_holiday"

        # Preset 6: Moved to another QR on the flood day -> file (known limit)
        r6 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 9,
                "rain_mm": 28,
                "sales_today_pct": 0,
                "days_traded_before": 3,
                "regular_weekly_holiday": "none",
            },
        )
        assert r6.status_code == 200
        body6 = r6.json()
        assert body6["decision"] == "file"
        assert body6["decision_label"] == "Files the claim"
        assert body6["reason"] == "flood_quorum_and_rain"

        # Preset 7: Weekly holiday yesterday, flood today -> file
        r7 = client.post(
            "/api/lab/decide",
            json={
                "shops_closed": 9,
                "rain_mm": 28,
                "sales_today_pct": 0,
                "days_traded_before": 2,
                "regular_weekly_holiday": "yesterday",
            },
        )
        assert r7.status_code == 200
        body7 = r7.json()
        assert body7["decision"] == "file"
        assert body7["decision_label"] == "Files the claim"
        assert body7["reason"] == "flood_quorum_and_rain"

        # Verify zero side effects in DB
        container = client.app.state.container
        with container.db.session() as session:
            assert session.scalars(select(Ask)).all() == []
            assert session.scalars(select(Claim)).all() == []
            assert session.scalars(select(Refund)).all() == []
