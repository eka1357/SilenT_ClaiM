"""Deterministic synthetic data generator for Silent Claim (seed 2026).

Generates:
- api/data/shops.csv (12 named shops on Panagal Park Road)
- api/data/street.csv (hourly payments from 24 Sep 2026 to 22 Oct 2026, 07:00-22:00 IST)
- api/data/rain.json (Open-Meteo daily precipitation_sum fixture)
- api/data/eval_shopweeks.csv (200 labelled shop-weeks with 140/60 tuning/held_out split)
- api/data/eval/case_001.csv .. case_200.csv (daily series per eval case)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED: int = 2026
START_DAY: date = date(2026, 9, 24)
END_DAY: date = date(2026, 10, 22)
EVENT_DAY: date = date(2026, 10, 21)
HOURS_IST: tuple[int, ...] = tuple(range(7, 23))  # 07:00 to 22:00 IST inclusive

DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
EVAL_DIR: Path = DATA_DIR / "eval"


@dataclass(frozen=True, slots=True)
class ShopSpec:
    """Configuration for one simulated shop on Panagal Park Road."""

    shop_id: str
    name: str
    owner: str
    category: str
    lat: float
    lon: float
    staging_order_id: str
    target_daily_rupees: int
    avg_ticket_rupees: int
    behaviour: str


SHOPS: tuple[ShopSpec, ...] = (
    ShopSpec(
        shop_id="shop_01",
        name="Flower stall",
        owner="Selvi",
        category="flowers",
        lat=13.0401,
        lon=80.2501,
        staging_order_id="ORD-STG-SHOP-01",
        target_daily_rupees=3200,
        avg_ticket_rupees=80,
        behaviour="hero_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_02",
        name="Tea stall",
        owner="Kumar",
        category="tea",
        lat=13.0402,
        lon=80.2502,
        staging_order_id="ORD-STG-SHOP-02",
        target_daily_rupees=2400,
        avg_ticket_rupees=30,
        behaviour="normal_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_03",
        name="Pharmacy",
        owner="Ravi",
        category="pharmacy",
        lat=13.0403,
        lon=80.2503,
        staging_order_id="ORD-STG-SHOP-03",
        target_daily_rupees=11500,
        avg_ticket_rupees=230,
        behaviour="thin_in_flood",
    ),
    ShopSpec(
        shop_id="shop_04",
        name="Fruit cart",
        owner="Lakshmi",
        category="fruit",
        lat=13.0404,
        lon=80.2504,
        staging_order_id="ORD-STG-SHOP-04",
        target_daily_rupees=2800,
        avg_ticket_rupees=70,
        behaviour="normal_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_05",
        name="Tailor",
        owner="Anwar",
        category="tailor",
        lat=13.0405,
        lon=80.2505,
        staging_order_id="ORD-STG-SHOP-05",
        target_daily_rupees=4200,
        avg_ticket_rupees=210,
        behaviour="monday_holiday_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_06",
        name="Mobile repair",
        owner="Priya",
        category="mobile_repair",
        lat=13.0406,
        lon=80.2506,
        staging_order_id="ORD-STG-SHOP-06",
        target_daily_rupees=5600,
        avg_ticket_rupees=280,
        behaviour="normal_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_07",
        name="Grocery",
        owner="Murugan",
        category="grocery",
        lat=13.0407,
        lon=80.2507,
        staging_order_id="ORD-STG-SHOP-07",
        target_daily_rupees=9800,
        avg_ticket_rupees=175,
        behaviour="thin_in_flood",
    ),
    ShopSpec(
        shop_id="shop_08",
        name="Bakery",
        owner="Fatima",
        category="bakery",
        lat=13.0408,
        lon=80.2508,
        staging_order_id="ORD-STG-SHOP-08",
        target_daily_rupees=4800,
        avg_ticket_rupees=120,
        behaviour="tuesday_holiday_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_09",
        name="Footwear",
        owner="Arjun",
        category="footwear",
        lat=13.0409,
        lon=80.2509,
        staging_order_id="ORD-STG-SHOP-09",
        target_daily_rupees=6400,
        avg_ticket_rupees=320,
        behaviour="normal_flood_drop",
    ),
    ShopSpec(
        shop_id="shop_10",
        name="Stationery",
        owner="Meena",
        category="stationery",
        lat=13.0410,
        lon=80.2510,
        staging_order_id="ORD-STG-SHOP-10",
        target_daily_rupees=3600,
        avg_ticket_rupees=90,
        behaviour="leave_from_18_oct",
    ),
    ShopSpec(
        shop_id="shop_11",
        name="Hotel (tiffin)",
        owner="Babu",
        category="tiffin",
        lat=13.0411,
        lon=80.2511,
        staging_order_id="ORD-STG-SHOP-11",
        target_daily_rupees=8400,
        avg_ticket_rupees=105,
        behaviour="thin_in_flood",
    ),
    ShopSpec(
        shop_id="shop_12",
        name="Saree shop",
        owner="Kavya",
        category="saree",
        lat=13.0412,
        lon=80.2512,
        staging_order_id="ORD-STG-SHOP-12",
        target_daily_rupees=14200,
        avg_ticket_rupees=710,
        behaviour="qr_switch_from_19_oct",
    ),
)


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _hourly_weights() -> dict[int, float]:
    """Two-peak daily rhythm: 08:00-10:00 and 18:00-21:00 IST."""
    raw: dict[int, float] = {}
    for h in HOURS_IST:
        if 8 <= h <= 10:
            raw[h] = 2.4
        elif 18 <= h <= 21:
            raw[h] = 2.6
        elif 11 <= h <= 14:
            raw[h] = 1.1
        else:
            raw[h] = 0.6
    total = sum(raw.values())
    return {h: w / total for h, w in raw.items()}


HOUR_WEIGHTS: dict[int, float] = _hourly_weights()


def _day_activity_multiplier(spec: ShopSpec, day: date) -> float:
    """Return multiplier for a shop on a given calendar day (0.0 = closed, 1.0 = normal)."""
    beh = spec.behaviour

    # Weekly holidays
    if beh == "monday_holiday_flood_drop" and day.weekday() == 0:
        return 0.0
    if beh == "tuesday_holiday_flood_drop" and day.weekday() == 1:
        return 0.0

    # Pre-event leave or QR switch
    if beh == "leave_from_18_oct" and day >= date(2026, 10, 18):
        return 0.0
    if beh == "qr_switch_from_19_oct" and day >= date(2026, 10, 19):
        return 0.0

    # Flood event on 21 Oct 2026 and aftermath on 22 Oct 2026
    if day == date(2026, 10, 21):
        if beh == "thin_in_flood":
            return 0.52  # Keeps trading (thin), well above 30% drop threshold
        return 0.0  # Dropped in the flood

    if day == date(2026, 10, 22):
        if beh == "hero_flood_drop":
            return 0.0  # Selvi drops on 21 and 22 Oct
        if beh == "thin_in_flood":
            return 0.70
        return 0.65

    return 1.0


def _simulate_hour(
    rng: np.random.Generator,
    expected_daily_count: float,
    avg_ticket_paise: int,
    hour_weight: float,
    day_multiplier: float,
) -> tuple[int, int]:
    """Simulate (n_payments, amount_paise) for one hour using Poisson count and log-normal tickets."""
    if day_multiplier <= 0.0:
        return 0, 0

    lam = expected_daily_count * hour_weight * day_multiplier
    n_payments = int(rng.poisson(lam))
    if n_payments <= 0:
        if day_multiplier >= 0.45 and hour_weight >= 0.10:
            n_payments = 1
        else:
            return 0, 0

    sigma = 0.28
    mu = float(np.log(avg_ticket_paise)) - 0.5 * (sigma**2)
    tickets = rng.lognormal(mean=mu, sigma=sigma, size=n_payments)
    rounded_paise = int(np.sum(np.round(tickets, -2)))
    return n_payments, max(rounded_paise, n_payments * 100)


def generate_shops_and_street(rng: np.random.Generator) -> None:
    """Write data/shops.csv and data/street.csv."""
    shops_rows = [
        {
            "shop_id": s.shop_id,
            "name": s.name,
            "owner": s.owner,
            "category": s.category,
            "lat": s.lat,
            "lon": s.lon,
            "plan_active": True,
            "staging_order_id": s.staging_order_id,
        }
        for s in SHOPS
    ]
    shops_df = pd.DataFrame(shops_rows)
    shops_df.to_csv(DATA_DIR / "shops.csv", index=False, lineterminator="\n")

    all_days = _date_range(START_DAY, END_DAY)
    street_rows: list[dict[str, object]] = []

    for spec in SHOPS:
        expected_daily_count = spec.target_daily_rupees / spec.avg_ticket_rupees
        avg_ticket_paise = spec.avg_ticket_rupees * 100
        for day in all_days:
            mult = _day_activity_multiplier(spec, day)
            for hour in HOURS_IST:
                n_pay, amt_paise = _simulate_hour(
                    rng=rng,
                    expected_daily_count=expected_daily_count,
                    avg_ticket_paise=avg_ticket_paise,
                    hour_weight=HOUR_WEIGHTS[hour],
                    day_multiplier=mult,
                )
                ts_hour = f"{day.isoformat()}T{hour:02d}:00:00+05:30"
                street_rows.append(
                    {
                        "shop_id": spec.shop_id,
                        "ts_hour": ts_hour,
                        "n_payments": n_pay,
                        "amount_paise": amt_paise,
                    }
                )

    street_df = pd.DataFrame(street_rows)
    street_df.to_csv(DATA_DIR / "street.csv", index=False, lineterminator="\n")


def generate_rain_fixture() -> dict[str, float]:
    """Write data/rain.json matching Open-Meteo archive format."""
    all_days = _date_range(START_DAY, END_DAY)
    daily_rain: dict[str, float] = {}
    for d in all_days:
        iso = d.isoformat()
        if d == date(2026, 10, 20):
            daily_rain[iso] = 17.7
        elif d == date(2026, 10, 21):
            daily_rain[iso] = 27.7
        elif d == date(2026, 10, 22):
            daily_rain[iso] = 19.2
        elif d in (date(2026, 10, 4), date(2026, 10, 11)):
            daily_rain[iso] = 4.2
        elif d == date(2026, 10, 15):
            daily_rain[iso] = 8.5
        else:
            daily_rain[iso] = 0.0

    payload = {
        "latitude": 13.04,
        "longitude": 80.25,
        "generationtime_ms": 0.42,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 11.0,
        "daily_units": {
            "time": "iso8601",
            "precipitation_sum": "mm",
        },
        "daily": {
            "time": list(daily_rain.keys()),
            "precipitation_sum": list(daily_rain.values()),
        },
    }
    (DATA_DIR / "rain.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return daily_rain


def _simulate_daily_series(
    rng: np.random.Generator,
    days: list[date],
    daily_rupees: int,
    avg_ticket_rupees: int,
    multipliers: dict[date, float],
) -> list[tuple[date, int, int]]:
    """Simulate daily (day, n_payments, amount_paise) for one shop across `days`."""
    expected_count = daily_rupees / avg_ticket_rupees
    avg_ticket_paise = avg_ticket_rupees * 100
    sigma = 0.22
    mu = float(np.log(avg_ticket_paise)) - 0.5 * (sigma**2)

    records: list[tuple[date, int, int]] = []
    for d in days:
        mult = multipliers.get(d, 1.0)
        if mult <= 0.0:
            records.append((d, 0, 0))
            continue
        n_pay = max(4, int(rng.poisson(expected_count * mult)))
        tickets = rng.lognormal(mean=mu, sigma=sigma, size=n_pay)
        amt = int(np.sum(np.round(tickets, -2)))
        records.append((d, n_pay, max(amt, n_pay * 100)))
    return records


def generate_eval_set(rng: np.random.Generator) -> None:
    """Generate the 200-case eval set (140 tuning / 60 held_out) in data/eval_shopweeks.csv and data/eval/."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    all_days = _date_range(START_DAY, END_DAY)

    # Scenario definitions: (scenario, true_label, expected_decision, tuning_count, held_out_count)
    # Total = 70 normal + 60 flood_street + 20 leave + 15 illness + 15 qr_switch + 10 weekly_holiday + 10 power_cut = 200
    # Split = 140 tuning + 60 held_out
    scenario_specs: list[tuple[str, str, str, int, int]] = [
        ("normal", "normal", "none", 49, 21),
        ("flood_street", "flood_closure", "file", 42, 18),
        ("leave", "leave", "ask", 14, 6),
        ("illness", "illness", "ask", 11, 4),
        ("qr_switch", "qr_switch", "ask", 10, 5),
        ("weekly_holiday", "weekly_holiday", "ask", 7, 3),
        ("power_cut", "power_cut", "ask", 7, 3),
    ]

    raw_cases: list[dict[str, object]] = []
    for scenario, true_label, expected_decision, n_tune, n_hold in scenario_specs:
        for i in range(n_tune + n_hold):
            split = "tuning" if i < n_tune else "held_out"
            raw_cases.append(
                {
                    "scenario": scenario,
                    "true_label": true_label,
                    "expected_decision": expected_decision,
                    "split": split,
                    "sub_index": i,
                    "within_split_index": i if i < n_tune else i - n_tune,
                }
            )

    # Deterministic shuffle of case order
    order = rng.permutation(len(raw_cases))
    shuffled_cases = [raw_cases[int(idx)] for idx in order]

    profiles = [
        ("flowers", 3200, 80),
        ("tea", 2500, 35),
        ("fruit", 2900, 75),
        ("tailor", 4300, 215),
        ("mobile_repair", 5500, 275),
        ("bakery", 4900, 125),
        ("footwear", 6300, 315),
        ("stationery", 3700, 95),
        ("saree", 12500, 625),
        ("grocery", 9200, 180),
    ]

    manifest_rows: list[dict[str, object]] = []

    for idx, item in enumerate(shuffled_cases, start=1):
        case_id = f"case_{idx:03d}"
        scenario = str(item["scenario"])
        true_label = str(item["true_label"])
        expected_decision = str(item["expected_decision"])
        split = str(item["split"])
        sub_idx = int(item["sub_index"])
        split_idx = int(item["within_split_index"])

        prof_name, daily_rs, ticket_rs = profiles[idx % len(profiles)]
        mults: dict[date, float] = {d: 1.0 for d in all_days}

        # Default street context on EVENT_DAY (21 Oct 2026):
        # 10 peer shops on the street so quorum is computed across 10 shops total
        peer_dropped_count = 1
        rain_mm = 1.2

        if scenario == "normal":
            # Normal day, shop trades normally
            peer_dropped_count = int(rng.integers(0, 2))
            rain_mm = float(np.round(rng.uniform(0.0, 6.0), 1))
            mults[EVENT_DAY] = float(rng.uniform(0.80, 1.20))

        elif scenario == "flood_street":
            peer_dropped_count = int(rng.integers(7, 9))
            rain_mm = float(np.round(rng.uniform(21.0, 42.0), 1))
            mults[EVENT_DAY] = 0.0

            # Include shops with regular weekly holidays 1 or 2 days before the flood
            if split_idx % 6 == 1:
                for d in all_days:
                    if d.weekday() == 0:  # Monday weekly holiday (19 Oct)
                        mults[d] = 0.0
            elif split_idx % 6 == 2:
                for d in all_days:
                    if d.weekday() == 1:  # Tuesday weekly holiday (20 Oct)
                        mults[d] = 0.0

            # Realistic edge case: 1 case in held_out (and 2 in tuning) has borderline partial trading (34% of baseline)
            if (split == "held_out" and split_idx == 17) or (
                split == "tuning" and split_idx in (40, 41)
            ):
                mults[EVENT_DAY] = 0.42

        elif scenario == "leave":
            mults[EVENT_DAY] = 0.0
            # DATA_SPEC.md: "20 leave (including 5 that start 1 to 3 days before a flood)"
            # 3 in tuning (split_idx 0, 1, 2) and 2 in held_out (split_idx 0, 1) = 5 pre-flood leaves
            is_pre_flood_leave = (split == "tuning" and split_idx in (0, 1, 2)) or (
                split == "held_out" and split_idx in (0, 1)
            )
            if is_pre_flood_leave:
                peer_dropped_count = 8
                rain_mm = 27.7
                days_before = (sub_idx % 3) + 1  # 1, 2, or 3 days before the flood
                for offset in range(1, days_before + 1):
                    mults[EVENT_DAY - timedelta(days=offset)] = 0.0
            else:
                peer_dropped_count = 0
                rain_mm = 0.0
                for offset in range(1, (sub_idx % 3) + 2):
                    mults[EVENT_DAY - timedelta(days=offset)] = 0.0

        elif scenario == "illness":
            # Lone drop on a normal day
            peer_dropped_count = 0
            rain_mm = float(np.round(rng.uniform(0.0, 4.0), 1))
            mults[EVENT_DAY] = 0.0

        elif scenario == "qr_switch":
            mults[EVENT_DAY] = 0.0
            # Realistic edge case: 1 QR switch in held_out (and 1 in tuning) happens on the exact morning of a flood
            if (split == "held_out" and split_idx == 4) or (split == "tuning" and split_idx == 9):
                peer_dropped_count = 8
                rain_mm = 27.7
            elif split_idx % 2 == 0:
                # Switched QR 2 days before a flood -> caught by eligibility check!
                peer_dropped_count = 8
                rain_mm = 27.7
                mults[EVENT_DAY - timedelta(days=1)] = 0.0
                mults[EVENT_DAY - timedelta(days=2)] = 0.0
            else:
                # Switched QR on a non-flood day -> lone drop
                peer_dropped_count = 0
                rain_mm = 0.0

        elif scenario == "weekly_holiday":
            # Shop closed for its weekly holiday on a non-flood day (Wednesday holiday)
            peer_dropped_count = 0
            rain_mm = 0.0
            for d in all_days:
                if d.weekday() == EVENT_DAY.weekday():
                    mults[d] = 0.0

        elif scenario == "power_cut":
            # Street quorum met, but no rain (< 15 mm)
            peer_dropped_count = 8
            rain_mm = float(np.round(rng.uniform(0.0, 4.5), 1))
            mults[EVENT_DAY] = 0.0

        target_series = _simulate_daily_series(
            rng=rng,
            days=all_days,
            daily_rupees=daily_rs,
            avg_ticket_rupees=ticket_rs,
            multipliers=mults,
        )

        # Write per-case daily series CSV in data/eval/{case_id}.csv
        rel_series_path = f"eval/{case_id}.csv"
        case_rows = [
            {
                "day": d.isoformat(),
                "n_payments": n_pay,
                "amount_paise": amt_paise,
            }
            for d, n_pay, amt_paise in target_series
        ]
        pd.DataFrame(case_rows).to_csv(
            DATA_DIR / rel_series_path,
            index=False,
            lineterminator="\n",
        )

        manifest_rows.append(
            {
                "case_id": case_id,
                "shop_profile": prof_name,
                "scenario": scenario,
                "true_label": true_label,
                "expected_decision": expected_decision,
                "split": split,
                "series_path": rel_series_path,
                "event_day": EVENT_DAY.isoformat(),
                "peer_shops_total": 9,
                "peer_shops_dropped": peer_dropped_count,
                "rain_mm": rain_mm,
            }
        )

    manifest_df = pd.DataFrame(manifest_rows)
    manifest_df.to_csv(DATA_DIR / "eval_shopweeks.csv", index=False, lineterminator="\n")


def main() -> None:
    """Generate all deterministic datasets in api/data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    generate_shops_and_street(rng)
    generate_rain_fixture()
    generate_eval_set(rng)
    print(f"Generated deterministic data (seed={SEED}) in {DATA_DIR}")


if __name__ == "__main__":
    main()
