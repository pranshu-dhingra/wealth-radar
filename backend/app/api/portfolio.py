"""Portfolio analysis endpoints.

GET  /api/portfolio/{client_id}                full holdings + allocation snapshot
GET  /api/portfolio/{client_id}/drift          detailed drift analysis (DRIFT tool)
GET  /api/portfolio/{client_id}/opportunities  TLH + Roth + QCD opportunities
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_DATA_DIR = Path(__file__).parent.parent / "data"


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


def _find_client(client_id: str) -> dict | None:
    return next((c for c in _load_clients() if c.get("id") == client_id), None)


@router.get("/{client_id}")
async def get_portfolio(client_id: str) -> dict:
    """Holdings, accounts, and current vs target allocation for a client."""
    client = _find_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")

    holdings = _load_holdings().get(client_id, [])

    # Summarise holdings by asset class (holdings use "current_value" field)
    asset_totals: dict[str, float] = {}
    total_value = sum(float(h.get("current_value", h.get("market_value", 0))) for h in holdings)
    for h in holdings:
        ac = h.get("asset_class", "OTHER")
        asset_totals[ac] = asset_totals.get(ac, 0) + float(h.get("current_value", h.get("market_value", 0)))
    holdings_allocation = {
        ac: round(v / total_value * 100, 2) if total_value else 0
        for ac, v in asset_totals.items()
    }

    return {
        "client_id": client_id,
        "client_name": client.get("name"),
        "tier": client.get("tier"),
        "aum": client.get("aum"),
        "accounts": client.get("accounts", []),
        "target_allocation": client.get("target_allocation", {}),
        "current_allocation": client.get("current_allocation", {}),
        "portfolio_drift": client.get("portfolio_drift", {}),
        "has_portfolio_drift": client.get("has_portfolio_drift", False),
        "holdings": holdings,
        "holdings_allocation": holdings_allocation,
        "total_holdings_value": round(total_value, 2),
    }


@router.get("/{client_id}/drift")
async def get_drift(client_id: str) -> dict:
    """Detailed portfolio drift analysis against IPS target allocation (5% threshold)."""
    from app.agents.sentinel_agent import run_financial_analysis
    result = json.loads(run_financial_analysis(client_id, "DRIFT"))
    if "error" in result and "holdings" in result.get("error", ""):
        # No holdings — return clean response
        client = _find_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
        return {"client_id": client_id, "drift_detected": False, "message": result["error"]}
    if "error" in result and not result.get("client_id"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{client_id}/opportunities")
async def get_opportunities(client_id: str) -> dict:
    """Tax-loss harvesting, Roth conversion, and QCD opportunities for a client."""
    from app.agents.sentinel_agent import run_financial_analysis

    client = _find_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")

    results: dict[str, Any] = {"client_id": client_id, "client_name": client.get("name")}
    for analysis_type in ("TLH", "ROTH", "QCD"):
        try:
            results[analysis_type.lower()] = json.loads(run_financial_analysis(client_id, analysis_type))
        except Exception as exc:
            results[analysis_type.lower()] = {"error": str(exc)}
    return results
