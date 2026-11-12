"""Trading-day baseline calculation (median over last 28 trading days).

Pure functions only: no I/O, no network, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.detector.config import BASELINE_TRADING_DAYS


@dataclass(frozen=True, slots=True)
class DailyIncome:
    """Aggregated payment activity for one shop on one calendar day (IST)."""

    day: date
    amount_paise: int
    n_payments: int = 1


@dataclass(frozen=True, slots=True)
class ShopHistory:
    """Chronological daily income series for a single shop."""

    shop_id: str
    days: tuple[DailyIncome, ...]


ShopInput = ShopHistory | Mapping[date | str, int | DailyIncome] | Sequence[DailyIncome]


def parse_day(value: date | str) -> date:
    """Convert an ISO date string or date object into a datetime.date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def is_trading_day(record: DailyIncome) -> bool:
    """A trading day is a calendar day on which the shop took at least one payment."""
    return record.n_payments > 0 and record.amount_paise > 0


def normalize_shop_history(shop: ShopInput, shop_id: str = "shop") -> ShopHistory:
    """Normalize supported shop history inputs into a sorted ShopHistory."""
    if isinstance(shop, ShopHistory):
        aggregated: dict[date, tuple[int, int]] = {}
        for item in shop.days:
            prev_amt, prev_cnt = aggregated.get(item.day, (0, 0))
            aggregated[item.day] = (prev_amt + item.amount_paise, prev_cnt + item.n_payments)
        sorted_days = tuple(
            DailyIncome(day=d, amount_paise=amt, n_payments=cnt)
            for d, (amt, cnt) in sorted(aggregated.items())
        )
        return ShopHistory(shop_id=shop.shop_id, days=sorted_days)

    if isinstance(shop, Mapping):
        aggregated_map: dict[date, tuple[int, int]] = {}
        for raw_day, raw_val in shop.items():
            d = parse_day(raw_day)
            if isinstance(raw_val, DailyIncome):
                amt = raw_val.amount_paise
                cnt = raw_val.n_payments
            else:
                amt = int(raw_val)
                cnt = 1 if amt > 0 else 0
            prev_amt, prev_cnt = aggregated_map.get(d, (0, 0))
            aggregated_map[d] = (prev_amt + amt, prev_cnt + cnt)
        sorted_days = tuple(
            DailyIncome(day=d, amount_paise=amt, n_payments=cnt)
            for d, (amt, cnt) in sorted(aggregated_map.items())
        )
        return ShopHistory(shop_id=shop_id, days=sorted_days)

    aggregated_seq: dict[date, tuple[int, int]] = {}
    for item in shop:
        prev_amt, prev_cnt = aggregated_seq.get(item.day, (0, 0))
        aggregated_seq[item.day] = (prev_amt + item.amount_paise, prev_cnt + item.n_payments)
    sorted_days = tuple(
        DailyIncome(day=d, amount_paise=amt, n_payments=cnt)
        for d, (amt, cnt) in sorted(aggregated_seq.items())
    )
    return ShopHistory(shop_id=shop_id, days=sorted_days)


def trading_days_before(shop: ShopInput, target_day: date | str) -> list[DailyIncome]:
    """Return all trading days strictly before target_day in chronological order."""
    day_val = parse_day(target_day)
    history = normalize_shop_history(shop)
    return [record for record in history.days if record.day < day_val and is_trading_day(record)]


def count_trading_days_before(shop: ShopInput, target_day: date | str) -> int:
    """Count how many trading days of history a shop has strictly before target_day."""
    return len(trading_days_before(shop, target_day))


def compute_baseline_paise(
    shop: ShopInput,
    target_day: date | str,
    window: int = BASELINE_TRADING_DAYS,
) -> int:
    """Compute the median daily income in paise over the last `window` trading days before target_day.

    Using trading days ensures a shop returning from a month's leave is compared
    with its last active trading month rather than with zeros.
    """
    prior_trading = trading_days_before(shop, target_day)
    if not prior_trading:
        return 0
    recent_window = prior_trading[-window:]
    amounts = sorted(record.amount_paise for record in recent_window)
    n = len(amounts)
    mid = n // 2
    if n % 2 == 1:
        return amounts[mid]
    return round((amounts[mid - 1] + amounts[mid]) / 2)


def get_day_income_paise(shop: ShopInput, target_day: date | str) -> int:
    """Return the shop's total income in paise on target_day (0 if no record exists)."""
    day_val = parse_day(target_day)
    history = normalize_shop_history(shop)
    for record in history.days:
        if record.day == day_val:
            return record.amount_paise
    return 0
