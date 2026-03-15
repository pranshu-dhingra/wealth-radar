"""Pydantic v2 schemas for client action packages."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ActionItem(BaseModel):
    title: str
    description: str
    priority: str  # "high" | "medium" | "low"
    category: str  # e.g. "rmd", "tax", "estate", "portfolio"


class EmailDraft(BaseModel):
    subject: str
    body: str


class ActionPackage(BaseModel):
    client_id: str
    generated_at: datetime
    summary: str
    action_items: List[ActionItem] = []
    email_draft: Optional[EmailDraft] = None
    meeting_agenda: Optional[List[str]] = None
