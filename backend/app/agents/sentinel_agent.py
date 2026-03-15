"""Sentinel Agent -- Proactive portfolio monitoring specialist.

Uses the trigger engine and financial calculation tools to scan client portfolios,
detect compound triggers, and flag high-priority action items for the advisor.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.models import BedrockModel

from app.tools.trigger_engine import scan_client, scan_all_clients, detect_cohort_patterns
from app.tools.rmd_calculator import calculate_rmd
from app.tools.drift_calculator import calculate_portfolio_drift
from app.tools.tlh_scanner import scan_tax_loss_harvesting
from app.tools.roth_analyzer import analyze_roth_conversion
from app.tools.qcd_calculator import calculate_qcd_opportunity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_clients() -> list[dict[str, Any]]:
    data_path = Path(__file__).parent.parent / "data" / "clients.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load clients.json: %s", exc)
        return []


def _load_holdings() -> dict[str, list[dict[str, Any]]]:
    data_path = Path(__file__).parent.parent / "data" / "holdings.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
        grouped: dict[str, list] = {}
        for h in raw:
            cid = h.get("client_id", "")
            grouped.setdefault(cid, []).append(h)
        return grouped
    except Exception as exc:
        logger.error("Failed to load holdings.json: %s", exc)
        return {}


def _load_market_events() -> list[dict[str, Any]]:
    data_path = Path(__file__).parent.parent / "data" / "market_events.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load market_events.json: %s", exc)
        return []


def _find_client(client_id: str) -> dict[str, Any] | None:
    for c in _load_clients():
        if c.get("id") == client_id or c.get("client_id") == client_id:
            return c
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def scan_client_triggers(client_id: str) -> str:
    """Scan a single client portfolio for all active triggers and compute the priority score.

    Runs all 12 individual trigger detectors:
      RMD_DUE, RMD_APPROACHING, PORTFOLIO_DRIFT, TLH_OPPORTUNITY, ROTH_WINDOW,
      QCD_OPPORTUNITY, ESTATE_REVIEW_OVERDUE, MEETING_OVERDUE, LIFE_EVENT_RECENT,
      BENEFICIARY_REVIEW, MARKET_EVENT, APPROACHING_MILESTONE.
    Also detects compound trigger patterns (e.g. RMD + QCD co-occurring).
    Priority formula: (base_urgency*0.6) + (revenue_impact*0.2) + (compound_bonus*0.2),
    then multiplied by tier multiplier (A=1.5, B=1.2, C=1.0, D=0.8), capped at 100.

    Args:
        client_id: Client identifier, e.g. "CLT001".

    Returns:
        JSON with fields: client_id, client_name, tier, trigger_count, triggers (list),
        compound_triggers (list), final_priority (0-100), action_items (list).
        Returns {"error": "..."} if client not found.
    """
    client = _find_client(client_id)
    if client is None:
        return json.dumps({"error": f"Client '{client_id}' not found in clients.json"})
    all_holdings = _load_holdings()
    client_holdings = all_holdings.get(client_id, [])
    market_events = _load_market_events()
    try:
        result = scan_client(client, client_holdings, market_events)
        return json.dumps(result.to_dict())
    except Exception as exc:
        logger.exception("scan_client failed for %s", client_id)
        return json.dumps({"error": str(exc), "client_id": client_id})


@tool
def scan_all_portfolios(max_results: int = 20, tier_filter: str = "") -> str:
    """Scan all clients in the book of business and return a prioritized action list.

    Runs the full trigger engine across all 50 clients, sorts by final priority score
    (highest first), and optionally filters by client tier. Use this for the advisor's
    daily morning briefing to identify who needs attention today.

    Args:
        max_results: Number of clients to return (1-50). Default 20.
        tier_filter: Filter by tier: "A", "B", "C", or "D". Empty string = all tiers.

    Returns:
        JSON with fields:
          - total_clients_scanned (int)
          - clients_with_triggers (int)
          - results (list): Top-N clients sorted by priority, each with client_id,
            client_name, tier, trigger_count, triggers, compound_triggers,
            final_priority, action_items
          - cohort_patterns (dict): Book-wide patterns detected
          - summary (str): Plain-English morning briefing
    """
    clients = _load_clients()
    all_holdings = _load_holdings()
    market_events = _load_market_events()
    if not clients:
        return json.dumps({"error": "No clients found in clients.json"})
    try:
        all_results = scan_all_clients(clients, all_holdings, market_events)
        if tier_filter and tier_filter.upper() in ("A", "B", "C", "D"):
            all_results = [r for r in all_results if r.tier == tier_filter.upper()]
        with_triggers = [r for r in all_results if r.triggers]
        top_n = all_results[: max(1, min(int(max_results), 50))]
        cohort_patterns = detect_cohort_patterns(all_results)
        urgent = [r for r in all_results if r.final_priority >= 70]
        monitor = [r for r in all_results if 40 <= r.final_priority < 70]
        summary = (
            f"Scanned {len(clients)} clients. "
            f"{len(with_triggers)} have active triggers. "
            f"{len(urgent)} require IMMEDIATE attention (priority 70+). "
            f"{len(monitor)} are in MONITOR range (40-70). "
        )
        if urgent:
            top_names = ", ".join(r.client_name for r in urgent[:3])
            summary += f"Top urgent: {top_names}."
        return json.dumps({
            "total_clients_scanned": len(clients),
            "clients_with_triggers": len(with_triggers),
            "results": [r.to_dict() for r in top_n],
            "cohort_patterns": cohort_patterns,
            "summary": summary,
        })
    except Exception as exc:
        logger.exception("scan_all_portfolios failed")
        return json.dumps({"error": str(exc)})


@tool
def run_financial_analysis(client_id: str, analysis_type: str) -> str:
    """Run a specific financial analysis tool for a client.

    Assembles the correct inputs from the client profile and holdings, then delegates
    to the appropriate domain tool. All calculations are deterministic and based on
    IRS rules coded in the individual tools.

    Args:
        client_id: Client identifier (e.g., "CLT001").
        analysis_type: One of:
          "RMD"   -- Required Minimum Distribution (IRS Uniform Lifetime Table III).
                     Uses Traditional IRA + 401k balances from the client's accounts.
          "DRIFT" -- Portfolio drift vs. IPS target allocation (5% absolute threshold).
                     Uses holdings.json data for the client.
          "TLH"   -- Tax-loss harvesting scan (taxable accounts only, >$1,000 loss).
                     Includes replacement security suggestions and wash-sale check.
          "ROTH"  -- Roth IRA conversion optimizer (fills current tax bracket).
                     Checks IRMAA risk and pro-rata rule (IRC 408(d)(2)).
          "QCD"   -- Qualified Charitable Distribution (age 70.5+, $111,000 limit 2026).
                     Shows how QCD satisfies RMD and compares to cash donation benefit.

    Returns:
        JSON string from the relevant financial tool. Always includes an "explanation"
        field with a plain-English summary for the advisor.
    """
    client = _find_client(client_id)
    if client is None:
        return json.dumps({"error": f"Client '{client_id}' not found"})
    all_holdings = _load_holdings()
    holdings = all_holdings.get(client_id, [])
    atype = analysis_type.upper().strip()
    try:
        if atype == "RMD":
            ira_balance = sum(
                float(a.get("balance", 0))
                for a in client.get("accounts", [])
                if a.get("account_type", "").lower() in (
                    "traditional ira", "401k", "ira", "rollover ira", "sep ira", "simple ira"
                )
            )
            dob = client.get("date_of_birth", "1950-01-01")
            birth_year = int(dob.split("-")[0])
            spouse_age = None
            if client.get("spouse"):
                spouse_dob = client["spouse"].get("date_of_birth", "")
                if spouse_dob:
                    from datetime import date
                    today = date.today()
                    sy = int(spouse_dob.split("-")[0])
                    spouse_age = today.year - sy
            payload: dict[str, Any] = {
                "client_id": client_id,
                "birth_year": birth_year,
                "age": client.get("age", 65),
                "traditional_ira_balance": ira_balance,
                "rmd_taken_ytd": 0.0,
            }
            if spouse_age is not None:
                payload["spouse_age"] = spouse_age
            return calculate_rmd(json.dumps(payload))

        elif atype == "DRIFT":
            if not holdings:
                return json.dumps({"error": f"No holdings for {client_id}", "client_id": client_id})
            target = client.get("target_allocation") or {
                "US_EQUITY": 60, "INTL_EQUITY": 20, "US_BOND": 15, "INTL_BOND": 5,
            }
            return calculate_portfolio_drift(json.dumps(holdings), json.dumps(target))

        elif atype == "TLH":
            bracket_str = str(client.get("tax_bracket", "24%")).replace("%", "")
            try:
                bracket = float(bracket_str)
            except ValueError:
                bracket = 24.0
            return scan_tax_loss_harvesting(json.dumps({
                "holdings": holdings, "tax_bracket_pct": bracket, "client_id": client_id,
            }))

        elif atype == "ROTH":
            dob = client.get("date_of_birth", "1960-01-01")
            birth_year = int(dob.split("-")[0])
            age = client.get("age", 65)
            ira_balance = sum(
                float(a.get("balance", 0))
                for a in client.get("accounts", [])
                if a.get("account_type", "").lower() in (
                    "traditional ira", "401k", "ira", "rollover ira", "sep ira", "simple ira"
                )
            )
            from app.tools.rmd_calculator import _rmd_start_age
            rmd_start = _rmd_start_age(birth_year)
            return analyze_roth_conversion(json.dumps({
                "client_id": client_id,
                "age": age,
                "filing_status": client.get("marital_status", "single"),
                "current_taxable_income": float(client.get("annual_income", 0.0)),
                "traditional_ira_balance": ira_balance,
                "nondeductible_ira_basis": 0.0,
                "rmd_age": rmd_start,
                "rmd_eligible": age >= rmd_start,
                "assumed_growth_rate": 0.06,
            }))

        elif atype == "QCD":
            dob = client.get("date_of_birth", "1950-01-01")
            parts = dob.split("-")
            birth_year, birth_month, birth_day = (
                int(parts[0]), int(parts[1]) if len(parts) > 1 else 1,
                int(parts[2]) if len(parts) > 2 else 1,
            )
            ira_balance = sum(
                float(a.get("balance", 0))
                for a in client.get("accounts", [])
                if a.get("account_type", "").lower() in ("traditional ira", "ira", "rollover ira")
            )
            from app.tools.rmd_calculator import UNIFORM_LIFETIME_TABLE, _rmd_start_age
            age = client.get("age", 65)
            rmd_amount = 0.0
            if age >= _rmd_start_age(birth_year):
                period = UNIFORM_LIFETIME_TABLE.get(min(age, 120), 26.5)
                rmd_amount = round(ira_balance / period, 2)
            return calculate_qcd_opportunity(json.dumps({
                "client_id": client_id,
                "birth_year": birth_year,
                "birth_month": birth_month,
                "birth_day": birth_day,
                "age": age,
                "traditional_ira_balance": ira_balance,
                "rmd_amount": rmd_amount,
                "qcd_taken_ytd": 0.0,
                "charitable_intent": min(rmd_amount, 25_000.0),
                "filing_status": client.get("marital_status", "married"),
                "itemized_deductions": 0.0,
                "agi_before_qcd": float(client.get("annual_income", 0.0)),
            }))

        else:
            return json.dumps({
                "error": f"Unknown analysis_type '{analysis_type}'. Choose: RMD, DRIFT, TLH, ROTH, QCD"
            })
    except Exception as exc:
        logger.exception("run_financial_analysis(%s, %s) failed", client_id, analysis_type)
        return json.dumps({"error": str(exc), "client_id": client_id, "analysis_type": analysis_type})


@tool
def get_client_profile(client_id: str) -> str:
    """Retrieve the full profile and account summary for a specific client.

    Returns demographic info, account balances, current vs target allocation,
    portfolio drift, recent life events, and meeting history. Use this to understand
    the client's full picture before running deeper analyses or generating recommendations.

    Args:
        client_id: Client identifier (e.g., "CLT001").

    Returns:
        JSON with fields: id, name, age, date_of_birth, marital_status, spouse, tier, aum,
        annual_income, tax_bracket, occupation, risk_tolerance, accounts (list with account_id,
        account_type, balance, custodian), target_allocation, current_allocation, portfolio_drift,
        has_portfolio_drift, life_events, beneficiary_last_reviewed, estate_documents,
        last_meeting_date, next_meeting_target, email, phone.
    """
    client = _find_client(client_id)
    if client is None:
        return json.dumps({"error": f"Client '{client_id}' not found"})
    from datetime import date, timedelta
    tier = client.get("tier", "C")
    freq_days = {"A": 91, "B": 122, "C": 183, "D": 365}
    last_meeting = client.get("last_meeting_date") or client.get("last_review_date") or ""
    next_target = ""
    if last_meeting:
        try:
            lm = date.fromisoformat(last_meeting)
            next_target = (lm + timedelta(days=freq_days.get(tier, 183))).isoformat()
        except ValueError:
            pass
    return json.dumps({
        "id": client.get("id"),
        "name": client.get("name"),
        "age": client.get("age"),
        "date_of_birth": client.get("date_of_birth"),
        "marital_status": client.get("marital_status"),
        "spouse": client.get("spouse"),
        "tier": tier,
        "aum": client.get("aum"),
        "annual_income": client.get("annual_income"),
        "tax_bracket": client.get("tax_bracket"),
        "occupation": client.get("occupation"),
        "risk_tolerance": client.get("risk_tolerance"),
        "accounts": [
            {
                "account_id": a.get("account_id"),
                "account_type": a.get("account_type"),
                "balance": a.get("balance"),
                "custodian": a.get("custodian"),
            }
            for a in client.get("accounts", [])
        ],
        "target_allocation": client.get("target_allocation", {}),
        "current_allocation": client.get("current_allocation", {}),
        "portfolio_drift": client.get("portfolio_drift", {}),
        "has_portfolio_drift": client.get("has_portfolio_drift", False),
        "life_events": client.get("life_events", []),
        "beneficiary_last_reviewed": client.get("beneficiary_last_reviewed"),
        "estate_documents": client.get("estate_documents", []),
        "last_meeting_date": last_meeting,
        "next_meeting_target": next_target,
        "email": client.get("email"),
        "phone": client.get("phone"),
    })


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_SENTINEL_SYSTEM_PROMPT = """You are a vigilant portfolio monitoring specialist for a financial advisory firm.

Your role is to proactively scan client portfolios for triggers, risks, and time-sensitive
opportunities, then surface the highest-priority items to the advisor each morning.

Tools available:
- scan_client_triggers: Scan one client for all 12 trigger types + compound patterns
- scan_all_portfolios: Scan all 50 clients and return a prioritized action list
- run_financial_analysis: Run a specific calculation (RMD, DRIFT, TLH, ROTH, or QCD)
- get_client_profile: Retrieve full client profile and account summary

Workflow:
1. When asked to monitor the full book, use scan_all_portfolios first to triage.
2. For high-priority clients (score >= 70), use scan_client_triggers for detail.
3. For specific financial questions, use run_financial_analysis with the right type.
4. Always lead with the highest-priority items and financial dollar impact.

Output format:
- Group clients by urgency: URGENT (70+), MONITOR (40-70), WATCH (< 40)
- For each trigger: what it is, why it matters, what action is needed
- Include specific dollar amounts wherever possible
- Flag regulatory deadlines (RMD Dec 31, QCD requirements, wash sale windows)

Domain rules:
- RMD ages: 73 (born 1951-1959), 75 (born 1960+). Dec 31 deadline (April 1 for first-ever RMD).
- Drift threshold: 5% absolute. Rebalance in tax-advantaged accounts first.
- TLH: Taxable accounts only. 61-day wash sale window. Identify replacement security.
- QCD: Age 70.5+. $111,000 limit (2026). No donor-advised funds.
- Roth: Pro-rata rule applies when client has nondeductible IRA basis.
"""


def create_sentinel_agent() -> Agent:
    """Create and return the Sentinel Agent (Nova 2 Lite + 4 monitoring tools)."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0.0,
        max_tokens=4096,
    )
    return Agent(
        model=model,
        system_prompt=_SENTINEL_SYSTEM_PROMPT,
        tools=[scan_client_triggers, scan_all_portfolios, run_financial_analysis, get_client_profile],
    )


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path

    logging.basicConfig(level=logging.INFO)
    print("=== Sentinel Agent Test ===\n")

    print("[1] scan_client_triggers('CLT001')")
    result = json.loads(scan_client_triggers("CLT001"))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Client: {result['client_name']} | Tier: {result['tier']} | Priority: {result['final_priority']}")
        for t in result.get("triggers", []):
            print(f"      - {t['type']}: {t['description']}")
    print()

    print("[2] scan_all_portfolios(max_results=5)")
    result = json.loads(scan_all_portfolios(5))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    {result['summary']}")
        for r in result.get("results", []):
            print(f"      [{r['final_priority']:5.1f}] {r['client_id']} {r['client_name']} Tier-{r['tier']} -- {r['trigger_count']} trigger(s)")
    print()

    print("[3] run_financial_analysis('CLT001', 'RMD')")
    result = json.loads(run_financial_analysis("CLT001", "RMD"))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Eligible: {result.get('eligible')} | RMD: ${result.get('rmd_required', 0):,.2f} | Deadline: {result.get('deadline')}")
    print()

    if "--agent" in sys.argv:
        print("[4] Sentinel Agent briefing...")
        try:
            agent = create_sentinel_agent()
            response = agent("Scan the full book and give me the top 3 clients needing attention today.")
            print(response)
        except Exception as e:
            print(f"    Agent error (expected without AWS creds): {e}")
