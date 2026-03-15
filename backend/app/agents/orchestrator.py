"""WealthRadar Orchestrator — AI Chief of Staff supervisor agent.

Architecture (Strands agents-as-tools pattern):
  - Each specialist agent is wrapped in a @tool function
  - The orchestrator (Nova 2 Lite) decides which agents to invoke and in what order
  - High-level Python workflow functions bypass the LLM for batch operations

Specialist agents:
  1. sentinel_scan        → SentinelAgent (portfolio monitoring + financial calculations)
  2. analyze_documents    → DocAgent      (PDF/document intelligence)
  3. gather_external_data → ScoutAgent    (browser automation: treasury.gov, SEC EDGAR, portal)
  4. compose_deliverable  → ComposerAgent (meeting prep, emails, campaigns)

Workflow functions (pure Python — no per-client LLM orchestration overhead):
  - analyze_single_client(client_id)  — full analysis pipeline for one client
  - daily_radar_scan(top_n)           — scan book, analyse top-N clients
  - prepare_meeting(client_id)        — complete meeting prep pipeline
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy agent singletons — created once, reused across workflow calls
# ---------------------------------------------------------------------------

_sentinel_agent: Agent | None = None
_doc_agent: Agent | None = None
_scout_agent: Agent | None = None
_composer_agent: Agent | None = None
_orchestrator_agent: Agent | None = None


def _get_sentinel() -> Agent:
    global _sentinel_agent
    if _sentinel_agent is None:
        from app.agents.sentinel_agent import create_sentinel_agent
        _sentinel_agent = create_sentinel_agent()
    return _sentinel_agent


def _get_doc_agent() -> Agent:
    global _doc_agent
    if _doc_agent is None:
        from app.agents.doc_agent import create_doc_agent
        _doc_agent = create_doc_agent()
    return _doc_agent


def _get_scout() -> Agent:
    global _scout_agent
    if _scout_agent is None:
        from app.agents.scout_agent import create_scout_agent
        _scout_agent = create_scout_agent()
    return _scout_agent


def _get_composer() -> Agent:
    global _composer_agent
    if _composer_agent is None:
        from app.agents.composer_agent import create_composer_agent
        _composer_agent = create_composer_agent()
    return _composer_agent


# ---------------------------------------------------------------------------
# Agents-as-tools: wrap each specialist so the orchestrator LLM can call them
# ---------------------------------------------------------------------------

@tool
def sentinel_scan(query: str) -> str:
    """Delegate a portfolio monitoring or financial analysis task to the Sentinel Agent.

    The Sentinel Agent can:
    - Scan any client for all 12 trigger types (RMD, TLH, drift, Roth, QCD, etc.)
    - Scan the entire book of business and return a prioritised action list
    - Run specific financial calculations (RMD amount, drift %, TLH savings, Roth optimal
      conversion, QCD opportunity) for any client
    - Return a full client profile including accounts, allocation, and meeting history

    Use this tool when you need to understand what financial actions are needed for a
    client or across the book of business. Always run this first before composing
    deliverables so you have specific dollar amounts and trigger details to work with.

    Args:
        query: Natural-language instruction for the Sentinel Agent. Examples:
            "Scan CLT001 for all active triggers and tell me the priority score"
            "Run an RMD analysis for CLT005 and show the required amount and deadline"
            "Show me the top 5 clients by urgency across the full book"
            "Get the full profile for client CLT012"

    Returns:
        Sentinel Agent response as a string — includes trigger summaries, financial
        calculations, and plain-English explanations with specific dollar amounts.
    """
    try:
        agent = _get_sentinel()
        result = agent(query)
        return str(result).encode("utf-8", errors="replace").decode("utf-8")
    except Exception as exc:
        logger.exception("sentinel_scan failed")
        return json.dumps({"error": f"Sentinel agent error: {exc}"})


@tool
def analyze_documents(query: str) -> str:
    """Delegate a document analysis task to the Document Intelligence Agent.

    The Document Intelligence Agent can:
    - Analyse trust documents: extract trustees, beneficiaries, provisions, successor trustees
    - Analyse account statements: extract holdings, performance, fees, allocation drift alerts
    - Run a full estate document review for a client: identify gaps, missing docs, stale docs
    - Search a client's documents by semantic query using FAISS embeddings

    Use this tool when you need supporting evidence from financial documents — e.g., to
    verify trust provisions before recommending a QCD, or to check whether estate documents
    are current before an estate review meeting.

    Args:
        query: Natural-language instruction for the Document Intelligence Agent. Examples:
            "Analyse the trust document for CLT001 and identify the successor trustee"
            "Review all estate documents for client CLT040 and identify gaps"
            "Search CLT001's documents for any references to charitable giving"
            "Analyse the account statement for CLT002 and flag any drift alerts"

    Returns:
        Document Intelligence Agent response as a string — includes extracted data from
        PDFs, gap analysis, and action flags for the advisor.
    """
    try:
        agent = _get_doc_agent()
        result = agent(query)
        return str(result).encode("utf-8", errors="replace").decode("utf-8")
    except Exception as exc:
        logger.exception("analyze_documents failed")
        return json.dumps({"error": f"Document agent error: {exc}"})


@tool
def gather_external_data(query: str) -> str:
    """Delegate a data collection task to the Scout Agent (browser automation).

    The Scout Agent uses Nova Act browser automation to fetch live data from:
    - treasury.gov: current yield curve rates (10Y, 30Y, Fed Funds, SOFR)
    - SEC EDGAR: recent 10-K, 8-K, proxy filings for any public company
    - Mock custodian portal (localhost:8080): client portfolio holdings and balances
    Falls back to realistic mock data if live sites are unreachable.

    Use this tool when you need current market data (e.g., treasury yields to assess
    bond allocation), company filings (e.g., check a concentrated stock position), or
    fresh portfolio data from the custodian portal.

    Args:
        query: Natural-language instruction for the Scout Agent. Examples:
            "Fetch the current treasury yield curve"
            "Search SEC EDGAR for recent 10-K filings from Apple Inc"
            "Get portfolio holdings from the custodian portal for client CLT001"

    Returns:
        Scout Agent response as a string — includes fetched data with source, date,
        and any fallback indicators if mock data was used.
    """
    try:
        agent = _get_scout()
        result = agent(query)
        return str(result).encode("utf-8", errors="replace").decode("utf-8")
    except Exception as exc:
        logger.exception("gather_external_data failed")
        return json.dumps({"error": f"Scout agent error: {exc}"})


@tool
def compose_deliverable(query: str) -> str:
    """Delegate a content generation task to the Composer Agent.

    The Composer Agent uses Nova 2 Lite to generate advisor-ready content:
    - Meeting preparation packages: executive summary, agenda, talking points, questions,
      recommendations, pre-meeting checklist
    - Personalized client outreach emails with compliance disclaimers
    - Batch cohort campaign templates with personalisation tokens

    Always run sentinel_scan first to get trigger data with specific dollar amounts before
    calling compose_deliverable — the Composer needs concrete trigger details to produce
    actionable (non-generic) content.

    Args:
        query: Natural-language instruction for the Composer Agent. Must include:
            - client_id or cohort description
            - The triggers JSON (from sentinel_scan) for personalisation
            - Type of deliverable: meeting prep / email / campaign
          Examples:
            "Generate a meeting prep package for CLT001 using these triggers: {json}"
            "Write a RMD_DUE outreach email for CLT005 with context: RMD of $32,000 due Dec 31"
            "Create an RMD cohort campaign for these 8 clients: {json}"

    Returns:
        Composer Agent response as a string — includes the complete deliverable
        (meeting package JSON, email subject/body, or campaign template) ready for review.
    """
    try:
        agent = _get_composer()
        result = agent(query)
        return str(result).encode("utf-8", errors="replace").decode("utf-8")
    except Exception as exc:
        logger.exception("compose_deliverable failed")
        return json.dumps({"error": f"Composer agent error: {exc}"})


# ---------------------------------------------------------------------------
# Orchestrator agent factory
# ---------------------------------------------------------------------------

_ORCHESTRATOR_SYSTEM_PROMPT = """You are the WealthRadar Orchestrator — an AI Chief of Staff for financial advisors.

Your role is to coordinate four specialist agents to deliver complete, actionable intelligence
about a financial advisor's book of business.

Specialist agents at your disposal:
  - sentinel_scan        : Portfolio monitoring, trigger detection, financial calculations
  - analyze_documents    : PDF document intelligence (trusts, statements, estate plans)
  - gather_external_data : Live market data (treasury yields, SEC filings, custodian portal)
  - compose_deliverable  : Meeting prep packages, client emails, cohort campaigns

Decision framework:
1. For CLIENT ANALYSIS: Always run sentinel_scan first to identify triggers and priority score.
   Then run analyze_documents if the client has relevant documents. Use gathered data to
   compose a clear, actionable summary.

2. For MEETING PREP: Run all agents in sequence:
   (a) sentinel_scan → identify all active triggers with dollar amounts
   (b) analyze_documents → check estate/trust documents for currency and gaps
   (c) gather_external_data → get current yield curve if client holds bonds
   (d) compose_deliverable → generate the full meeting prep package

3. For DAILY BRIEFING: Run sentinel_scan for book-wide triage, then focus compose_deliverable
   on the top 3 urgent clients.

4. For OUTREACH: Run sentinel_scan to confirm trigger details, then compose_deliverable
   with the specific dollar amounts from sentinel output.

Output standards:
- Always include specific dollar amounts (RMD: $45,230 not "significant amount")
- Always include regulatory deadlines (RMD: Dec 31 or Apr 1 for first RMD)
- Group findings by urgency: URGENT (priority 70+), MONITOR (40-70), WATCH (<40)
- Never fabricate financial numbers — only use amounts from the agent responses
- Compliance note: flag any action that requires client consent before execution

Domain rules:
- RMD ages: 73 (born 1951-1959), 75 (born 1960+). Dec 31 deadline (Apr 1 for first RMD only).
- Portfolio drift threshold: 5% absolute. Rebalance in tax-advantaged accounts first.
- TLH: Taxable accounts only. 61-day wash sale window. Always identify replacement security.
- QCD: Age 70.5+. $111,000 limit (2026). No donor-advised funds. Must go custodian-to-charity.
- Roth: Pro-rata rule (IRC 408(d)(2)) applies when client has nondeductible IRA basis.
"""


def create_orchestrator() -> Agent:
    """Create and return the WealthRadar Orchestrator Agent.

    Returns:
        Configured Strands Agent with BedrockModel (Nova 2 Lite) and 4 specialist agent tools.
    """
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0.3,  # balanced: analytical but slightly creative for narratives
        max_tokens=8192,
    )
    return Agent(
        model=model,
        system_prompt=_ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[sentinel_scan, analyze_documents, gather_external_data, compose_deliverable],
    )


def _get_orchestrator() -> Agent:
    global _orchestrator_agent
    if _orchestrator_agent is None:
        _orchestrator_agent = create_orchestrator()
    return _orchestrator_agent


# ---------------------------------------------------------------------------
# High-level workflow functions (Python-level, not Strands @tools)
# ---------------------------------------------------------------------------

def _load_clients() -> list[dict[str, Any]]:
    """Load all client profiles."""
    from pathlib import Path
    data_path = Path(__file__).parent.parent / "data" / "clients.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load clients.json: %s", exc)
        return []


def _load_holdings() -> dict[str, list[dict[str, Any]]]:
    """Load holdings keyed by client_id."""
    from pathlib import Path
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
    """Load market events."""
    from pathlib import Path
    data_path = Path(__file__).parent.parent / "data" / "market_events.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load market_events.json: %s", exc)
        return []


def analyze_single_client(client_id: str, use_orchestrator: bool = False) -> dict[str, Any]:
    """Run a complete analysis pipeline for one client.

    Workflow:
      1. Run Sentinel scan directly (structured trigger data + financial calculations)
      2. Optionally run relevant financial analyses for each active trigger type
      3. If use_orchestrator=True, run the orchestrator LLM for a narrative summary

    Args:
        client_id: Client identifier (e.g., "CLT001").
        use_orchestrator: If True, invoke the orchestrator LLM for a narrative. This makes
            additional Bedrock API calls. Default False for batch operations.

    Returns:
        Dict with fields:
            - client_id (str)
            - client_name (str), tier (str), final_priority (float)
            - triggers (list): Active triggers with descriptions and dollar details
            - compound_triggers (list): Detected compound patterns
            - financial_analyses (dict): Keyed by analysis type (RMD, DRIFT, TLH, ROTH, QCD)
            - action_items (list): Recommended immediate actions
            - orchestrator_narrative (str | None): LLM narrative if use_orchestrator=True
            - error (str): Set only on failure
    """
    from app.agents.sentinel_agent import (
        scan_client_triggers, run_financial_analysis,
    )

    # 1. Sentinel scan — structured trigger data
    triggers_json = scan_client_triggers(client_id)
    try:
        triggers_data = json.loads(triggers_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Sentinel scan failed: {exc}", "client_id": client_id}

    if "error" in triggers_data:
        return triggers_data

    # 2. Financial analyses for each active trigger type
    financial_analyses: dict[str, Any] = {}
    trigger_types = {t["type"] for t in triggers_data.get("triggers", [])}

    _TRIGGER_TO_ANALYSIS = {
        "RMD_DUE": "RMD",
        "RMD_APPROACHING": "RMD",
        "PORTFOLIO_DRIFT": "DRIFT",
        "TLH_OPPORTUNITY": "TLH",
        "ROTH_WINDOW": "ROTH",
        "QCD_OPPORTUNITY": "QCD",
    }

    for trigger_type, analysis_type in _TRIGGER_TO_ANALYSIS.items():
        if trigger_type in trigger_types and analysis_type not in financial_analyses:
            try:
                raw = run_financial_analysis(client_id, analysis_type)
                financial_analyses[analysis_type] = json.loads(raw)
            except Exception as exc:
                logger.warning("Financial analysis %s failed for %s: %s", analysis_type, client_id, exc)
                financial_analyses[analysis_type] = {"error": str(exc)}

    # 3. Optional: orchestrator LLM narrative
    orchestrator_narrative: str | None = None
    if use_orchestrator:
        try:
            prompt = (
                f"Provide a comprehensive advisor briefing for client {client_id}. "
                f"Trigger data: {triggers_json}. "
                f"Financial analyses: {json.dumps(financial_analyses)}. "
                "Summarize: (1) the 3 most important actions with deadlines and dollar amounts, "
                "(2) any compound trigger synergies, (3) recommended next step for the advisor."
            )
            orch = _get_orchestrator()
            orchestrator_narrative = str(orch(prompt)).encode("utf-8", errors="replace").decode("utf-8")
        except Exception as exc:
            logger.warning("Orchestrator narrative failed for %s: %s", client_id, exc)
            orchestrator_narrative = f"[Orchestrator unavailable: {exc}]"

    return {
        "client_id": client_id,
        "client_name": triggers_data.get("client_name", ""),
        "tier": triggers_data.get("tier", ""),
        "final_priority": triggers_data.get("final_priority", 0.0),
        "triggers": triggers_data.get("triggers", []),
        "compound_triggers": triggers_data.get("compound_triggers", []),
        "financial_analyses": financial_analyses,
        "action_items": triggers_data.get("action_items", []),
        "orchestrator_narrative": orchestrator_narrative,
    }


def daily_radar_scan(top_n: int = 10, use_orchestrator: bool = False) -> dict[str, Any]:
    """Scan the full book of business and analyse the top-N priority clients.

    Runs trigger_engine.scan_all_clients() directly (no per-client LLM overhead),
    then calls analyze_single_client() for the top-N clients by priority score.

    Args:
        top_n: Number of top-priority clients to fully analyse. Default 10.
        use_orchestrator: If True, run the orchestrator LLM for each client narrative.
            Expensive (many Bedrock calls). Default False.

    Returns:
        Dict with fields:
            - scan_date (str): ISO date of the scan
            - total_clients_scanned (int)
            - clients_with_triggers (int)
            - urgent_count (int): Clients with priority >= 70
            - monitor_count (int): Clients with priority 40-70
            - top_clients (list): list of analyze_single_client() results for top-N
            - cohort_patterns (list): Book-wide trigger patterns
            - morning_briefing (str): Concise plain-English summary
    """
    from app.tools.trigger_engine import scan_all_clients, detect_cohort_patterns

    clients = _load_clients()
    all_holdings = _load_holdings()
    market_events = _load_market_events()

    if not clients:
        return {"error": "No clients found in clients.json"}

    logger.info("daily_radar_scan: scanning %d clients...", len(clients))
    all_results = scan_all_clients(clients, all_holdings, market_events)

    with_triggers = [r for r in all_results if r.triggers]
    urgent = [r for r in all_results if r.final_priority >= 70]
    monitor = [r for r in all_results if 40 <= r.final_priority < 70]

    # Detect cohort patterns across the full book
    cohort_patterns = detect_cohort_patterns(all_results)

    # Analyse top-N clients in detail
    top_results = all_results[:max(1, min(top_n, len(all_results)))]
    logger.info("daily_radar_scan: running detailed analysis for top %d clients...", len(top_results))

    client_analyses: list[dict[str, Any]] = []
    for result in top_results:
        analysis = analyze_single_client(result.client_id, use_orchestrator=use_orchestrator)
        client_analyses.append(analysis)

    # Build morning briefing text
    briefing_lines = [
        f"WealthRadar Daily Scan — {date.today().isoformat()}",
        f"Scanned {len(clients)} clients. {len(with_triggers)} have active triggers.",
        f"URGENT ({len(urgent)} clients, priority 70+): "
        + (", ".join(r.client_name for r in urgent[:5]) + ("..." if len(urgent) > 5 else "")
           if urgent else "None"),
        f"MONITOR ({len(monitor)} clients, priority 40-70): "
        + (", ".join(r.client_name for r in monitor[:3]) + ("..." if len(monitor) > 3 else "")
           if monitor else "None"),
    ]
    if urgent:
        top_client = urgent[0]
        briefing_lines.append(
            f"Top priority: {top_client.client_name} (Tier {top_client.tier}, "
            f"score {top_client.final_priority:.0f}) — "
            f"{len(top_client.triggers)} trigger(s): "
            + ", ".join(t.trigger_type for t in top_client.triggers[:3])
        )

    return {
        "scan_date": date.today().isoformat(),
        "total_clients_scanned": len(clients),
        "clients_with_triggers": len(with_triggers),
        "urgent_count": len(urgent),
        "monitor_count": len(monitor),
        "top_clients": client_analyses,
        "cohort_patterns": cohort_patterns,
        "morning_briefing": "\n".join(briefing_lines),
    }


def prepare_meeting(client_id: str, use_orchestrator: bool = True) -> dict[str, Any]:
    """Run the full meeting preparation pipeline for a client.

    Workflow:
      1. Sentinel scan — identify all active triggers and run relevant financial analyses
      2. Document Intelligence — review estate/trust documents for currency and gaps
      3. Scout — fetch current treasury yields (market context)
      4. Composer — generate the full meeting prep package using trigger data

    Args:
        client_id: Client identifier (e.g., "CLT001").
        use_orchestrator: If True, also run the orchestrator LLM for an overall narrative.
            Default True since this is a high-value single-client operation.

    Returns:
        Dict with fields:
            - client_id (str), client_name (str), prepared_date (str)
            - trigger_analysis (dict): Full sentinel scan result with financial analyses
            - document_review (str): Estate document analysis from doc agent
            - market_context (str): Treasury yield data from scout agent
            - meeting_package (dict): Full meeting prep from composer (agenda, talking points, etc.)
            - orchestrator_summary (str | None): LLM narrative if use_orchestrator=True
            - error (str): Set only on failure
    """
    from app.agents.sentinel_agent import scan_client_triggers
    from app.agents.composer_agent import generate_meeting_prep

    logger.info("prepare_meeting: starting pipeline for %s", client_id)

    # 1. Sentinel scan + financial analyses
    trigger_analysis = analyze_single_client(client_id, use_orchestrator=False)
    if "error" in trigger_analysis and not trigger_analysis.get("client_name"):
        return trigger_analysis

    triggers_json = json.dumps({
        "client_id": client_id,
        "client_name": trigger_analysis.get("client_name", ""),
        "tier": trigger_analysis.get("tier", ""),
        "trigger_count": len(trigger_analysis.get("triggers", [])),
        "final_priority": trigger_analysis.get("final_priority", 0),
        "triggers": trigger_analysis.get("triggers", []),
        "compound_triggers": trigger_analysis.get("compound_triggers", []),
        "action_items": trigger_analysis.get("action_items", []),
    })

    # 2. Document review (doc agent — best-effort)
    document_review = ""
    try:
        doc_agent = _get_doc_agent()
        doc_result = doc_agent(
            f"Review all estate and account documents for client {client_id}. "
            "Identify any gaps, stale documents, or missing provisions. "
            "Be concise — 3-5 bullet points."
        )
        document_review = str(doc_result).encode("utf-8", errors="replace").decode("utf-8")
        logger.info("prepare_meeting: document review complete")
    except Exception as exc:
        logger.warning("Document review failed for %s: %s", client_id, exc)
        document_review = f"Document review unavailable: {exc}"

    # 3. Market context (scout agent — best-effort)
    market_context = ""
    try:
        scout = _get_scout()
        scout_result = scout("Fetch the current treasury yield curve rates.")
        market_context = str(scout_result).encode("utf-8", errors="replace").decode("utf-8")
        logger.info("prepare_meeting: market context fetched")
    except Exception as exc:
        logger.warning("Scout data fetch failed: %s", exc)
        market_context = f"Market data unavailable: {exc}"

    # 4. Composer — meeting prep package
    meeting_package: dict[str, Any] = {}
    try:
        raw = generate_meeting_prep(client_id, triggers_json)
        meeting_package = json.loads(raw)
        logger.info("prepare_meeting: meeting package generated")
    except Exception as exc:
        logger.warning("Meeting prep generation failed for %s: %s", client_id, exc)
        meeting_package = {"error": str(exc)}

    # 5. Optional orchestrator narrative
    orchestrator_summary: str | None = None
    if use_orchestrator:
        try:
            orch = _get_orchestrator()
            prompt = (
                f"Prepare a final advisor briefing for the meeting with {trigger_analysis.get('client_name', client_id)}.\n"
                f"Trigger analysis summary: {len(trigger_analysis.get('triggers', []))} triggers, "
                f"priority {trigger_analysis.get('final_priority', 0):.0f}/100.\n"
                f"Key triggers: {', '.join(t['type'] for t in trigger_analysis.get('triggers', [])[:4])}.\n"
                f"Document review highlights: {document_review[:300]}.\n"
                "Give the advisor: (1) the single most important thing to accomplish in this meeting, "
                "(2) the opening talking point, (3) the one action that must be completed before they leave the meeting."
            )
            orchestrator_summary = str(orch(prompt)).encode("utf-8", errors="replace").decode("utf-8")
            logger.info("prepare_meeting: orchestrator summary complete")
        except Exception as exc:
            logger.warning("Orchestrator summary failed: %s", exc)
            orchestrator_summary = f"[Orchestrator unavailable: {exc}]"

    return {
        "client_id": client_id,
        "client_name": trigger_analysis.get("client_name", ""),
        "prepared_date": date.today().isoformat(),
        "trigger_analysis": trigger_analysis,
        "document_review": document_review,
        "market_context": market_context,
        "meeting_package": meeting_package,
        "orchestrator_summary": orchestrator_summary,
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Windows CP1252 terminals can't encode Unicode emitted by Strands streaming.
    # Reconfigure stdout/stderr to UTF-8 so emojis and special chars don't crash.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    use_orch = "--orchestrator" in sys.argv
    client_id = "CLT001"

    print("=" * 60)
    print("WealthRadar Orchestrator Test")
    print(f"LLM orchestration: {'ENABLED' if use_orch else 'DISABLED (pass --orchestrator to enable)'}")
    print("=" * 60)
    print()

    # ----------------------------------------------------------------
    # Test 1: analyze_single_client
    # ----------------------------------------------------------------
    print(f"[1] analyze_single_client('{client_id}', use_orchestrator={use_orch})")
    result = analyze_single_client(client_id, use_orchestrator=use_orch)

    if "error" in result and not result.get("client_name"):
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Client: {result['client_name']} | Tier: {result['tier']} | Priority: {result['final_priority']}")
        print(f"    Triggers: {len(result.get('triggers', []))}")
        for t in result.get("triggers", []):
            print(f"      - {t['type']}: {t['description'][:80]}")
        print(f"    Financial analyses run: {list(result.get('financial_analyses', {}).keys())}")
        for atype, data in result.get("financial_analyses", {}).items():
            expl = data.get("explanation", data.get("error", ""))[:100]
            print(f"      [{atype}] {expl}...")
        if result.get("orchestrator_narrative"):
            print(f"    Orchestrator narrative:")
            print(f"      {result['orchestrator_narrative'][:400]}...")
    print()

    # ----------------------------------------------------------------
    # Test 2: daily_radar_scan (top 5 to keep it fast)
    # ----------------------------------------------------------------
    print(f"[2] daily_radar_scan(top_n=5, use_orchestrator={use_orch})")
    scan = daily_radar_scan(top_n=5, use_orchestrator=use_orch)

    if "error" in scan:
        print(f"    ERROR: {scan['error']}")
    else:
        print(f"    {scan['morning_briefing']}")
        print(f"    Top clients analysed: {len(scan['top_clients'])}")
        for c in scan["top_clients"]:
            print(
                f"      [{c.get('final_priority', 0):5.1f}] {c.get('client_id')} "
                f"{c.get('client_name')} Tier-{c.get('tier')} "
                f"- {len(c.get('triggers', []))} trigger(s), "
                f"analyses: {list(c.get('financial_analyses', {}).keys())}"
            )
        print(f"    Cohort patterns detected: {len(scan.get('cohort_patterns', []))}")
    print()

    # ----------------------------------------------------------------
    # Test 3: prepare_meeting
    # ----------------------------------------------------------------
    print(f"[3] prepare_meeting('{client_id}', use_orchestrator={use_orch})")
    pkg = prepare_meeting(client_id, use_orchestrator=use_orch)

    if "error" in pkg and not pkg.get("client_name"):
        print(f"    ERROR: {pkg['error']}")
    else:
        print(f"    Client: {pkg.get('client_name')} | Date: {pkg.get('prepared_date')}")
        mp = pkg.get("meeting_package", {})
        if "error" in mp:
            print(f"    Meeting package error: {mp['error']}")
        else:
            print(f"    Summary: {str(mp.get('executive_summary', ''))[:150]}...")
            print(f"    Agenda items: {len(mp.get('agenda', []))}")
            print(f"    Recommendations: {len(mp.get('recommendations', []))}")
        print(f"    Document review: {str(pkg.get('document_review', ''))[:120]}...")
        print(f"    Market context: {str(pkg.get('market_context', ''))[:120]}...")
        if pkg.get("orchestrator_summary"):
            print(f"    Orchestrator summary: {str(pkg['orchestrator_summary'])[:300]}...")
    print()

    # ----------------------------------------------------------------
    # Test 4: Full orchestrator agent (optional)
    # ----------------------------------------------------------------
    if use_orch:
        print("[4] Orchestrator agent — full morning briefing (LLM)")
        try:
            orch = create_orchestrator()
            response = orch(
                "Good morning. Scan the book of business and give me a focused morning briefing: "
                "which 3 clients need my attention most urgently today and why?"
            )
            print(f"    {str(response)[:600]}...")
        except Exception as e:
            print(f"    Agent error: {e}")
