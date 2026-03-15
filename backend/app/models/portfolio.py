"""Pydantic v2 schemas for portfolio holdings and allocations."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Holding(BaseModel):
    ticker: str
    name: str
    shares: float
    price: float
    market_value: float
    asset_class: str
    account_type: str  # e.g. "taxable", "traditional_ira", "roth_ira"


class TargetAllocation(BaseModel):
    asset_class: str
    target_pct: float = Field(..., ge=0, le=100)
    current_pct: float = Field(..., ge=0, le=100)

    @property
    def drift(self) -> float:
        # Absolute drift — alert threshold is 5%
        return abs(self.current_pct - self.target_pct)


class Portfolio(BaseModel):
    client_id: str
    total_value: float
    holdings: List[Holding] = []
    allocations: List[TargetAllocation] = []
