"""Pydantic state schema for the Silent Claim LangGraph workflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClaimState(BaseModel):
    """State carried across sense -> confirm -> ask -> classify -> file/close/human_review."""

    shop_id: str
    day: str  # ISO calendar date YYYY-MM-DD (Asia/Kolkata)
    street_id: str = "panagal_park_road"
    detection: dict[str, Any] = Field(default_factory=dict)
    ask: dict[str, Any] = Field(default_factory=dict)
    claim: dict[str, Any] = Field(default_factory=dict)
    refund: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    live_flags: dict[str, bool] = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)
    terminal_status: str = ""
