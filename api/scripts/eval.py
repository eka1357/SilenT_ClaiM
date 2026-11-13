"""Evaluate detector rules on the 60 held-out shop-weeks in api/data/eval_shopweeks.csv.

Reports (matching docs/DATA_SPEC.md Metrics):
- Wrong-claim share = filed claims whose true label != `flood_closure`, divided by all filed claims
  ("of N claims filed, M were right").
- False-positive rate = non-flood cases decided `file`, divided by all non-flood cases.
- Missed-claim rate = true `flood_closure` cases not decided `file`, divided by true `flood_closure` cases.
- Confusion matrices and every misclassified case (case_id, scenario, expected, decided, reason,
  day income as % of baseline).
"""

from __future__ import annotations

import json
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
class MisclassifiedCase:
    """Details of a single misclassified evaluation case."""

    case_id: str
    scenario: str
    expected: str
    decided: str
    reason: str
    income_pct_of_baseline: float


@dataclass(frozen=True, slots=True)
class EvalMetrics:
    """Summary metrics on an evaluation split."""

    split: str
    total_cases: int
    flood_cases: int
    non_flood_cases: int
    claims_filed: int
    claims_right: int
    wrong_claims: int
    wrong_claim_share: float
    false_positive_rate: float
    missed_claims: int
    missed_claim_rate: float
    decision_matrix: dict[str, dict[str, int]]
    binary_matrix: dict[str, dict[str, int]]
    misclassified: tuple[MisclassifiedCase, ...]


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
    """Run decide() across all cases in `split` and compute DATA_SPEC.md metrics."""
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
    non_flood_cases = 0
    claims_filed = 0
    claims_right = 0
    wrong_claims = 0
    missed_claims = 0
    misclassified: list[MisclassifiedCase] = []

    for _, row in split_df.iterrows():
        case_id = str(row["case_id"])
        scenario = str(row["scenario"])
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

        if is_pred_file:
            claims_filed += 1
            if is_true_flood:
                claims_right += 1
            else:
                wrong_claims += 1

        if is_true_flood:
            flood_cases += 1
            if is_pred_file:
                binary_matrix["flood_closure"]["file"] += 1
            else:
                binary_matrix["flood_closure"]["not_file"] += 1
                missed_claims += 1
        else:
            non_flood_cases += 1
            if is_pred_file:
                binary_matrix["not_flood_closure"]["file"] += 1
            else:
                binary_matrix["not_flood_closure"]["not_file"] += 1

        if pred != expected_decision or is_pred_file != is_true_flood:
            income_pct = (
                (100.0 * result.day_income_paise / result.baseline_paise)
                if result.baseline_paise > 0
                else 0.0
            )
            misclassified.append(
                MisclassifiedCase(
                    case_id=case_id,
                    scenario=scenario,
                    expected=expected_decision,
                    decided=pred,
                    reason=result.reason.value,
                    income_pct_of_baseline=income_pct,
                )
            )

    wrong_claim_share = wrong_claims / claims_filed if claims_filed > 0 else 0.0
    false_positive_rate = wrong_claims / non_flood_cases if non_flood_cases > 0 else 0.0
    missed_claim_rate = missed_claims / flood_cases if flood_cases > 0 else 0.0

    return EvalMetrics(
        split=split,
        total_cases=total_cases,
        flood_cases=flood_cases,
        non_flood_cases=non_flood_cases,
        claims_filed=claims_filed,
        claims_right=claims_right,
        wrong_claims=wrong_claims,
        wrong_claim_share=wrong_claim_share,
        false_positive_rate=false_positive_rate,
        missed_claims=missed_claims,
        missed_claim_rate=missed_claim_rate,
        decision_matrix=decision_matrix,
        binary_matrix=binary_matrix,
        misclassified=tuple(misclassified),
    )


def write_eval_results_json(
    metrics: EvalMetrics,
    output_path: Path = DATA_DIR / "eval_results.json",
) -> Path:
    """Persist held-out evaluation summary to api/data/eval_results.json for GET /api/metrics."""
    payload = {
        "rules_version": RULES_VERSION,
        "split": metrics.split,
        "label": "Simulated eval",
        "total_cases": metrics.total_cases,
        "claims_filed": metrics.claims_filed,
        "claims_right": metrics.claims_right,
        "wrong_claims": metrics.wrong_claims,
        "wrong_claim_share": round(metrics.wrong_claim_share, 6),
        "false_positive_rate": round(metrics.false_positive_rate, 6),
        "closures_missed": metrics.missed_claims,
        "total_closures": metrics.flood_cases,
        "missed_claim_rate": round(metrics.missed_claim_rate, 6),
        "non_flood_cases": metrics.non_flood_cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    """Print held-out evaluation metrics, confusion matrices, and misclassified cases."""
    metrics = evaluate_split("held_out")
    write_eval_results_json(metrics)
    print(f"Silent Claim Detector Evaluation (RULES_VERSION={RULES_VERSION})")
    print("Dataset: 200 simulated shop-weeks (140 tuning / 60 held-out)")
    print(f"Split reported: {metrics.split} (n={metrics.total_cases})")
    print("-" * 72)
    print(
        f"Claims filed      : of {metrics.claims_filed} claims filed, "
        f"{metrics.claims_right} were right "
        f"(wrong-claim share: {metrics.wrong_claim_share * 100:.2f}%, "
        f"{metrics.wrong_claims}/{metrics.claims_filed}; target <= 10.0%)"
    )
    print(
        f"False-positive rate: {metrics.false_positive_rate * 100:.2f}% "
        f"({metrics.wrong_claims}/{metrics.non_flood_cases} non-flood cases)"
    )
    print(
        f"Missed-claim rate  : {metrics.missed_claim_rate * 100:.2f}% "
        f"({metrics.missed_claims}/{metrics.flood_cases} flood_closure cases; target <= 10.0%)"
    )
    print("-" * 72)
    print("Binary Confusion Matrix (True Label vs Filed):")
    bin_header = "True / Predicted"
    print(f"{bin_header:<22} {'file':>10} {'not_file':>10}")
    for row_key in ("flood_closure", "not_flood_closure"):
        f_cnt = metrics.binary_matrix[row_key]["file"]
        nf_cnt = metrics.binary_matrix[row_key]["not_file"]
        print(f"{row_key:<22} {f_cnt:>10} {nf_cnt:>10}")
    print("-" * 72)
    print("Decision Confusion Matrix (Expected vs Decided):")
    dec_header = "Expected / Decided"
    print(f"{dec_header:<22} {'file':>8} {'ask':>8} {'none':>8}")
    for exp in ("file", "ask", "none"):
        r = metrics.decision_matrix[exp]
        print(f"{exp:<22} {r['file']:>8} {r['ask']:>8} {r['none']:>8}")
    print("-" * 72)
    print(f"Misclassified cases ({len(metrics.misclassified)}):")
    if not metrics.misclassified:
        print("  (none)")
    else:
        print(
            f"  {'case_id':<10} {'scenario':<15} {'expected':<10} "
            f"{'decided':<9} {'reason':<23} {'day_income_%_baseline'}"
        )
        for item in metrics.misclassified:
            print(
                f"  {item.case_id:<10} {item.scenario:<15} {item.expected:<10} "
                f"{item.decided:<9} {item.reason:<23} {item.income_pct_of_baseline:>6.1f}%"
            )


if __name__ == "__main__":
    main()
