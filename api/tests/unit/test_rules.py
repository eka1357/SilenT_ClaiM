"""Unit tests for detector baseline, eligibility, quorum, decision rules, and payout cap.

Covers cases 1 to 11 from docs/TESTING.md, named by behaviour.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.detector.baseline import (
    DailyIncome,
    ShopHistory,
    compute_baseline_paise,
)
from app.detector.config import PLAN_FEE_PAISE, RULES_VERSION
from app.detector.rules import (
    DecisionOutcome,
    DecisionReason,
    check_payout_cap,
    decide,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EVENT_DAY = date(2026, 10, 21)


@pytest.fixture(scope="module")
def simulated_street() -> dict[str, ShopHistory]:
    """Load the generated Panagal Park Road daily series by shop_id from data/street.csv."""
    street_csv = DATA_DIR / "street.csv"
    df = pd.read_csv(street_csv)
    df["day"] = df["ts_hour"].str.slice(0, 10)
    daily_df = (
        df.groupby(["shop_id", "day"], as_index=False)
        .agg({"n_payments": "sum", "amount_paise": "sum"})
        .sort_values(["shop_id", "day"])
    )

    street: dict[str, ShopHistory] = {}
    for shop_id, group in daily_df.groupby("shop_id"):
        days = tuple(
            DailyIncome(
                day=date.fromisoformat(str(row["day"])),
                amount_paise=int(row["amount_paise"]),
                n_payments=int(row["n_payments"]),
            )
            for _, row in group.iterrows()
        )
        street[str(shop_id)] = ShopHistory(shop_id=str(shop_id), days=days)
    return street


@pytest.fixture(scope="module")
def simulated_rain() -> dict[str, float]:
    """Load the daily precipitation map from data/rain.json."""
    payload = json.loads((DATA_DIR / "rain.json").read_text(encoding="utf-8"))
    times: list[str] = payload["daily"]["time"]
    precip: list[float] = payload["daily"]["precipitation_sum"]
    return dict(zip(times, precip, strict=True))


# Case 1: Flood street, Selvi -> file
def test_flood_street_selvi_is_filed(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    result = decide("shop_01", EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.FILE
    assert result.reason == DecisionReason.FLOOD_QUORUM_AND_RAIN
    assert result.dropped is True
    assert result.eligible is True
    assert result.quorum_share == pytest.approx(9 / 12)
    assert result.rain_mm == pytest.approx(27.7)
    assert result.rules_version == RULES_VERSION


# Case 2: Same street, Ravi (still trading) -> none
def test_flood_street_ravi_still_trading_is_none(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    result = decide("shop_03", EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.NONE
    assert result.reason == DecisionReason.NOT_DROPPED
    assert result.dropped is False


# Case 3: Meena, on leave from 18 Oct -> ask, reason inactive_before_event
def test_leave_before_flood_is_asked_not_filed(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    result = decide("shop_10", EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.INACTIVE_BEFORE_EVENT
    assert result.dropped is True
    assert result.eligible is False


# Case 4: Leave that starts on 20 Oct (one day before) -> ask
def test_leave_starting_one_day_before_flood_is_asked(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    selvi_days = [
        DailyIncome(day=r.day, amount_paise=0, n_payments=0)
        if r.day in (date(2026, 10, 20), EVENT_DAY)
        else r
        for r in simulated_street["shop_01"].days
    ]
    leave_one_day_before_shop = ShopHistory(shop_id="shop_leave_20_oct", days=tuple(selvi_days))
    result = decide(leave_one_day_before_shop, EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.INACTIVE_BEFORE_EVENT
    assert result.eligible is False


# Case 5: Anwar, Monday holiday on 19 Oct -> still eligible, file
def test_monday_weekly_holiday_before_flood_remains_eligible_and_filed(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    result = decide("shop_05", EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.FILE
    assert result.reason == DecisionReason.FLOOD_QUORUM_AND_RAIN
    assert result.eligible is True

    # Fatima (Tuesday weekly holiday on 20 Oct) is also eligible and filed
    fatima_result = decide("shop_08", EVENT_DAY, simulated_street, simulated_rain)
    assert fatima_result.decision == DecisionOutcome.FILE
    assert fatima_result.eligible is True


# Case 6: Kavya, QR switch on 19 Oct -> ask
def test_qr_switch_before_flood_is_asked_not_filed(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    result = decide("shop_12", EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.INACTIVE_BEFORE_EVENT
    assert result.dropped is True
    assert result.eligible is False


# Case 7: A lone drop with no quorum (illness) -> ask, reason lone_drop
def test_lone_drop_without_quorum_is_asked_with_lone_drop_reason() -> None:
    start = date(2026, 9, 24)
    normal_days = [
        DailyIncome(day=start + timedelta(days=i), amount_paise=350_000, n_payments=35)
        for i in range(27)
    ]
    ill_shop = ShopHistory(
        shop_id="shop_ill",
        days=(*normal_days, DailyIncome(day=EVENT_DAY, amount_paise=0, n_payments=0)),
    )
    peer_shops = [
        ShopHistory(
            shop_id=f"peer_{idx}",
            days=(*normal_days, DailyIncome(day=EVENT_DAY, amount_paise=350_000, n_payments=35)),
        )
        for idx in range(9)
    ]
    street = [ill_shop, *peer_shops]

    result = decide(ill_shop, EVENT_DAY, street, rain=28.0)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.LONE_DROP
    assert result.quorum_met is False
    assert result.quorum_share == pytest.approx(0.10)


# Case 8: Quorum met but 3 mm of rain (power cut or strike) -> ask, reason no_rain_signal
def test_quorum_met_with_low_rain_is_asked_with_no_rain_signal_reason(
    simulated_street: dict[str, ShopHistory],
) -> None:
    result = decide("shop_01", EVENT_DAY, simulated_street, rain=3.0)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.NO_RAIN_SIGNAL
    assert result.quorum_met is True
    assert result.rain_gate_met is False
    assert result.rain_mm == pytest.approx(3.0)


# Case 9: Under 14 trading days of history -> ask
def test_shop_under_fourteen_trading_days_is_asked_never_auto_filed(
    simulated_street: dict[str, ShopHistory],
    simulated_rain: dict[str, float],
) -> None:
    short_days = tuple(
        DailyIncome(
            day=EVENT_DAY - timedelta(days=offset),
            amount_paise=300_000,
            n_payments=25,
        )
        for offset in range(10, 0, -1)
    ) + (DailyIncome(day=EVENT_DAY, amount_paise=0, n_payments=0),)
    new_shop = ShopHistory(shop_id="new_shop_10_days", days=short_days)

    result = decide(new_shop, EVENT_DAY, simulated_street, simulated_rain)
    assert result.decision == DecisionOutcome.ASK
    assert result.reason == DecisionReason.INSUFFICIENT_HISTORY
    assert result.trading_days_count == 10


# Case 10: Returning after a month's leave -> baseline equals median of 28 trading days before leave
def test_returning_after_month_leave_computes_baseline_from_last_28_trading_days() -> None:
    # 28 active trading days in August, followed by 30 calendar days of leave (0 paise) in September
    aug_start = date(2026, 8, 1)
    active_amounts = [300_000 + (i * 10_000) for i in range(28)]
    active_days = [
        DailyIncome(day=aug_start + timedelta(days=i), amount_paise=amt, n_payments=20)
        for i, amt in enumerate(active_amounts)
    ]
    leave_start = date(2026, 8, 29)
    leave_days = [
        DailyIncome(day=leave_start + timedelta(days=i), amount_paise=0, n_payments=0)
        for i in range(30)
    ]
    return_day = date(2026, 9, 28)
    history = ShopHistory(shop_id="returning_shop", days=(*active_days, *leave_days))

    expected_median = round((active_amounts[13] + active_amounts[14]) / 2)
    baseline = compute_baseline_paise(history, return_day)
    assert baseline == expected_median
    assert baseline > 0


# Case 11: Payout cap -> a second refund for the same shop in the same month is refused
def test_second_refund_for_same_shop_in_same_month_is_refused() -> None:
    first_refund = check_payout_cap(
        shop_id="shop_01",
        refund_day=date(2026, 10, 21),
        existing_refund_days=(),
    )
    assert first_refund.allowed is True
    assert first_refund.amount_paise == PLAN_FEE_PAISE

    second_same_month = check_payout_cap(
        shop_id="shop_01",
        refund_day=date(2026, 10, 28),
        existing_refund_days=[date(2026, 10, 21)],
    )
    assert second_same_month.allowed is False
    assert second_same_month.amount_paise == 0
    assert second_same_month.reason == "monthly_cap_reached"

    next_month_refund = check_payout_cap(
        shop_id="shop_01",
        refund_day=date(2026, 11, 2),
        existing_refund_days=[date(2026, 10, 21)],
    )
    assert next_month_refund.allowed is True
    assert next_month_refund.amount_paise == PLAN_FEE_PAISE
