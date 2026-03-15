"""Pydantic v2 schemas for client profiles."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClientTier(str, Enum):
    A = "A"  # $1M+ AUM
    B = "B"  # $500K–$1M
    C = "C"  # $200K–$500K
    D = "D"  # <$200K


class Client(BaseModel):
    id: str
    name: str
    date_of_birth: date
    tier: ClientTier
    aum: float = Field(..., description="Assets under management in USD")
    email: Optional[str] = None
    phone: Optional[str] = None
    last_meeting: Optional[date] = None
    notes: Optional[str] = None
