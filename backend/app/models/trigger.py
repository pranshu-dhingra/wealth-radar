"""Pydantic v2 schemas for triggers and priority scoring."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    RMD_DUE = "RMD_DUE"
    RMD_APPROACHING = "RMD_APPROACHING"
    PORTFOLIO_DRIFT = "PORTFOLIO_DRIFT"
    TLH_OPPORTUNITY = "TLH_OPPORTUNITY"
    ROTH_WINDOW = "ROTH_WINDOW"
    QCD_OPPORTUNITY = "QCD_OPPORTUNITY"
    ESTATE_REVIEW_OVERDUE = "ESTATE_REVIEW_OVERDUE"
    MEETING_OVERDUE = "MEETING_OVERDUE"
    LIFE_EVENT_RECENT = "LIFE_EVENT_RECENT"
    BENEFICIARY_REVIEW = "BENEFICIARY_REVIEW"
    MARKET_EVENT = "MARKET_EVENT"
    APPROACHING_MILESTONE = "APPROACHING_MILESTONE"


class Trigger(BaseModel):
    trigger_type: TriggerType
    client_id: str
    base_urgency: float = Field(..., ge=0, le=100)
    revenue_impact: float = Field(..., ge=0, le=100)
    details: Optional[str] = None


class PrioritizedTrigger(BaseModel):
    """Trigger with computed priority score after applying compound bonuses and tier multiplier."""
    trigger: Trigger
    co_occurring_triggers: List[TriggerType] = []
    priority_score: float
    tier_multiplier: float
