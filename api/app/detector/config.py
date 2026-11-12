"""Detector thresholds and rule version from docs/DATA_SPEC.md."""

RULES_VERSION: str = "2026.11-a"

# Baseline & history thresholds
BASELINE_TRADING_DAYS: int = 28
MIN_TRADING_DAYS: int = 14

# Drop & street quorum thresholds
DROP_RATIO_THRESHOLD: float = 0.30
STREET_QUORUM_SHARE: float = 0.60

# Weather confirmation gate (Open-Meteo daily precipitation_sum in mm)
RAIN_GATE_MM: float = 15.0

# Pre-event activity eligibility window (at least 2 of the 3 calendar days before event)
ELIGIBILITY_LOOKBACK_DAYS: int = 3
ELIGIBILITY_MIN_ACTIVE_DAYS: int = 2

# Plan-fee refund constants (Rs 35 = 3,500 paise, once per shop per calendar month)
PLAN_FEE_PAISE: int = 3500
MAX_REFUNDS_PER_SHOP_PER_MONTH: int = 1
