"""Composer Agent -- Generates complete client action packages.

Uses Nova 2 Lite via Bedrock Converse API to produce:
  - Full meeting preparation packages (agenda, talking points, questions, action items)
  - Personalized outreach emails (with compliance disclaimer)
  - Cohort campaign templates (batch outreach for clients sharing a trigger pattern)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_clients() -> list[dict[str, Any]]:
    try:
        with open(_DATA_DIR / "clients.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load clients.json: %s", exc)
        return []


def _find_client(client_id: str) -> dict[str, Any] | None:
    for c in _load_clients():
        if c.get("id") == client_id or c.get("client_id") == client_id:
            return c
    return None


def _bedrock_generate(prompt: str, system: str = "", temperature: float = 0.7) -> str:
    """Call Nova 2 Lite via Bedrock Converse API for content generation."""
    try:
        from app.services.bedrock import get_bedrock_service
        svc = get_bedrock_service()
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        return svc.converse(messages, system=system, temperature=temperature, max_tokens=2048)
    except Exception as exc:
        logger.warning("Bedrock unavailable (%s) -- using structured mock", exc)
        return f"[MOCK CONTENT -- Bedrock unavailable: {exc}]\n\n{prompt[:200]}..."


def _client_context_block(client: dict[str, Any]) -> str:
    """Build a compact text block summarising the client for LLM prompts."""
    accounts = client.get("accounts", [])
    total_aum = client.get("aum", sum(a.get("balance", 0) for a in accounts))
    acct_lines = "\n".join(
        f"  - {a.get('account_type', 'Account')} ({a.get('account_id', '?')}): ${a.get('balance', 0):,.0f}"
        for a in accounts
    )
    life_events = client.get("life_events", [])
    events_line = (
        ", ".join(e.get("type", str(e)) for e in life_events[:3]) if life_events else "None recent"
    )
    return f"""Client: {client.get('name')} ({client.get('id')})
Age: {client.get('age')} | Tier: {client.get('tier')} | AUM: ${total_aum:,.0f}
Occupation: {client.get('occupation', 'Unknown')} | Tax bracket: {client.get('tax_bracket', 'Unknown')}
Risk tolerance: {client.get('risk_tolerance', 'Unknown')} | Marital status: {client.get('marital_status', 'Unknown')}
Accounts:
{acct_lines if acct_lines else "  - No accounts on file"}
Recent life events: {events_line}
Last meeting: {client.get('last_meeting_date', 'Unknown')}"""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def generate_meeting_prep(client_id: str, triggers_json: str) -> str:
    """Generate a complete meeting preparation package for an upcoming client meeting.

    Produces a structured package including: executive summary, personalized agenda,
    talking points for each active trigger, probing questions to ask the client,
    specific financial recommendations with dollar amounts, and a pre-meeting checklist.
    Uses Nova 2 Lite to generate natural, advisor-ready content grounded in the
    trigger data and client profile.

    Args:
        client_id: Client identifier (e.g., "CLT001").
        triggers_json: JSON string from scan_client_triggers tool output, containing
            the list of active triggers, their descriptions, details, and priority score.
            Must include fields: client_id, client_name, tier, triggers (list),
            compound_triggers (list), final_priority, action_items.

    Returns:
        JSON string with fields:
            - client_id (str), client_name (str), meeting_date (str)
            - executive_summary (str): 3-5 sentence overview for the advisor
            - agenda (list): Ordered agenda items with time estimates
            - talking_points (list): Per-trigger talking points with dollar amounts
            - client_questions (list): Open-ended questions to ask the client
            - recommendations (list): Specific action recommendations
            - pre_meeting_checklist (list): Items advisor should prepare before meeting
            - compliance_note (str): Standard compliance reminder
            - error (str): Set only on failure
    """
    client = _find_client(client_id)
    if client is None:
        return json.dumps({"error": f"Client '{client_id}' not found"})

    try:
        triggers_data = json.loads(triggers_json) if isinstance(triggers_json, str) else triggers_json
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid triggers_json: {exc}"})

    triggers = triggers_data.get("triggers", [])
    compound = triggers_data.get("compound_triggers", [])
    priority = triggers_data.get("final_priority", 0)
    action_items = triggers_data.get("action_items", [])
    client_name = triggers_data.get("client_name") or client.get("name", "Client")

    ctx = _client_context_block(client)
    trigger_summary = "\n".join(
        f"  - [{t['type']}] {t['description']} (urgency={t['base_urgency']}, revenue_impact={t['revenue_impact']})"
        for t in triggers
    )
    compound_summary = "\n".join(
        f"  - {c.get('pattern_name', 'Compound')}: {c.get('description', '')}"
        for c in compound
    ) if compound else "  - None detected"

    system_prompt = (
        "You are an expert financial advisor assistant specializing in wealth management "
        "for high-net-worth clients. Generate professional, actionable meeting preparation "
        "content. Be specific with dollar amounts and deadlines. Write in a professional "
        "but warm tone appropriate for client-facing communication."
    )

    prompt = f"""Generate a comprehensive meeting preparation package for the following client.

{ctx}

ACTIVE TRIGGERS (priority score: {priority:.1f}/100):
{trigger_summary if trigger_summary else "  - No active triggers"}

COMPOUND PATTERNS:
{compound_summary}

PENDING ACTION ITEMS:
{chr(10).join(f"  - {item}" for item in action_items) if action_items else "  - None"}

Generate a meeting prep package in this exact JSON format:
{{
  "executive_summary": "<3-5 sentence overview of the client situation and what this meeting needs to accomplish>",
  "agenda": [
    {{"item": "<agenda item>", "time_minutes": <int>, "priority": "high|medium|low"}}
  ],
  "talking_points": [
    {{"trigger": "<trigger type>", "opening": "<how to introduce this topic>", "key_points": ["<point 1>", "<point 2>"], "dollar_impact": "<specific $ amount or range>"}}
  ],
  "client_questions": [
    "<open-ended question to ask client>"
  ],
  "recommendations": [
    {{"action": "<specific action>", "rationale": "<why>", "deadline": "<date or timeframe>", "dollar_amount": "<$ if applicable>"}}
  ],
  "pre_meeting_checklist": [
    "<item to prepare before meeting>"
  ]
}}

Return only valid JSON. No preamble or explanation."""

    try:
        raw = _bedrock_generate(prompt, system=system_prompt, temperature=0.5)
        # Extract JSON from the response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        package = json.loads(raw)
    except Exception as exc:
        logger.warning("LLM generation failed, using structured fallback: %s", exc)
        package = {
            "executive_summary": (
                f"{client_name} has {len(triggers)} active trigger(s) with a priority score of "
                f"{priority:.1f}/100. "
                + (f"Key issues: {triggers[0]['description']}" if triggers else "No critical issues detected.")
            ),
            "agenda": [
                {"item": "Portfolio review and performance update", "time_minutes": 10, "priority": "high"},
                *[
                    {"item": t["description"], "time_minutes": 10, "priority": "high"}
                    for t in triggers[:4]
                ],
                {"item": "Questions and next steps", "time_minutes": 5, "priority": "medium"},
            ],
            "talking_points": [
                {
                    "trigger": t["type"],
                    "opening": f"I wanted to discuss {t['description']} with you today.",
                    "key_points": [t.get("description", ""), str(t.get("details", ""))],
                    "dollar_impact": "See trigger details",
                }
                for t in triggers[:5]
            ],
            "client_questions": [
                "Have there been any changes in your financial situation since we last met?",
                "Are there any major expenses or life changes coming up in the next 12 months?",
                "How are you feeling about your current investment strategy?",
            ],
            "recommendations": [
                {"action": item, "rationale": "Identified by trigger engine", "deadline": "Within 30 days", "dollar_amount": "TBD"}
                for item in (action_items or ["Schedule follow-up review"])[:5]
            ],
            "pre_meeting_checklist": [
                "Pull current account statements",
                "Review last meeting notes",
                "Prepare RMD calculation if applicable",
                "Check for pending beneficiary updates",
                "Review estate document dates",
            ],
        }

    from datetime import date
    return json.dumps({
        "client_id": client_id,
        "client_name": client_name,
        "meeting_date": date.today().isoformat(),
        **package,
        "compliance_note": (
            "COMPLIANCE REMINDER: All recommendations must be documented in the client's file. "
            "Ensure suitability is established before executing any transactions. "
            "This meeting prep is for internal advisor use only."
        ),
    })


@tool
def generate_outreach_email(client_id: str, trigger_type: str, context: str) -> str:
    """Generate a personalized client outreach email for a specific trigger or opportunity.

    Uses Nova 2 Lite to write a professional, warm email that introduces the relevant
    financial topic without being alarmist. Always includes a compliance disclaimer.
    The email is ready to review and send -- the advisor should personalize before sending.

    Args:
        client_id: Client identifier (e.g., "CLT001").
        trigger_type: The trigger driving the outreach. One of:
            RMD_DUE, RMD_APPROACHING, PORTFOLIO_DRIFT, TLH_OPPORTUNITY, ROTH_WINDOW,
            QCD_OPPORTUNITY, ESTATE_REVIEW_OVERDUE, MEETING_OVERDUE, LIFE_EVENT_RECENT,
            BENEFICIARY_REVIEW, MARKET_EVENT, APPROACHING_MILESTONE.
        context: Additional context string to personalize the email. Can include specific
            dollar amounts, dates, or circumstances identified by the trigger engine
            (e.g., "RMD of $45,230 due by Dec 31" or "portfolio drift in US_EQUITY: +7.2%").

    Returns:
        JSON string with fields:
            - client_id (str), client_name (str), trigger_type (str)
            - subject (str): Ready-to-use email subject line
            - body (str): Full email body (plain text, advisor-ready)
            - tone (str): "informational" | "urgent" | "opportunity"
            - suggested_send_date (str): ISO date for optimal timing
            - compliance_disclaimer (str): Must be included when sending
            - error (str): Set only on failure
    """
    client = _find_client(client_id)
    if client is None:
        return json.dumps({"error": f"Client '{client_id}' not found"})

    client_name = client.get("name", "Client")
    first_name = client.get("first_name") or client_name.split()[0]
    advisor_name = "Your Financial Advisor"  # In production: pull from advisor profile

    ctx = _client_context_block(client)

    # Determine tone based on trigger urgency
    urgent_triggers = {"RMD_DUE", "LIFE_EVENT_RECENT", "PORTFOLIO_DRIFT"}
    opportunity_triggers = {"TLH_OPPORTUNITY", "ROTH_WINDOW", "QCD_OPPORTUNITY", "APPROACHING_MILESTONE"}
    if trigger_type in urgent_triggers:
        tone = "urgent"
    elif trigger_type in opportunity_triggers:
        tone = "opportunity"
    else:
        tone = "informational"

    system_prompt = (
        "You are a professional financial advisor writing to a valued client. "
        "Write in a warm, professional tone. Be specific but not alarmist. "
        "Never give generic advice -- always reference the client's specific situation. "
        "Keep emails concise (200-300 words). Never include specific investment advice "
        "that would require additional suitability review."
    )

    prompt = f"""Write a personalized client outreach email for the following situation.

{ctx}

TRIGGER TYPE: {trigger_type}
TONE: {tone}
SPECIFIC CONTEXT: {context}

Write the email in this exact JSON format:
{{
  "subject": "<compelling, specific subject line>",
  "body": "<full email body, use \\n for line breaks, address client by first name ({first_name}), sign off as {advisor_name}>"
}}

The email should:
- Open with a personal greeting
- Introduce the topic naturally without jargon
- Explain why this is relevant to the client specifically
- Include a clear call to action (schedule a call, review account, etc.)
- Be warm and professional
- NOT include the compliance disclaimer (added separately)

Return only valid JSON."""

    try:
        raw = _bedrock_generate(prompt, system=system_prompt, temperature=0.7)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        email_content = json.loads(raw)
        subject = email_content.get("subject", f"Important Update: {trigger_type.replace('_', ' ').title()}")
        body = email_content.get("body", "")
    except Exception as exc:
        logger.warning("Email generation failed, using template fallback: %s", exc)
        subject, body = _email_template_fallback(trigger_type, first_name, context, advisor_name)

    from datetime import date
    compliance_disclaimer = (
        "This email is for informational purposes only and does not constitute investment advice. "
        "Past performance is not indicative of future results. Please contact our office to discuss "
        "your specific situation before taking any action. "
        "[Firm Name] is a registered investment advisor."
    )

    return json.dumps({
        "client_id": client_id,
        "client_name": client_name,
        "trigger_type": trigger_type,
        "subject": subject,
        "body": body,
        "tone": tone,
        "suggested_send_date": date.today().isoformat(),
        "compliance_disclaimer": compliance_disclaimer,
    })


def _email_template_fallback(
    trigger_type: str, first_name: str, context: str, advisor_name: str
) -> tuple[str, str]:
    """Return a (subject, body) template when Bedrock is unavailable."""
    templates: dict[str, tuple[str, str]] = {
        "RMD_DUE": (
            "Action Required: Your Required Minimum Distribution",
            f"Dear {first_name},\n\nI wanted to reach out regarding your Required Minimum Distribution (RMD) for this year.\n\n{context}\n\nAs a reminder, your RMD must be taken by December 31st to avoid a significant IRS penalty. Please give us a call at your earliest convenience so we can process this distribution before the deadline.\n\nBest regards,\n{advisor_name}",
        ),
        "TLH_OPPORTUNITY": (
            "Year-End Tax-Loss Harvesting Opportunity",
            f"Dear {first_name},\n\nI've identified a potential tax-loss harvesting opportunity in your portfolio that could reduce your tax bill this year.\n\n{context}\n\nWould you have time for a brief call to discuss this strategy? Acting before year-end would maximize the benefit.\n\nBest regards,\n{advisor_name}",
        ),
        "PORTFOLIO_DRIFT": (
            "Portfolio Rebalancing Review",
            f"Dear {first_name},\n\nYour portfolio has drifted from its target allocation and may benefit from rebalancing.\n\n{context}\n\nRebalancing helps maintain your intended risk level. Please reach out to schedule a review.\n\nBest regards,\n{advisor_name}",
        ),
        "ROTH_WINDOW": (
            "Roth Conversion Opportunity Worth Discussing",
            f"Dear {first_name},\n\nBased on your current income situation, this may be an excellent time to consider a Roth IRA conversion.\n\n{context}\n\nConverting now could provide significant long-term tax advantages. Let's schedule a call to explore this.\n\nBest regards,\n{advisor_name}",
        ),
        "QCD_OPPORTUNITY": (
            "Charitable Giving Strategy: QCD for 2026",
            f"Dear {first_name},\n\nIf you plan to make charitable donations this year, a Qualified Charitable Distribution (QCD) from your IRA could offer significant tax advantages.\n\n{context}\n\nThis strategy can satisfy your RMD while excluding the amount from taxable income. Let's discuss.\n\nBest regards,\n{advisor_name}",
        ),
        "MEETING_OVERDUE": (
            "Let's Reconnect -- Scheduling Your Review",
            f"Dear {first_name},\n\nIt's been a while since our last review meeting, and I wanted to reach out to schedule time together.\n\n{context}\n\nA lot can change in the markets and in life, and I want to make sure your financial plan reflects your current goals. Please reply with your availability.\n\nBest regards,\n{advisor_name}",
        ),
        "ESTATE_REVIEW_OVERDUE": (
            "Time to Review Your Estate Documents",
            f"Dear {first_name},\n\nI wanted to touch base about reviewing your estate planning documents.\n\n{context}\n\nEnsuring your documents are current is an important part of protecting your family. I'd like to schedule a review at your convenience.\n\nBest regards,\n{advisor_name}",
        ),
    }
    default = (
        f"Financial Planning Update: {trigger_type.replace('_', ' ').title()}",
        f"Dear {first_name},\n\nI wanted to reach out regarding an important matter in your financial plan.\n\n{context}\n\nPlease contact me at your earliest convenience to discuss next steps.\n\nBest regards,\n{advisor_name}",
    )
    return templates.get(trigger_type, default)


@tool
def generate_cohort_campaign(cohort_json: str) -> str:
    """Generate a batch outreach campaign template for a cohort of clients sharing a trigger.

    Takes the output from the trigger engine's detect_cohort_patterns() and generates:
    - A campaign overview with rationale
    - A parameterized email template with personalization tokens
    - Priority ordering for outreach
    - Key talking points and objection handlers
    - Suggested campaign timeline

    This enables the advisor to efficiently reach out to many clients about the same
    issue (e.g., "all Tier A clients with RMD due") without writing each email from scratch.

    Args:
        cohort_json: JSON string describing the cohort. Can be:
          (a) Output from detect_cohort_patterns() -- dict with keys like "RMD_DUE",
              "PORTFOLIO_DRIFT", etc., each containing {"clients": [...], "count": int,
              "recommended_actions": [...]}
          (b) A custom dict with fields:
              - trigger_type (str): The shared trigger (e.g., "RMD_DUE")
              - clients (list): List of client dicts with id, name, tier, details
              - shared_context (str): Common situation description

    Returns:
        JSON string with fields:
            - campaign_name (str)
            - trigger_type (str)
            - cohort_size (int): Number of clients targeted
            - campaign_rationale (str): Why this outreach matters now
            - email_template (dict): Template with subject and body containing
              {{FIRST_NAME}}, {{SPECIFIC_DETAIL}}, {{DOLLAR_AMOUNT}} tokens
            - personalization_guide (str): How to customize for each client
            - priority_order (list): Client IDs ordered by urgency (highest first)
            - talking_points (list): Key points for phone follow-ups
            - objection_handlers (list): Common objections and suggested responses
            - timeline (list): Suggested send dates and follow-up schedule
            - compliance_note (str)
            - error (str): Set only on failure
    """
    try:
        cohort_data = json.loads(cohort_json) if isinstance(cohort_json, str) else cohort_json
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid cohort_json: {exc}"})

    # Normalize input -- detect_cohort_patterns returns a dict of trigger->cohort,
    # or the user may pass a single cohort dict directly
    if "trigger_type" in cohort_data:
        # Single cohort dict
        trigger_type = cohort_data.get("trigger_type", "UNKNOWN")
        clients = cohort_data.get("clients", [])
        shared_context = cohort_data.get("shared_context", "")
        recommended_actions = cohort_data.get("recommended_actions", [])
    else:
        # detect_cohort_patterns output -- pick the largest cohort
        if not cohort_data:
            return json.dumps({"error": "cohort_json is empty -- no cohort patterns found"})
        trigger_type = max(cohort_data.keys(), key=lambda k: cohort_data[k].get("count", 0))
        cohort = cohort_data[trigger_type]
        clients = cohort.get("clients", [])
        shared_context = f"{len(clients)} clients with {trigger_type}"
        recommended_actions = cohort.get("recommended_actions", [])

    cohort_size = len(clients)
    if cohort_size == 0:
        return json.dumps({"error": "No clients in cohort"})

    # Sort clients by tier priority (A > B > C > D)
    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    sorted_clients = sorted(clients, key=lambda c: tier_order.get(c.get("tier", "D"), 3))
    priority_order = [c.get("id", c.get("client_id", "?")) for c in sorted_clients]
    tier_a_count = sum(1 for c in clients if c.get("tier") == "A")

    system_prompt = (
        "You are a financial advisor creating a targeted outreach campaign. "
        "Write campaign content that is professional, personalized, and action-oriented. "
        "Use clear personalization tokens like {{FIRST_NAME}} and {{SPECIFIC_DETAIL}}."
    )

    prompt = f"""Create a batch outreach email campaign for the following client cohort.

TRIGGER: {trigger_type}
COHORT SIZE: {cohort_size} clients ({tier_a_count} Tier A)
SHARED SITUATION: {shared_context}
RECOMMENDED ACTIONS: {json.dumps(recommended_actions)}

Generate a campaign in this JSON format:
{{
  "campaign_name": "<descriptive campaign name>",
  "campaign_rationale": "<2-3 sentences explaining why this outreach is timely and important>",
  "email_template": {{
    "subject": "<subject line with {{SPECIFIC_DETAIL}} token if appropriate>",
    "body": "<email body with {{FIRST_NAME}}, {{SPECIFIC_DETAIL}}, {{DOLLAR_AMOUNT}} tokens. Use \\n for line breaks. Sign off as [Advisor Name]>"
  }},
  "personalization_guide": "<instructions for filling in the tokens for each client>",
  "talking_points": [
    "<key point for phone follow-up>"
  ],
  "objection_handlers": [
    {{"objection": "<common client objection>", "response": "<suggested advisor response>"}}
  ]
}}

Return only valid JSON."""

    try:
        raw = _bedrock_generate(prompt, system=system_prompt, temperature=0.6)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        campaign = json.loads(raw)
    except Exception as exc:
        logger.warning("Campaign generation failed, using fallback: %s", exc)
        trigger_label = trigger_type.replace("_", " ").title()
        campaign = {
            "campaign_name": f"{trigger_label} Outreach Campaign",
            "campaign_rationale": (
                f"We have identified {cohort_size} clients who share the {trigger_label} trigger. "
                "Proactive outreach now will help clients take timely action and demonstrates "
                "the value of comprehensive financial planning."
            ),
            "email_template": {
                "subject": f"Important: {{SPECIFIC_DETAIL}} -- Action May Be Required",
                "body": (
                    f"Dear {{FIRST_NAME}},\n\n"
                    f"I wanted to reach out regarding {{SPECIFIC_DETAIL}} which may be relevant "
                    f"to your financial plan.\n\n"
                    f"Based on your current situation, taking action now could result in "
                    f"approximately {{DOLLAR_AMOUNT}} in benefit (or avoided cost).\n\n"
                    f"Please contact me to discuss your options.\n\nBest regards,\n[Advisor Name]"
                ),
            },
            "personalization_guide": (
                "Replace {{FIRST_NAME}} with client first name. "
                f"Replace {{SPECIFIC_DETAIL}} with the client's specific {trigger_label} situation. "
                "Replace {{DOLLAR_AMOUNT}} with the estimated financial impact."
            ),
            "talking_points": recommended_actions or [
                f"Address {trigger_label} situation specific to this client",
                "Explain the financial impact and timeline",
                "Outline the recommended next steps",
            ],
            "objection_handlers": [
                {
                    "objection": "I'll take care of it myself",
                    "response": "Absolutely -- I just wanted to make sure you're aware of the details. Let me send you a summary.",
                },
                {
                    "objection": "This isn't a good time",
                    "response": "I understand. When would be a better time? I want to make sure we don't miss the deadline.",
                },
            ],
        }

    from datetime import date, timedelta
    today = date.today()
    timeline = [
        {"week": 1, "action": "Send initial outreach email", "date": today.isoformat()},
        {"week": 2, "action": "Follow-up call for non-responders", "date": (today + timedelta(days=7)).isoformat()},
        {"week": 3, "action": "Final reminder for urgent cases", "date": (today + timedelta(days=14)).isoformat()},
        {"week": 4, "action": "Document outreach in CRM; escalate if unresolved", "date": (today + timedelta(days=21)).isoformat()},
    ]

    return json.dumps({
        "campaign_name": campaign.get("campaign_name", f"{trigger_type} Campaign"),
        "trigger_type": trigger_type,
        "cohort_size": cohort_size,
        "campaign_rationale": campaign.get("campaign_rationale", ""),
        "email_template": campaign.get("email_template", {}),
        "personalization_guide": campaign.get("personalization_guide", ""),
        "priority_order": priority_order,
        "talking_points": campaign.get("talking_points", []),
        "objection_handlers": campaign.get("objection_handlers", []),
        "timeline": timeline,
        "compliance_note": (
            "COMPLIANCE: All outreach must be logged in the CRM. Ensure each client's "
            "suitability profile is current before recommending specific actions. "
            "Obtain client acknowledgment before executing any transactions."
        ),
    })


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_COMPOSER_SYSTEM_PROMPT = """You are a client communications and meeting preparation specialist for a financial advisory firm.

Your role is to transform raw trigger data and client profiles into polished, advisor-ready
content: meeting packages, personalized emails, and cohort campaign templates.

Tools available:
- generate_meeting_prep: Full meeting prep package for a specific client
- generate_outreach_email: Personalized email for a specific trigger and client
- generate_cohort_campaign: Batch campaign template for a group of clients sharing a trigger

Workflow:
1. Always start by understanding the trigger data before generating content.
2. Use specific dollar amounts, dates, and client details whenever available.
3. Meeting prep packages should give the advisor everything they need in one document.
4. Emails should be warm, specific, and immediately ready to send (after advisor review).
5. Cohort campaigns should be efficient -- minimize advisor time per client contact.

Quality standards:
- Never use generic advice. Always reference the specific trigger and client situation.
- All financial specifics must come from the trigger data -- never invent numbers.
- Compliance disclaimers must always be included in emails.
- Meeting agendas should prioritize triggers by urgency (highest base_urgency first).
- Roth conversion emails should mention the IRMAA risk if relevant.
- RMD emails must include the deadline (Dec 31 or April 1 for first-ever RMD).
"""


def create_composer_agent() -> Agent:
    """Create and return the Composer Agent (Nova 2 Lite + 3 content generation tools)."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0.7,  # creative for content generation
        max_tokens=4096,
    )
    return Agent(
        model=model,
        system_prompt=_COMPOSER_SYSTEM_PROMPT,
        tools=[generate_meeting_prep, generate_outreach_email, generate_cohort_campaign],
    )


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=== Composer Agent Test ===\n")

    # Build a minimal trigger payload for CLT001
    sample_triggers = json.dumps({
        "client_id": "CLT001",
        "client_name": "Mark Johnson",
        "tier": "A",
        "trigger_count": 2,
        "final_priority": 78.5,
        "triggers": [
            {
                "type": "RMD_DUE",
                "description": "RMD of approximately $45,230 due by December 31, 2026",
                "base_urgency": 95,
                "revenue_impact": 80,
                "details": {"rmd_required": 45230, "deadline": "December 31, 2026"},
            },
            {
                "type": "QCD_OPPORTUNITY",
                "description": "Client is 77, QCD-eligible, charitable giving can offset RMD",
                "base_urgency": 50,
                "revenue_impact": 60,
                "details": {"qcd_limit": 111000, "recommended_qcd": 25000},
            },
        ],
        "compound_triggers": [
            {"pattern_name": "RMD + QCD", "description": "Combine RMD distribution with charitable giving via QCD for maximum tax efficiency"}
        ],
        "action_items": [
            "Process RMD before Dec 31 -- $45,230 required",
            "Coordinate QCD up to $25,000 to offset charitable giving",
        ],
    })

    print("[1] generate_meeting_prep('CLT001')")
    result = json.loads(generate_meeting_prep("CLT001", sample_triggers))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Client: {result['client_name']} | Date: {result['meeting_date']}")
        print(f"    Summary: {result['executive_summary'][:150]}...")
        print(f"    Agenda items: {len(result.get('agenda', []))}")
        print(f"    Recommendations: {len(result.get('recommendations', []))}")
    print()

    print("[2] generate_outreach_email('CLT001', 'RMD_DUE')")
    result = json.loads(generate_outreach_email("CLT001", "RMD_DUE", "RMD of $45,230 due by December 31, 2026"))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Subject: {result['subject']}")
        print(f"    Tone: {result['tone']}")
        print(f"    Body preview: {result['body'][:200]}...")
    print()

    print("[3] generate_cohort_campaign (RMD cohort)")
    cohort = json.dumps({
        "trigger_type": "RMD_DUE",
        "clients": [
            {"id": "CLT001", "name": "Mark Johnson", "tier": "A"},
            {"id": "CLT003", "name": "Susan Williams", "tier": "A"},
            {"id": "CLT007", "name": "Robert Davis", "tier": "B"},
        ],
        "shared_context": "3 clients with RMD due by December 31, 2026",
        "recommended_actions": ["Process RMD distributions", "Coordinate QCD where applicable"],
    })
    result = json.loads(generate_cohort_campaign(cohort))
    if "error" in result:
        print(f"    ERROR: {result['error']}")
    else:
        print(f"    Campaign: {result['campaign_name']}")
        print(f"    Cohort size: {result['cohort_size']}")
        print(f"    Priority order: {result['priority_order']}")
        print(f"    Timeline steps: {len(result['timeline'])}")
    print()

    if "--agent" in sys.argv:
        print("[4] Composer Agent (full LLM generation)...")
        try:
            agent = create_composer_agent()
            response = agent(
                f"Generate a meeting prep package for CLT001 (Mark Johnson) using these triggers: {sample_triggers}"
            )
            print(response)
        except Exception as e:
            print(f"    Agent error (expected without AWS creds): {e}")
