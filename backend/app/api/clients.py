"""Client CRUD endpoints.

GET  /api/clients                        list all clients (tier/sort/search filters)
GET  /api/clients/{client_id}            full client detail with holdings
GET  /api/clients/{client_id}/triggers   run trigger scan for one client
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/clients", tags=["clients"])

_DATA_DIR = Path(__file__).parent.parent / "data"

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_clients() -> list[dict[str, Any]]:
    with open(_DATA_DIR / "clients.json", encoding="utf-8") as f:
        return json.load(f)


def _load_holdings() -> dict[str, list[dict[str, Any]]]:
    with open(_DATA_DIR / "holdings.json", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return raw
    grouped: dict[str, list] = {}
    for h in raw:
        grouped.setdefault(h.get("client_id", ""), []).append(h)
    return grouped


def _find_client(client_id: str, clients: list[dict]) -> dict | None:
    return next((c for c in clients if c.get("id") == client_id), None)


def _client_summary(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "first_name": c.get("first_name"),
        "last_name": c.get("last_name"),
        "tier": c.get("tier"),
        "aum": c.get("aum"),
        "age": c.get("age"),
        "email": c.get("email"),
        "phone": c.get("phone"),
        "occupation": c.get("occupation"),
        "risk_tolerance": c.get("risk_tolerance"),
        "tax_bracket": c.get("tax_bracket"),
        "last_meeting_date": c.get("last_meeting_date"),
        "has_portfolio_drift": c.get("has_portfolio_drift", False),
        "marital_status": c.get("marital_status"),
        "state": (c.get("address") or {}).get("state"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_clients(
    tier: Optional[str] = Query(None, description="Filter by tier: A, B, C, or D"),
    sort: Optional[str] = Query("aum", description="Sort field: aum | name | tier | priority"),
    search: Optional[str] = Query(None, description="Search by name, id, or email"),
    limit: int = Query(50, ge=1, le=50),
) -> list[dict]:
    """List all clients with optional filtering and sorting."""
    clients = _load_clients()

    if tier:
        clients = [c for c in clients if c.get("tier", "").upper() == tier.upper()]

    if search:
        q = search.lower()
        clients = [
            c for c in clients
            if q in c.get("name", "").lower()
            or q in c.get("id", "").lower()
            or q in c.get("email", "").lower()
        ]

    sort_key = (sort or "aum").lower()
    if sort_key == "name":
        clients.sort(key=lambda c: c.get("name", ""))
    elif sort_key == "tier":
        clients.sort(key=lambda c: TIER_ORDER.get(c.get("tier", "D"), 3))
    else:  # default: aum descending
        clients.sort(key=lambda c: c.get("aum", 0), reverse=True)

    return [_client_summary(c) for c in clients[:limit]]


@router.get("/{client_id}")
async def get_client(client_id: str) -> dict:
    """Full client detail including accounts, current/target allocation, and holdings."""
    clients = _load_clients()
    client = _find_client(client_id, clients)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")

    all_holdings = _load_holdings()
    holdings = all_holdings.get(client_id, [])

    return {**client, "holdings": holdings}


@router.get("/{client_id}/triggers")
async def get_client_triggers(client_id: str) -> dict:
    """Run the full trigger scan for a single client and return prioritised results."""
    from app.agents.sentinel_agent import scan_client_triggers
    result = json.loads(scan_client_triggers(client_id))
    if "error" in result and not result.get("client_name"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result
