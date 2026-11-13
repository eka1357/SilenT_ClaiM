"""Stateless 'Try to fool it' lab endpoint calling the real deterministic rules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.detector.baseline import DailyIncome, ShopHistory
from app.detector.rules import DecisionOutcome, DecisionReason, decide

router = APIRouter(prefix="/api/lab", tags=["lab"])

LAB_EVENT_DAY = date(2026, 10, 21)
LAB_BASELINE_PAISE = 320_000
LAB_STREET_SIZE = 12


class LabDecideRequest(BaseModel):
    """Inputs from the /lab interactive controls."""

    shops_closed: int = Field(default=9, ge=0, le=12)
    rain_mm: float = Field(default=28.0, ge=0.0, le=60.0)
    sales_today_pct: float = Field(default=0.0, ge=0.0, le=150.0)
    days_traded_before: int = Field(default=3, ge=0, le=3)
    regular_weekly_holiday: Literal["none", "yesterday", "today"] = "none"
    weekly_holiday_yesterday: bool | None = None


class LabDecideResponse(BaseModel):
    """Decision, plain-English reason, and next step from detector/rules.py."""

    decision: Literal["file", "ask", "none"]
    decision_label: str
    reason: str
    explanation: str
    next_step: str
    shops_closed_effective: int
    quorum_share: float
    quorum_met: bool
    rain_mm: float
    rain_gate_met: bool
    dropped: bool
    eligible: bool
    rules_version: str


def _resolve_holiday_mode(
    req: LabDecideRequest,
) -> Literal["none", "yesterday", "today"]:
    if req.regular_weekly_holiday != "none":
        return req.regular_weekly_holiday
    if req.weekly_holiday_yesterday is True:
        return "yesterday"
    return "none"


def _build_synthetic_street(
    req: LabDecideRequest,
) -> tuple[ShopHistory, list[ShopHistory]]:
    """Construct a 12-shop synthetic street history matching the slider inputs."""
    holiday_mode = _resolve_holiday_mode(req)

    # Which of the 3 days immediately before LAB_EVENT_DAY (offsets 3, 2, 1) are active?
    if req.days_traded_before == 3:
        active_recent_offsets = {1, 2, 3}
    elif req.days_traded_before == 2:
        # When yesterday is the recurring weekly holiday, offset 1 is the closed day
        # and offsets 2 and 3 are the 2 active trading days.
        if holiday_mode == "yesterday":
            active_recent_offsets = {2, 3}
        else:
            active_recent_offsets = {1, 2}
    elif req.days_traded_before == 1:
        active_recent_offsets = {3}
    else:
        active_recent_offsets = set()

    target_days: list[DailyIncome] = []
    # 38 prior calendar days ensure >= 28 active trading days even with weekly holidays
    for offset in range(38, 0, -1):
        d = LAB_EVENT_DAY - timedelta(days=offset)
        if offset in (1, 2, 3):
            is_active = offset in active_recent_offsets
        elif (holiday_mode == "today" and offset in (7, 14, 21, 28, 35)) or (
            holiday_mode == "yesterday" and offset in (8, 15, 22, 29, 36)
        ):
            is_active = False
        else:
            is_active = True

        target_days.append(
            DailyIncome(
                day=d,
                amount_paise=LAB_BASELINE_PAISE if is_active else 0,
                n_payments=30 if is_active else 0,
            )
        )

    today_paise = round(LAB_BASELINE_PAISE * (req.sales_today_pct / 100.0))
    today_payments = 0 if today_paise == 0 else max(1, round(30 * (req.sales_today_pct / 100.0)))
    target_days.append(
        DailyIncome(
            day=LAB_EVENT_DAY,
            amount_paise=today_paise,
            n_payments=today_payments,
        )
    )
    target_shop = ShopHistory(shop_id="shop_01", days=tuple(target_days))

    target_dropped = today_paise <= (LAB_BASELINE_PAISE * 0.25)
    if target_dropped:
        peer_closed_count = min(
            LAB_STREET_SIZE - 1,
            max(0, req.shops_closed - 1),
        )
    else:
        peer_closed_count = min(LAB_STREET_SIZE - 1, max(0, req.shops_closed))

    peer_base_days = tuple(
        DailyIncome(
            day=LAB_EVENT_DAY - timedelta(days=offset),
            amount_paise=LAB_BASELINE_PAISE,
            n_payments=30,
        )
        for offset in range(38, 0, -1)
    )

    street: list[ShopHistory] = [target_shop]
    for idx in range(LAB_STREET_SIZE - 1):
        is_peer_closed = idx < peer_closed_count
        peer_today = DailyIncome(
            day=LAB_EVENT_DAY,
            amount_paise=0 if is_peer_closed else LAB_BASELINE_PAISE,
            n_payments=0 if is_peer_closed else 30,
        )
        street.append(
            ShopHistory(
                shop_id=f"shop_{idx + 2:02d}",
                days=(*peer_base_days, peer_today),
            )
        )

    return target_shop, street


def _format_decision_copy(
    req: LabDecideRequest,
    decision: DecisionOutcome,
    reason: DecisionReason,
    closed_count: int,
    quorum_share: float,
    rain_mm: float,
) -> tuple[str, str, str]:
    if decision == DecisionOutcome.FILE:
        decision_label = "Files the claim"
        next_step = (
            "asks one consent question in Tamil, files the evidence pack after "
            "one tap, and returns the ₹35 plan fee"
        )
    elif decision == DecisionOutcome.ASK:
        decision_label = "Asks first"
        next_step = "asks in Tamil and pays nothing until answered"
    else:
        decision_label = "No action"
        next_step = "stays quiet, sends no message, and files no claim"

    quorum_pct = round(quorum_share * 100)
    if reason == DecisionReason.FLOOD_QUORUM_AND_RAIN:
        explanation = (
            f"Sales dropped to {req.sales_today_pct:g}% of baseline, "
            f"{closed_count} of {LAB_STREET_SIZE} shops on the street shut "
            f"({quorum_pct}% quorum, threshold 60%), and {rain_mm:g} mm of rain "
            "crossed the 15 mm threshold."
        )
    elif reason == DecisionReason.WEEKLY_HOLIDAY:
        explanation = (
            "Today matches the shop's recurring weekly closing day across the "
            "previous 4 weeks, so the silence is expected and no income was lost."
        )
    elif reason == DecisionReason.NOT_DROPPED:
        explanation = (
            f"Sales today are {req.sales_today_pct:g}% of baseline (above the "
            "25% drop threshold), so the shop is still trading."
        )
    elif reason == DecisionReason.INACTIVE_BEFORE_EVENT:
        explanation = (
            f"The shop traded on {req.days_traded_before} of the 3 days before "
            "today without a recurring weekly holiday yesterday, so it may "
            "already have been on leave or using another QR."
        )
    elif reason == DecisionReason.NO_RAIN_SIGNAL:
        explanation = (
            f"{closed_count} of {LAB_STREET_SIZE} shops shut ({quorum_pct}% "
            f"quorum), but {rain_mm:g} mm of rain is below the 15 mm threshold "
            "(for example, a bandh, strike, or power cut)."
        )
    elif reason == DecisionReason.LONE_DROP:
        explanation = (
            f"Only {closed_count} of {LAB_STREET_SIZE} shops on the street shut "
            f"({quorum_pct}%, below the 60% street quorum), so the closure looks "
            "specific to this shop."
        )
    else:
        explanation = (
            "The shop has fewer than 14 prior trading days, so its baseline is not established yet."
        )

    return decision_label, explanation, next_step


@router.post("/decide", response_model=LabDecideResponse)
def decide_lab_scenario(req: LabDecideRequest) -> LabDecideResponse:
    """Run the production decide() function against synthetic street histories.

    Stateless: never creates asks, claims, batches, or refunds.
    """
    target_shop, street = _build_synthetic_street(req)
    result = decide(
        shop=target_shop,
        day=LAB_EVENT_DAY,
        street=street,
        rain=req.rain_mm,
    )
    closed_count = round(result.quorum_share * LAB_STREET_SIZE)
    decision_label, explanation, next_step = _format_decision_copy(
        req=req,
        decision=result.decision,
        reason=result.reason,
        closed_count=closed_count,
        quorum_share=result.quorum_share,
        rain_mm=result.rain_mm,
    )
    return LabDecideResponse(
        decision=result.decision.value,
        decision_label=decision_label,
        reason=result.reason.value,
        explanation=explanation,
        next_step=next_step,
        shops_closed_effective=closed_count,
        quorum_share=result.quorum_share,
        quorum_met=result.quorum_met,
        rain_mm=result.rain_mm,
        rain_gate_met=result.rain_gate_met,
        dropped=result.dropped,
        eligible=result.eligible,
        rules_version=result.rules_version,
    )
