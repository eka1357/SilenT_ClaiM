"""Pure deterministic rules for Silent Claim detection, eligibility, street quorum, and payout cap.

Non-negotiable: no I/O, no LLM, no randomness. Money is always integer paise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.detector.baseline import (
    ShopHistory,
    ShopInput,
    compute_baseline_paise,
    count_trading_days_before,
    get_day_income_paise,
    normalize_shop_history,
    parse_day,
)
from app.detector.config import (
    DROP_RATIO_THRESHOLD,
    ELIGIBILITY_LOOKBACK_DAYS,
    ELIGIBILITY_MIN_ACTIVE_DAYS,
    MAX_REFUNDS_PER_SHOP_PER_MONTH,
    MIN_TRADING_DAYS,
    PLAN_FEE_PAISE,
    RAIN_GATE_MM,
    RULES_VERSION,
    STREET_QUORUM_SHARE,
)


class DecisionOutcome(StrEnum):
    """Possible outcomes of decide()."""

    FILE = "file"
    ASK = "ask"
    NONE = "none"


class DecisionReason(StrEnum):
    """Machine-readable reason codes for decide()."""

    FLOOD_QUORUM_AND_RAIN = "flood_quorum_and_rain"
    NOT_DROPPED = "not_dropped"
    WEEKLY_HOLIDAY = "weekly_holiday"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INACTIVE_BEFORE_EVENT = "inactive_before_event"
    NO_RAIN_SIGNAL = "no_rain_signal"
    LONE_DROP = "lone_drop"


@dataclass(frozen=True, slots=True)
class Decision:
    """Deterministic decision output for a single shop on a single calendar day."""

    shop_id: str
    day: date
    decision: DecisionOutcome
    reason: DecisionReason
    baseline_paise: int
    day_income_paise: int
    trading_days_count: int
    dropped: bool
    eligible: bool
    quorum_share: float
    quorum_met: bool
    rain_mm: float
    rain_gate_met: bool
    rules_version: str = RULES_VERSION


@dataclass(frozen=True, slots=True)
class PayoutCapDecision:
    """Result of checking the once-per-calendar-month plan-fee refund cap."""

    shop_id: str
    allowed: bool
    amount_paise: int
    reason: str


StreetInput = Mapping[str, ShopInput] | Sequence[ShopInput]
RainInput = float | int | Mapping[date | str, float | int]


def _normalize_street(street: StreetInput, fallback_shop: ShopHistory) -> list[ShopHistory]:
    """Convert street input into a list of normalized ShopHistory objects."""
    histories: list[ShopHistory] = []
    if isinstance(street, Mapping):
        for sid, shop_data in street.items():
            histories.append(normalize_shop_history(shop_data, shop_id=str(sid)))
    else:
        for idx, shop_data in enumerate(street):
            default_id = (
                shop_data.shop_id if isinstance(shop_data, ShopHistory) else f"shop_{idx + 1:02d}"
            )
            histories.append(normalize_shop_history(shop_data, shop_id=default_id))

    if not any(h.shop_id == fallback_shop.shop_id for h in histories):
        histories.append(fallback_shop)
    return histories


def _extract_rain_mm(rain: RainInput, target_day: date) -> float:
    """Resolve daily rainfall in mm for target_day."""
    if isinstance(rain, (int, float)):
        return float(rain)
    if target_day in rain:
        return float(rain[target_day])
    iso = target_day.isoformat()
    if iso in rain:
        return float(rain[iso])
    return 0.0


def is_day_dropped(
    day_income_paise: int,
    baseline_paise: int,
    drop_ratio: float = DROP_RATIO_THRESHOLD,
) -> bool:
    """Return True when day income is strictly below `drop_ratio` (30%) of baseline."""
    if baseline_paise <= 0:
        return False
    return day_income_paise < (baseline_paise * drop_ratio)


def is_recurring_weekly_holiday(
    shop: ShopInput,
    target_day: date | str,
    baseline_paise: int | None = None,
) -> bool:
    """Check whether target_day's weekday is a recurring weekly holiday for the shop.

    Examines all calendar occurrences of the same weekday from the shop's earliest
    recorded day up to (but excluding) target_day. If there are at least 2 prior
    occurrences of that weekday and the shop dropped on at least half of them,
    the weekday is recognized as the shop's weekly holiday.
    """
    day_val = parse_day(target_day)
    history = normalize_shop_history(shop)
    if not history.days:
        return False

    base = (
        baseline_paise if baseline_paise is not None else compute_baseline_paise(history, day_val)
    )
    if base <= 0:
        return False

    first_day = history.days[0].day
    prior_same_weekdays: list[date] = []
    cursor = day_val - timedelta(days=7)
    while cursor >= first_day:
        prior_same_weekdays.append(cursor)
        cursor -= timedelta(days=7)

    if len(prior_same_weekdays) < 2:
        return False

    dropped_prior = sum(
        1 for d in prior_same_weekdays if is_day_dropped(get_day_income_paise(history, d), base)
    )
    return dropped_prior * 2 >= len(prior_same_weekdays)


def is_eligible_before_event(
    shop: ShopInput,
    event_day: date | str,
    baseline_paise: int | None = None,
) -> bool:
    """Check whether the shop was actively trading before event_day.

    Rules from DATA_SPEC.md:
    The shop traded normally (did not drop) on at least 2 of the 3 calendar days
    before the event, and the day just before the event (event_day - 1) was normal
    unless it is the shop's regular weekly holiday (dropped on at least half of that
    weekday's earlier occurrences). A weekly holiday still passes; a leave or a QR
    switch that started before the event, even the day before, does not.
    """
    day_val = parse_day(event_day)
    history = normalize_shop_history(shop)
    base = (
        baseline_paise if baseline_paise is not None else compute_baseline_paise(history, day_val)
    )
    if base <= 0:
        return False

    lookback_days = [
        day_val - timedelta(days=offset) for offset in range(ELIGIBILITY_LOOKBACK_DAYS, 0, -1)
    ]
    normal_days_count = sum(
        1 for d in lookback_days if not is_day_dropped(get_day_income_paise(history, d), base)
    )
    if normal_days_count < ELIGIBILITY_MIN_ACTIVE_DAYS:
        return False

    day_before = day_val - timedelta(days=1)
    if not is_day_dropped(get_day_income_paise(history, day_before), base):
        return True
    return is_recurring_weekly_holiday(history, day_before, baseline_paise=base)


def compute_street_quorum(
    street: StreetInput,
    event_day: date | str,
    fallback_shop: ShopHistory | None = None,
) -> tuple[float, int, int]:
    """Compute the share of shops on the street (with >= 14 trading days) that dropped on event_day.

    Returns (quorum_share, dropped_count, qualified_shops_count).
    """
    day_val = parse_day(event_day)
    dummy = fallback_shop or ShopHistory(shop_id="__none__", days=())
    histories = _normalize_street(street, dummy)
    if fallback_shop is None:
        histories = [h for h in histories if h.shop_id != "__none__"]

    qualified_count = 0
    dropped_count = 0
    for shop_hist in histories:
        if count_trading_days_before(shop_hist, day_val) < MIN_TRADING_DAYS:
            continue
        qualified_count += 1
        shop_base = compute_baseline_paise(shop_hist, day_val)
        shop_income = get_day_income_paise(shop_hist, day_val)
        if is_day_dropped(shop_income, shop_base):
            dropped_count += 1

    if qualified_count == 0:
        return 0.0, 0, 0
    return dropped_count / qualified_count, dropped_count, qualified_count


def decide(
    shop: ShopInput | str,
    day: date | str,
    street: StreetInput,
    rain: RainInput,
) -> Decision:
    """Evaluate the DATA_SPEC.md decision table for a shop on a given day."""
    day_val = parse_day(day)

    if isinstance(shop, str):
        if not isinstance(street, Mapping) or shop not in street:
            msg = f"Shop id '{shop}' not found in street mapping"
            raise KeyError(msg)
        shop_hist = normalize_shop_history(street[shop], shop_id=shop)
    else:
        shop_hist = normalize_shop_history(shop)

    trading_days_count = count_trading_days_before(shop_hist, day_val)
    baseline_paise = compute_baseline_paise(shop_hist, day_val)
    day_income_paise = get_day_income_paise(shop_hist, day_val)
    dropped = is_day_dropped(day_income_paise, baseline_paise)
    eligible = is_eligible_before_event(shop_hist, day_val, baseline_paise=baseline_paise)

    quorum_share, _, _ = compute_street_quorum(street, day_val, fallback_shop=shop_hist)
    quorum_met = quorum_share >= STREET_QUORUM_SHARE

    rain_mm = _extract_rain_mm(rain, day_val)
    rain_gate_met = rain_mm >= RAIN_GATE_MM

    # Condition 1: Shop has under 14 trading days of history -> ask
    if trading_days_count < MIN_TRADING_DAYS:
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.ASK,
            reason=DecisionReason.INSUFFICIENT_HISTORY,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 2: Today is the shop's recurring weekly holiday -> none
    if is_recurring_weekly_holiday(shop_hist, day_val, baseline_paise=baseline_paise):
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.NONE,
            reason=DecisionReason.WEEKLY_HOLIDAY,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 3: Shop did not drop -> none
    if not dropped:
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.NONE,
            reason=DecisionReason.NOT_DROPPED,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 3: Shop dropped, not eligible -> ask (reason inactive_before_event)
    if not eligible:
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.ASK,
            reason=DecisionReason.INACTIVE_BEFORE_EVENT,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 4: Shop dropped, street quorum met, rain gate met -> file
    if quorum_met and rain_gate_met:
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.FILE,
            reason=DecisionReason.FLOOD_QUORUM_AND_RAIN,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 5: Shop dropped, quorum met, rain gate not met -> ask (reason no_rain_signal)
    if quorum_met and not rain_gate_met:
        return Decision(
            shop_id=shop_hist.shop_id,
            day=day_val,
            decision=DecisionOutcome.ASK,
            reason=DecisionReason.NO_RAIN_SIGNAL,
            baseline_paise=baseline_paise,
            day_income_paise=day_income_paise,
            trading_days_count=trading_days_count,
            dropped=dropped,
            eligible=eligible,
            quorum_share=quorum_share,
            quorum_met=quorum_met,
            rain_mm=rain_mm,
            rain_gate_met=rain_gate_met,
        )

    # Condition 6: Shop dropped, quorum not met -> ask (reason lone_drop)
    return Decision(
        shop_id=shop_hist.shop_id,
        day=day_val,
        decision=DecisionOutcome.ASK,
        reason=DecisionReason.LONE_DROP,
        baseline_paise=baseline_paise,
        day_income_paise=day_income_paise,
        trading_days_count=trading_days_count,
        dropped=dropped,
        eligible=eligible,
        quorum_share=quorum_share,
        quorum_met=quorum_met,
        rain_mm=rain_mm,
        rain_gate_met=rain_gate_met,
    )


def check_payout_cap(
    shop_id: str,
    refund_day: date | str,
    existing_refund_days: Sequence[date | str] = (),
) -> PayoutCapDecision:
    """Enforce the monthly plan-fee refund cap (at most 1 refund of Rs 35 per shop per calendar month)."""
    day_val = parse_day(refund_day)
    same_month_count = sum(
        1
        for prev in existing_refund_days
        if (parsed := parse_day(prev)).year == day_val.year and parsed.month == day_val.month
    )
    if same_month_count >= MAX_REFUNDS_PER_SHOP_PER_MONTH:
        return PayoutCapDecision(
            shop_id=shop_id,
            allowed=False,
            amount_paise=0,
            reason="monthly_cap_reached",
        )
    return PayoutCapDecision(
        shop_id=shop_id,
        allowed=True,
        amount_paise=PLAN_FEE_PAISE,
        reason="ok",
    )
