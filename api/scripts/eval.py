"""Evaluate detector rules on the 60 held-out shop-weeks in api/data/eval_shopweeks.csv.

Reports:
- False-claim rate = cases decided `file` whose true label != `flood_closure`, divided by all cases.
- Missed-claim rate = true `flood_closure` cases not decided `file`, divided by true `flood_closure` cases.
- Confusion matrix on the 60 held-out cases.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.detector.baseline import DailyIncome, ShopHistory
from app.detector.config import RULES_VERSION
from app.detector.rules import DecisionOutcome, decide

DATA_DIR: Path = API_ROOT / "data"


@dataclass(frozen=True, slots=True)
class EvalMetrics:
    """Summary metrics on an evaluation split."""

    split: str
    total_cases: int
    flood_cases: int
    false_claims: int
    false_claim_rate: float
    missed_claims: int
    missed_claim_rate: float
    decision_matrix: dict[str, dict[str, int]]
    binary_matrix: dict[str, dict[str, int]]


def _build_peer_street(
    target_history: ShopHistory,
    event_day: date,
    peer_total: int,
    peer_dropped: int,
) -> list[ShopHistory]:
    """Construct peer ShopHistory objects on the same street for quorum evaluation."""
    start_day = event_day - timedelta(days=27)
    base_days = [
        DailyIncome(day=start_day + timedelta(days=i), amount_paise=400_000, n_payments=20)
        for i in range(27)
    ]

    street: list[ShopHistory] = [target_history]
    for idx in range(peer_total):
        dropped_on_event = idx < peer_dropped
        event_record = (
            DailyIncome(day=event_day, amount_paise=0, n_payments=0)
            if dropped_on_event
            else DailyIncome(day=event_day, amount_paise=400_000, n_payments=20)
        )
        street.append(
            ShopHistory(
                shop_id=f"peer_{idx + 1:02d}",
                days=(*base_days, event_record),
            )
        )
    return street


def evaluate_split(split: str = "held_out") -> EvalMetrics:
    """Run decide() across all cases in `split` and compute false-claim and missed-claim rates."""
    manifest_path = DATA_DIR / "eval_shopweeks.csv"
    manifest_df = pd.read_csv(manifest_path)
    split_df = manifest_df[manifest_df["split"] == split].copy()

    outcomes = ("file", "ask", "none")
    decision_matrix: dict[str, dict[str, int]] = {
        exp: {pred: 0 for pred in outcomes} for exp in outcomes
    }
    binary_matrix: dict[str, dict[str, int]] = {
        "flood_closure": {"file": 0, "not_file": 0},
        "not_flood_closure": {"file": 0, "not_file": 0},
    }

    total_cases = 0
    flood_cases = 0
    false_claims = 0
    missed_claims = 0

    for _, row in split_df.iterrows():
        case_id = str(row["case_id"])
        true_label = str(row["true_label"])
        expected_decision = str(row["expected_decision"])
        series_rel = str(row["series_path"])
        event_day = date.fromisoformat(str(row["event_day"]))
        peer_total = int(row["peer_shops_total"])
        peer_dropped = int(row["peer_shops_dropped"])
        rain_mm = float(row["rain_mm"])

        series_df = pd.read_csv(DATA_DIR / series_rel)
        daily_records = tuple(
            DailyIncome(
                day=date.fromisoformat(str(r["day"])),
                amount_paise=int(r["amount_paise"]),
                n_payments=int(r["n_payments"]),
            )
            for _, r in series_df.iterrows()
        )
        target_history = ShopHistory(shop_id=case_id, days=daily_records)
        street = _build_peer_street(
            target_history=target_history,
            event_day=event_day,
            peer_total=peer_total,
            peer_dropped=peer_dropped,
        )

        result = decide(
            shop=target_history,
            day=event_day,
            street=street,
            rain=rain_mm,
        )
        pred = result.decision.value

        total_cases += 1
        decision_matrix[expected_decision][pred] += 1

        is_true_flood = true_label == "flood_closure"
        is_pred_file = result.decision == DecisionOutcome.FILE

        if is_true_flood:
            flood_cases += 1
            if is_pred_file:
                binary_matrix["flood_closure"]["file"] += 1
            else:
                binary_matrix["flood_closure"]["not_file"] += 1
                missed_claims += 1
        else:
            if is_pred_file:
                binary_matrix["not_flood_closure"]["file"] += 1
                false_claims += 1
            else:
                binary_matrix["not_flood_closure"]["not_file"] += 1

    false_claim_rate = false_claims / total_cases if total_cases > 0 else 0.0
    missed_claim_rate = missed_claims / flood_cases if flood_cases > 0 else 0.0

    return EvalMetrics(
        split=split,
        total_cases=total_cases,
        flood_cases=flood_cases,
        false_claims=false_claims,
        false_claim_rate=false_claim_rate,
        missed_claims=missed_claims,
        missed_claim_rate=missed_claim_rate,
        decision_matrix=decision_matrix,
        binary_matrix=binary_matrix,
    )


def main() -> None:
    """Print held-out evaluation metrics and confusion matrices."""
    metrics = evaluate_split("held_out")
    print(f"Silent Claim Detector Evaluation (RULES_VERSION={RULES_VERSION})")
    print("Dataset: 200 simulated shop-weeks (140 tuning / 60 held-out)")
    print(f"Split reported: {metrics.split} (n={metrics.total_cases})")
    print("-" * 64)
    print(
        f"False-claim rate : {metrics.false_claim_rate * 100:.2f}% "
        f"({metrics.false_claims}/{metrics.total_cases} cases; target <= 5.0%)"
    )
    print(
        f"Missed-claim rate: {metrics.missed_claim_rate * 100:.2f}% "
        f"({metrics.missed_claims}/{metrics.flood_cases} flood_closure cases; target <= 10.0%)"
    )
    print("-" * 64)
    print("Binary Confusion Matrix (True Label vs Filed):")
    bin_header = "True / Predicted"
    print(f"{bin_header:<22} {'file':>10} {'not_file':>10}")
    for row_key in ("flood_closure", "not_flood_closure"):
        f_cnt = metrics.binary_matrix[row_key]["file"]
        nf_cnt = metrics.binary_matrix[row_key]["not_file"]
        print(f"{row_key:<22} {f_cnt:>10} {nf_cnt:>10}")
    print("-" * 64)
    print("Decision Confusion Matrix (Expected vs Decided):")
    dec_header = "Expected / Decided"
    print(f"{dec_header:<22} {'file':>8} {'ask':>8} {'none':>8}")
    for exp in ("file", "ask", "none"):
        r = metrics.decision_matrix[exp]
        print(f"{exp:<22} {r['file']:>8} {r['ask']:>8} {r['none']:>8}")


if __name__ == "__main__":
    main()
