"""Scout Agent - browser automation via Nova Act SDK.

Three browser-automation tools against public/local financial sites:
  1. fetch_treasury_yields()              - treasury.gov daily yield rates
  2. search_sec_filings(company_name)     - SEC EDGAR company filing search
  3. fetch_portfolio_from_portal(client_id) - mock custodian portal at localhost:8080

Design:
  - Each @tool wraps a _live_*() helper that uses NovaAct in headless mode.
  - If Nova Act is unavailable (missing key, network error, timeout) the tool
    transparently returns pre-canned mock data.
  - Passwords are NEVER passed through act() prompts - only typed into form fields.

Nova Act API key: set NOVA_ACT_API_KEY in .env.
Mock portal:      python backend/mock_portal/serve.py
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime

from strands import Agent, tool
from strands.models import BedrockModel

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nova Act availability
# ---------------------------------------------------------------------------

try:
    from nova_act import ActError, ActTimeoutError, NovaAct  # type: ignore[import]
    _NOVA_ACT_AVAILABLE = True
    logger.info("Nova Act SDK loaded OK")
except ImportError:
    _NOVA_ACT_AVAILABLE = False
    logger.warning("nova-act not installed - all tools will use mock fallback")

_NOVA_ACT_KEY: str = (
    os.getenv("NOVA_ACT_API_KEY", "")
    or getattr(settings, "NOVA_ACT_API_KEY", "")
)

# ---------------------------------------------------------------------------
# Mock / fallback data
# ---------------------------------------------------------------------------

_TODAY = date.today().isoformat()

_MOCK_TREASURY_YIELDS = {
    "source": "mock_fallback",
    "date":   _TODAY,
    "yields": {
        "3_month": 5.27,
        "6_month": 5.21,
        "1_year":  5.01,
        "2_year":  4.73,
        "5_year":  4.47,
        "10_year": 4.58,
        "20_year": 4.83,
        "30_year": 4.72,
    },
    "note": (
        "Mock data - Nova Act unavailable. "
        "Real rates: https://home.treasury.gov/resource-center/"
        "data-chart-center/interest-rates/"
    ),
}

_MOCK_SEC_FILINGS: dict[str, list[dict]] = {
    "_default": [
        {"form_type": "10-K",   "filed": "2025-02-14", "description": "Annual Report - FY 2024"},
        {"form_type": "10-Q",   "filed": "2024-11-08", "description": "Quarterly Report - Q3 2024"},
        {"form_type": "8-K",    "filed": "2024-10-23", "description": "Current Report - Q3 2024 Earnings"},
        {"form_type": "DEF14A", "filed": "2024-04-10", "description": "Definitive Proxy Statement 2024"},
        {"form_type": "10-Q",   "filed": "2024-08-09", "description": "Quarterly Report - Q2 2024"},
    ]
}

_MOCK_PORTAL_CLIENTS: dict[str, dict] = {
    "CLT001": {
        "client_id":     "CLT001",
        "client_name":   "Mark Johnson",
        "tier":          "A",
        "total_aum":     1422526.12,
        "account_count": 4,
        "alert_count":   3,
        "alerts": [
            {"severity": "red",    "text": "RMD DUE: 2026 RMD of ~$28,148 not yet distributed"},
            {"severity": "yellow", "text": "QCD AVAILABLE: Up to $111,000 charitable transfer capacity"},
            {"severity": "yellow", "text": "BENEFICIARY REVIEW: Joint Brokerage last reviewed Feb 2023"},
        ],
        "accounts": [
            {"id": "CLT001-TRADIT-1", "type": "Traditional IRA", "institution": "Morgan Stanley", "balance": 644583.11},
            {"id": "CLT001-TRUST_-2", "type": "Trust Account",   "institution": "Morgan Stanley", "balance": 358997.70},
            {"id": "CLT001-JOINT_-3", "type": "Joint Brokerage", "institution": "Raymond James",  "balance": 236043.01},
            {"id": "CLT001-ROTH_I-4", "type": "Roth IRA",        "institution": "Vanguard",       "balance": 182902.30},
        ],
        "holdings": [
            {"ticker": "VTI",  "name": "Vanguard Total Stock Market ETF", "asset_class": "US_EQUITY",   "shares": 553.34,  "price": 285.40, "value": 157922.86, "gl": 58727.76},
            {"ticker": "VXUS", "name": "Vanguard Total Intl Stock ETF",   "asset_class": "INTL_EQUITY", "shares": 930.73,  "price": 65.10,  "value": 60590.81,  "gl": 12915.24},
            {"ticker": "BND",  "name": "Vanguard Total Bond Market ETF",  "asset_class": "US_BOND",     "shares": 2325.35, "price": 73.80,  "value": 171611.00, "gl": 46871.37},
        ],
        "source": "mock_fallback",
    },
    "CLT002": {
        "client_id":     "CLT002",
        "client_name":   "Julia Nelson",
        "tier":          "A",
        "total_aum":     1878460.70,
        "account_count": 3,
        "alert_count":   3,
        "alerts": [
            {"severity": "red",    "text": "PORTFOLIO DRIFT: US Equity +7.2% over target"},
            {"severity": "red",    "text": "RMD DUE: 2026 RMD not yet taken"},
            {"severity": "yellow", "text": "MEETING OVERDUE: 110 days since last meeting"},
        ],
        "accounts": [
            {"id": "CLT002-TRADIT-1", "type": "Traditional IRA", "institution": "Fidelity",       "balance": 892340.00},
            {"id": "CLT002-ROTH_I-2", "type": "Roth IRA",        "institution": "Fidelity",       "balance": 341200.50},
            {"id": "CLT002-JOINT_-3", "type": "Joint Brokerage", "institution": "Charles Schwab", "balance": 644920.20},
        ],
        "holdings": [
            {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "asset_class": "US_EQUITY", "shares": 1240.50, "price": 285.40, "value": 354022.70, "gl": 112400.00},
            {"ticker": "AGG", "name": "iShares Core US Aggregate Bond",  "asset_class": "US_BOND",   "shares": 1850.00, "price": 97.40,  "value": 180190.00, "gl": 22100.00},
        ],
        "source": "mock_fallback",
    },
}


# ---------------------------------------------------------------------------
# Live Nova Act helpers
# ---------------------------------------------------------------------------

def _session(starting_page: str) -> "NovaAct":
    """Open a headless Nova Act browser session."""
    return NovaAct(
        starting_page=starting_page,
        nova_act_api_key=_NOVA_ACT_KEY,
        headless=True,
    )


def _live_fetch_treasury_yields() -> dict:
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/TextView?type=daily_treasury_yield_curve"
        "&field_tdr_date_value_month=202503"
    )
    schema = {
        "type": "object",
        "properties": {
            "date":    {"type": "string"},
            "3_month": {"type": "number"},
            "6_month": {"type": "number"},
            "1_year":  {"type": "number"},
            "2_year":  {"type": "number"},
            "5_year":  {"type": "number"},
            "10_year": {"type": "number"},
            "20_year": {"type": "number"},
            "30_year": {"type": "number"},
        },
        "required": ["date", "10_year", "30_year"],
    }
    with _session(url) as nova:
        result = nova.act(
            "Find the most recent row in the Treasury yield curve table. "
            "Extract the date and all yield values (3-month through 30-year) "
            "as decimal percentages.",
            schema=schema,
            timeout=60,
        )
        yields = (
            result.parsed_response
            if hasattr(result, "parsed_response") and result.parsed_response
            else {"raw": getattr(result, "response", ""), "date": _TODAY}
        )
    return {
        "source":       "treasury.gov",
        "url":          url,
        "retrieved_at": datetime.utcnow().isoformat() + "Z",
        "yields":       yields,
    }


def _live_search_sec_filings(company_name: str) -> dict:
    encoded = company_name.replace(" ", "+")
    url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar"
        f"?company={encoded}&CIK=&type=10-K&dateb=&owner=include"
        f"&count=10&search_text=&action=getcompany"
    )
    schema = {
        "type": "object",
        "properties": {
            "company_found": {"type": "string"},
            "filings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "form_type":   {"type": "string"},
                        "filed":       {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        },
        "required": ["filings"],
    }
    with _session(url) as nova:
        result = nova.act(
            f"Search for {company_name!r} SEC filings. "
            "Extract the company name and up to 5 recent filings with "
            "form type, filing date, and description.",
            schema=schema,
            timeout=90,
        )
        data = (
            result.parsed_response
            if hasattr(result, "parsed_response") and result.parsed_response
            else {"company_found": company_name, "filings": []}
        )
    return {
        "source":        "SEC EDGAR",
        "query":         company_name,
        "retrieved_at":  datetime.utcnow().isoformat() + "Z",
        "company_found": data.get("company_found", company_name),
        "filings":       data.get("filings", [])[:5],
    }


def _live_fetch_portfolio_from_portal(client_id: str) -> dict:
    """Log in to mock portal and extract client portfolio data."""
    login_url = f"http://localhost:8080/index.html?client={client_id}"
    schema = {
        "type": "object",
        "properties": {
            "client_id":     {"type": "string"},
            "client_name":   {"type": "string"},
            "tier":          {"type": "string"},
            "total_aum":     {"type": "number"},
            "account_count": {"type": "number"},
            "alert_count":   {"type": "number"},
            "alerts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string"},
                        "text":     {"type": "string"},
                    },
                },
            },
        },
        "required": ["client_id", "client_name", "total_aum"],
    }
    with _session(login_url) as nova:
        # Credentials typed into form fields - password NOT in prompt text
        nova.act("Type 'demo' into the Advisor ID input field", timeout=30)
        nova.act("Type 'demo123' into the Password input field", timeout=30)
        nova.act("Click the Sign In button", timeout=30)

        result = nova.act(
            f"Extract the portfolio summary for client {client_id}: "
            "client name, tier, total AUM, account count, alert count, "
            "and all alert texts with severity.",
            schema=schema,
            timeout=60,
        )
        if hasattr(result, "parsed_response") and result.parsed_response:
            data = result.parsed_response
        else:
            dr = nova.act(
                "Read the hidden element with id portal-data and return its JSON content.",
                timeout=30,
            )
            raw = getattr(dr, "response", "") or "{}"
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}

    data["source"] = "mock_portal_live"
    data["retrieved_at"] = datetime.utcnow().isoformat() + "Z"
    return data


# ---------------------------------------------------------------------------
# Strands @tool wrappers
# ---------------------------------------------------------------------------

@tool
def fetch_treasury_yields() -> str:
    """Fetch current US Treasury yield curve rates from treasury.gov via Nova Act.

    Navigates to the Treasury daily yield curve data page and extracts the most
    recent rates for all maturities (3-month through 30-year).

    These rates help advisors:
      - Analyse bond portfolio duration vs 5% drift thresholds
      - Time Roth conversions around rate-driven equity valuations
      - Build client proposals on fixed-income return expectations
      - Make bond laddering and relative-value recommendations

    Returns:
        JSON string with keys:
          source       - "treasury.gov" or "mock_fallback"
          date         - YYYY-MM-DD of the rate data
          retrieved_at - ISO 8601 UTC timestamp
          yields       - dict: maturity -> rate in percent (4.58 = 4.58%)
          note         - present only when fallback is returned
    """
    if not _NOVA_ACT_AVAILABLE or not _NOVA_ACT_KEY:
        logger.info("fetch_treasury_yields: mock fallback (Nova Act unavailable)")
        return json.dumps(_MOCK_TREASURY_YIELDS, indent=2)
    try:
        return json.dumps(_live_fetch_treasury_yields(), indent=2)
    except Exception as exc:
        logger.warning("fetch_treasury_yields live failed (%s) - fallback", exc)
        return json.dumps({**_MOCK_TREASURY_YIELDS, "fallback_reason": str(exc)}, indent=2)


@tool
def search_sec_filings(company_name: str) -> str:
    """Search SEC EDGAR for a company's recent regulatory filings via Nova Act.

    Navigates to SEC EDGAR company search and extracts recent 10-K annual
    reports, 10-Q quarterly reports, 8-K current reports, and proxy statements.

    Useful for advisors to:
      - Conduct due diligence on concentrated stock positions
      - Monitor material events (8-K) for clients holding employer stock
      - Verify financial health before large equity purchases
      - Validate business interest valuations for estate planning

    Args:
        company_name: Company to search (e.g. "Apple", "Vanguard", "BlackRock").
                      EDGAR supports partial name matching.

    Returns:
        JSON string with keys:
          source        - "SEC EDGAR" or "mock_fallback"
          query         - search term used
          company_found - exact name returned by EDGAR
          retrieved_at  - ISO 8601 UTC timestamp
          filings       - list of up to 5 dicts:
                          {form_type, filed (YYYY-MM-DD), description}
    """
    if not _NOVA_ACT_AVAILABLE or not _NOVA_ACT_KEY:
        logger.info("search_sec_filings: mock fallback")
        filings = _MOCK_SEC_FILINGS.get(company_name, _MOCK_SEC_FILINGS["_default"])
        return json.dumps({
            "source": "mock_fallback", "query": company_name,
            "company_found": company_name, "retrieved_at": _TODAY,
            "filings": filings, "note": "Mock data - Nova Act unavailable.",
        }, indent=2)
    try:
        return json.dumps(_live_search_sec_filings(company_name), indent=2)
    except Exception as exc:
        logger.warning("search_sec_filings live failed (%s) - fallback", exc)
        filings = _MOCK_SEC_FILINGS.get(company_name, _MOCK_SEC_FILINGS["_default"])
        return json.dumps({
            "source": "mock_fallback", "query": company_name,
            "company_found": company_name, "retrieved_at": _TODAY,
            "filings": filings, "fallback_reason": str(exc),
        }, indent=2)


@tool
def fetch_portfolio_from_portal(client_id: str) -> str:
    """Fetch a client portfolio from the custodian portal via Nova Act automation.

    Demonstrates how WealthRadar automates custodian data retrieval - a task
    advisors currently do manually across multiple portals. The tool navigates
    the login flow, finds the client account, and extracts balances, holdings,
    and active alerts.

    For the demo this targets the local mock portal (localhost:8080).
    Prerequisites: python backend/mock_portal/serve.py

    Args:
        client_id: WealthRadar client ID, e.g. "CLT001" or "CLT002".

    Returns:
        JSON string with keys:
          client_id, client_name, tier
          total_aum           - float
          account_count, alert_count  - int
          alerts              - list of {severity: red|yellow|green, text}
          accounts            - list of {id, type, institution, balance}
          holdings            - list of {ticker, name, asset_class, shares, price, value, gl}
          source              - "mock_portal_live" or "mock_fallback"
          retrieved_at        - ISO 8601 UTC timestamp
    """
    fallback = _MOCK_PORTAL_CLIENTS.get(client_id, {
        "client_id": client_id, "client_name": f"Client {client_id}",
        "tier": "C", "total_aum": 0.0, "account_count": 0, "alert_count": 0,
        "alerts": [], "accounts": [], "holdings": [], "source": "mock_fallback",
        "note": f"No mock data for {client_id}",
    })

    if not _NOVA_ACT_AVAILABLE or not _NOVA_ACT_KEY:
        logger.info("fetch_portfolio_from_portal: mock fallback")
        return json.dumps(fallback, indent=2)

    import urllib.error, urllib.request
    try:
        urllib.request.urlopen("http://localhost:8080/index.html", timeout=2)
    except (urllib.error.URLError, OSError):
        logger.warning("Portal not reachable. Run: python backend/mock_portal/serve.py")
        return json.dumps({**fallback, "note": "Portal not running."}, indent=2)

    try:
        return json.dumps(_live_fetch_portfolio_from_portal(client_id), indent=2)
    except Exception as exc:
        logger.warning("fetch_portfolio_from_portal live failed (%s) - fallback", exc)
        return json.dumps({**fallback, "fallback_reason": str(exc)}, indent=2)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the Scout Agent for WealthRadar, a browser automation specialist
that gathers real-time financial intelligence from public and custodian web sources.

Your role:
  1. Retrieve current market data (Treasury yields) from official government sites.
  2. Search SEC filings for companies held in client portfolios.
  3. Extract portfolio data from custodian portals on behalf of advisors.

Always return structured, actionable data with source and timestamp.
Clearly label mock/fallback data. Never embed credentials in act() prompts."""


def create_scout_agent() -> Agent:
    """Create and return the Scout Strands Agent with browser automation tools."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=settings.AWS_DEFAULT_REGION,
    )
    return Agent(
        model=model,
        tools=[fetch_treasury_yields, search_sec_filings, fetch_portfolio_from_portal],
        system_prompt=_SYSTEM_PROMPT,
    )


# ---------------------------------------------------------------------------
# Smoke test  (python -m app.agents.scout_agent  from backend/)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s -- %(message)s")
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    print("\n=== Scout Agent -- Smoke Test ===")
    print(f"Nova Act available : {_NOVA_ACT_AVAILABLE}")
    print(f"API key configured : {'yes' if _NOVA_ACT_KEY else 'NO -- set NOVA_ACT_API_KEY'}")

    def _parse(raw) -> dict:
        if hasattr(raw, "content"):
            return json.loads(raw.content[0].text)
        return json.loads(str(raw))

    print("\n--- Tool 1: fetch_treasury_yields() ---")
    yields = _parse(fetch_treasury_yields())
    print(f"  Source : {yields.get('source')}")
    for mat, rate in (yields.get("yields") or {}).items():
        if isinstance(rate, (int, float)):
            print(f"  {mat:>8} : {rate:.2f}%")

    print("\n--- Tool 2: search_sec_filings(\'Vanguard\') ---")
    fd = _parse(search_sec_filings("Vanguard"))
    print(f"  Source  : {fd.get('source')}")
    print(f"  Company : {fd.get('company_found')}")
    for i, f in enumerate(fd.get("filings", [])[:5], 1):
        print(f"  {i}. [{f.get('form_type','?')}] {f.get('filed','?')} -- {f.get('description','')[:60]}")

    print("\n--- Tool 3: fetch_portfolio_from_portal(\'CLT001\') ---")
    pd_ = _parse(fetch_portfolio_from_portal("CLT001"))
    print(f"  Source    : {pd_.get('source')}")
    print(f"  Client    : {pd_.get('client_name')} ({pd_.get('client_id')})")
    print(f"  Total AUM : ${pd_.get('total_aum', 0):,.2f}")
    print(f"  Alerts    : {pd_.get('alert_count')}")
    for a in pd_.get("alerts", []):
        print(f"    [{a.get('severity','?').upper()}] {a.get('text','')}")
