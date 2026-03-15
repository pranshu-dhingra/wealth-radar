"""Compound trigger detection engine.

Priority scoring formula (CLAUDE.md):
  priority = (base_urgency × 0.6) + (revenue_impact × 0.2) + (compound_bonus × 0.2)
  compound_bonus = 30 per additional co-occurring trigger (i.e., 30 × (n_triggers - 1))
  tier_multiplier: A=1.5, B=1.2, C=1.0, D=0.8
  final_priority = priority × tier_multiplier  (capped at 100)

Individual trigger base scores (base_urgency, revenue_impact):
  RMD_DUE              (95, 80)  — RMD-eligible, not yet distributed this year
  RMD_APPROACHING      (65, 60)  — Turns RMD age within 12 months
  PORTFOLIO_DRIFT      (70, 65)  — Any asset class >5% from target
  TLH_OPPORTUNITY      (60, 70)  — Unrealized loss >$1,000 in taxable account
  ROTH_WINDOW          (55, 75)  — Gap year: retired, pre-SS, pre-RMD
  QCD_OPPORTUNITY      (50, 60)  — Age 70½+, RMD-eligible, charitable intent
  ESTATE_REVIEW_OVERDUE(60, 55)  — Docs >3 years old or missing
  MEETING_OVERDUE      (45, 50)  — Past due per tier meeting frequency
  LIFE_EVENT_RECENT    (75, 65)  — Major event in last 90 days, unresolved
  BENEFICIARY_REVIEW   (50, 45)  — Not reviewed in 2+ years
  MARKET_EVENT         (70, 60)  — Market event impacts client's positions
  APPROACHING_MILESTONE(55, 50)  — Key age within 12 months: 59½,62,65,70½,73,75
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY = date(2026, 3, 8)  # Project date per CLAUDE.md

TIER_MULTIPLIER: dict[str, float] = {
    "A": 1.5,
    "B": 1.2,
    "C": 1.0,
    "D": 0.8,
}

# (base_urgency, revenue_impact) per trigger type
TRIGGER_BASE_SCORES: dict[str, tuple[int, int]] = {
    "RMD_DUE":              (95, 80),
    "RMD_APPROACHING":      (65, 60),
    "PORTFOLIO_DRIFT":      (70, 65),
    "TLH_OPPORTUNITY":      (60, 70),
    "ROTH_WINDOW":          (55, 75),
    "QCD_OPPORTUNITY":      (50, 60),
    "ESTATE_REVIEW_OVERDUE":(60, 55),
    "MEETING_OVERDUE":      (45, 50),
    "LIFE_EVENT_RECENT":    (75, 65),
    "BENEFICIARY_REVIEW":   (50, 45),
    "MARKET_EVENT":         (70, 60),
    "APPROACHING_MILESTONE":(55, 50),
}

# Ages that represent key financial milestones
MILESTONE_AGES = [59.5, 62, 65, 70.5, 73, 75]

# Meeting frequency in days per tier
MEETING_FREQUENCY_DAYS: dict[str, int] = {
    "A": 91,   # ~4×/year
    "B": 122,  # ~3×/year (middle of 2–3 range)
    "C": 183,  # ~2×/year
    "D": 365,  # 1×/year
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Trigger:
    trigger_type: str
    client_id: str
    base_urgency: int
    revenue_impact: int
    details: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def raw_priority(self, compound_bonus: int = 0) -> float:
        """Compute raw priority (before tier multiplier)."""
        return (
            self.base_urgency * 0.6
            + self.revenue_impact * 0.2
            + compound_bonus * 0.2
        )


@dataclass
class ClientScanResult:
    client_id: str
    client_name: str
    tier: str
    triggers: list[Trigger] = field(default_factory=list)
    compound_triggers: list[dict[str, Any]] = field(default_factory=list)
    final_priority: float = 0.0
    action_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "tier": self.tier,
            "trigger_count": len(self.triggers),
            "triggers": [
                {
                    "type": t.trigger_type,
                    "base_urgency": t.base_urgency,
                    "revenue_impact": t.revenue_impact,
                    "description": t.description,
                    "details": t.details,
                }
                for t in self.triggers
            ],
            "compound_triggers": self.compound_triggers,
            "final_priority": round(self.final_priority, 2),
            "action_items": self.action_items,
        }


# ---------------------------------------------------------------------------
# Priority calculation
# ---------------------------------------------------------------------------

def _compute_priority(triggers: list[Trigger], tier: str) -> float:
    """Apply the CLAUDE.md priority formula with tier multiplier.

    priority = (base_urgency × 0.6) + (revenue_impact × 0.2) + (compound_bonus × 0.2)
    compound_bonus = 30 × (n_triggers - 1)
    final_priority = priority × tier_multiplier  (capped at 100)
    """
    if not triggers:
        return 0.0

    n = len(triggers)
    compound_bonus = 30 * (n - 1)

    # Use the highest-urgency trigger as the "anchor" for base calculations,
    # then add revenue_impact and compound_bonus contributions
    anchor = max(triggers, key=lambda t: t.base_urgency)
    raw = (
        anchor.base_urgency * 0.6
        + anchor.revenue_impact * 0.2
        + compound_bonus * 0.2
    )

    multiplier = TIER_MULTIPLIER.get(tier.upper(), 1.0)
    return min(100.0, round(raw * multiplier, 2))


# ---------------------------------------------------------------------------
# Individual trigger detectors
# ---------------------------------------------------------------------------

def _detect_rmd_due(client: dict) -> Trigger | None:
    """RMD_DUE — RMD-eligible but not yet distributed this year."""
    if not client.get("rmd_eligible"):
        return None
    if client.get("rmd_taken_this_year"):
        return None

    rmd_amount = float(client.get("rmd_amount_estimated", 0.0))
    bu, ri = TRIGGER_BASE_SCORES["RMD_DUE"]
    return Trigger(
        trigger_type="RMD_DUE",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"2026 RMD of ~${rmd_amount:,.0f} not yet distributed. "
            "Deadline: December 31, 2026 (or April 1 in first RMD year). "
            "Failure triggers 25% excise tax (IRC §4974, reduced by SECURE 2.0 Sec. 302)."
        ),
        details={
            "rmd_amount_estimated": rmd_amount,
            "rmd_overdue": client.get("rmd_overdue", False),
        },
    )


def _detect_rmd_approaching(client: dict) -> Trigger | None:
    """RMD_APPROACHING — Client turns RMD age (73 or 75) within the next 12 months."""
    if client.get("rmd_eligible"):
        return None  # Already RMD-eligible, use RMD_DUE instead

    age = int(client.get("age", 0))
    birth_year = int(client.get("date_of_birth", "1900-01-01").split("-")[0])

    # SECURE 2.0: age 73 for born 1951–1959, age 75 for born 1960+
    rmd_start = 75 if birth_year >= 1960 else 73
    years_to_rmd = rmd_start - age

    if years_to_rmd < 0 or years_to_rmd > 1:
        return None

    bu, ri = TRIGGER_BASE_SCORES["RMD_APPROACHING"]
    return Trigger(
        trigger_type="RMD_APPROACHING",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"Client turns {rmd_start} within 12 months — RMD begins. "
            "Time to optimize Roth conversions and QCDs before RMD forces taxable distributions."
        ),
        details={"rmd_start_age": rmd_start, "years_to_rmd": years_to_rmd},
    )


def _detect_portfolio_drift(client: dict) -> Trigger | None:
    """PORTFOLIO_DRIFT — Any asset class exceeds 5% absolute drift from target."""
    if not client.get("has_portfolio_drift"):
        # Also check max_drift_pct directly for flexibility
        max_drift = abs(float(client.get("max_drift_pct", 0.0)))
        if max_drift <= 5.0:
            return None

    max_drift = abs(float(client.get("max_drift_pct", 0.0)))
    drift_map = client.get("portfolio_drift", {})
    breached = {k: v for k, v in drift_map.items() if abs(v) > 5.0}

    bu, ri = TRIGGER_BASE_SCORES["PORTFOLIO_DRIFT"]
    # Scale urgency with severity
    scaled_urgency = min(100, int(bu + max(0, max_drift - 5.0) * 2))
    return Trigger(
        trigger_type="PORTFOLIO_DRIFT",
        client_id=client["id"],
        base_urgency=scaled_urgency,
        revenue_impact=ri,
        description=(
            f"Portfolio drift detected. Max drift: {max_drift:.1f}%. "
            f"Breached classes: {list(breached.keys()) or 'see details'}. "
            "Rebalancing required per IPS (5% threshold)."
        ),
        details={
            "max_drift_pct": max_drift,
            "breached_classes": breached,
        },
    )


def _detect_tlh_opportunity(client: dict) -> Trigger | None:
    """TLH_OPPORTUNITY — Client has TLH opportunity flagged."""
    if not client.get("tax_loss_harvesting_opportunity"):
        return None

    bu, ri = TRIGGER_BASE_SCORES["TLH_OPPORTUNITY"]
    return Trigger(
        trigger_type="TLH_OPPORTUNITY",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            "Tax-loss harvesting opportunity detected in taxable account(s). "
            "Unrealized loss >$1,000 — harvest before year-end. "
            "Sell loser, immediately buy replacement ETF to maintain exposure (IRC §1091)."
        ),
        details={"tlh_flagged": True},
    )


def _detect_roth_window(client: dict) -> Trigger | None:
    """ROTH_WINDOW — Gap-year opportunity: retired, pre-Social Security, pre-RMD."""
    if not client.get("roth_conversion_candidate"):
        return None
    if client.get("rmd_eligible"):
        return None  # RMD_DUE takes precedence

    occupation = str(client.get("occupation", "")).lower()
    is_retired = "retired" in occupation or occupation == "retired"

    bu, ri = TRIGGER_BASE_SCORES["ROTH_WINDOW"]
    return Trigger(
        trigger_type="ROTH_WINDOW",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            "Roth conversion window detected. "
            "Client is retired with reduced income — fill tax bracket with Roth conversions "
            "before Social Security and/or RMDs begin. Watch IRMAA thresholds (2-year lookback)."
        ),
        details={
            "is_retired": is_retired,
            "roth_conversion_candidate": True,
        },
    )


def _detect_qcd_opportunity(client: dict) -> Trigger | None:
    """QCD_OPPORTUNITY — Age 70½+, takes RMD, has charitable intent."""
    if not client.get("qcd_eligible"):
        return None
    if not client.get("rmd_eligible"):
        return None

    qcd_ytd = float(client.get("qcd_amount_gifted_ytd", 0.0))
    qcd_limit = float(client.get("qcd_limit_2026", 111_000.0))
    remaining = max(0.0, qcd_limit - qcd_ytd)

    if remaining <= 0:
        return None

    bu, ri = TRIGGER_BASE_SCORES["QCD_OPPORTUNITY"]
    return Trigger(
        trigger_type="QCD_OPPORTUNITY",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"QCD opportunity: up to ${remaining:,.0f} remaining capacity in 2026. "
            "QCD satisfies RMD obligation without adding to taxable income (IRC §408(d)(8)). "
            "Especially valuable if client uses standard deduction."
        ),
        details={
            "qcd_limit_2026": qcd_limit,
            "qcd_taken_ytd": qcd_ytd,
            "qcd_remaining": remaining,
        },
    )


def _detect_estate_review_overdue(client: dict) -> Trigger | None:
    """ESTATE_REVIEW_OVERDUE — Estate docs >3 years old or missing."""
    if client.get("estate_docs_outdated"):
        bu, ri = TRIGGER_BASE_SCORES["ESTATE_REVIEW_OVERDUE"]
        return Trigger(
            trigger_type="ESTATE_REVIEW_OVERDUE",
            client_id=client["id"],
            base_urgency=bu,
            revenue_impact=ri,
            description=(
                "Estate documents are outdated or missing. "
                "Review will, trust, POA, and healthcare directive for currency."
            ),
            details={"estate_docs_outdated": True},
        )

    # Manual scan of estate_documents for missing or >3yr-old docs
    estate_docs = client.get("estate_documents", {})
    cutoff = TODAY - timedelta(days=365 * 3)
    issues: list[str] = []

    for doc_name, doc in estate_docs.items():
        status = str(doc.get("status", "")).lower()
        if status == "missing":
            issues.append(f"{doc_name}: MISSING")
        elif status == "current":
            date_str = doc.get("date_executed")
            if date_str:
                try:
                    executed = date.fromisoformat(date_str)
                    if executed < cutoff:
                        issues.append(f"{doc_name}: executed {date_str} (>3 years ago)")
                except ValueError:
                    pass

    if not issues:
        return None

    bu, ri = TRIGGER_BASE_SCORES["ESTATE_REVIEW_OVERDUE"]
    return Trigger(
        trigger_type="ESTATE_REVIEW_OVERDUE",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=f"Estate document review needed: {'; '.join(issues)}.",
        details={"issues": issues},
    )


def _detect_meeting_overdue(client: dict) -> Trigger | None:
    """MEETING_OVERDUE — Past due per tier meeting frequency."""
    last_meeting_str = client.get("last_meeting_date")
    if not last_meeting_str:
        # No meeting ever recorded — flag it
        bu, ri = TRIGGER_BASE_SCORES["MEETING_OVERDUE"]
        return Trigger(
            trigger_type="MEETING_OVERDUE",
            client_id=client["id"],
            base_urgency=bu,
            revenue_impact=ri,
            description="No meeting on record. Schedule initial review.",
            details={"last_meeting_date": None},
        )

    try:
        last_meeting = date.fromisoformat(last_meeting_str)
    except ValueError:
        return None

    tier = str(client.get("tier", "C")).upper()
    max_days = MEETING_FREQUENCY_DAYS.get(tier, 365)
    days_since = (TODAY - last_meeting).days

    if days_since <= max_days:
        return None

    bu, ri = TRIGGER_BASE_SCORES["MEETING_OVERDUE"]
    overdue_by = days_since - max_days
    return Trigger(
        trigger_type="MEETING_OVERDUE",
        client_id=client["id"],
        base_urgency=min(100, bu + overdue_by // 10),  # escalate with delay
        revenue_impact=ri,
        description=(
            f"Last meeting: {last_meeting_str} ({days_since} days ago). "
            f"Tier {tier} requires meeting every {max_days} days. "
            f"Overdue by {overdue_by} days."
        ),
        details={
            "last_meeting_date": last_meeting_str,
            "days_since_meeting": days_since,
            "required_frequency_days": max_days,
            "overdue_by_days": overdue_by,
        },
    )


def _detect_life_event(client: dict) -> Trigger | None:
    """LIFE_EVENT_RECENT — Major unresolved life event in last 90 days."""
    if not client.get("has_recent_life_event"):
        # Also manually check life_events array
        life_events = client.get("life_events", [])
        window = TODAY - timedelta(days=90)
        recent_unresolved = [
            e for e in life_events
            if not e.get("resolved", True)
            and _parse_date_safe(e.get("date")) is not None
            and _parse_date_safe(e.get("date")) >= window
        ]
        if not recent_unresolved:
            return None
        events_to_report = recent_unresolved
    else:
        life_events = client.get("life_events", [])
        window = TODAY - timedelta(days=90)
        events_to_report = [
            e for e in life_events
            if not e.get("resolved", True)
            and _parse_date_safe(e.get("date")) is not None
            and _parse_date_safe(e.get("date")) >= window
        ]
        if not events_to_report:
            # has_recent_life_event flag is True but no matching events — use flag
            events_to_report = [{"type": "unknown", "description": "Recent life event flagged"}]

    bu, ri = TRIGGER_BASE_SCORES["LIFE_EVENT_RECENT"]
    descriptions = [e.get("type", "event").replace("_", " ").title() for e in events_to_report]
    return Trigger(
        trigger_type="LIFE_EVENT_RECENT",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"Recent unresolved life event(s): {', '.join(descriptions)}. "
            "Review financial plan, beneficiaries, and tax implications."
        ),
        details={"recent_events": events_to_report},
    )


def _detect_beneficiary_review(client: dict) -> Trigger | None:
    """BENEFICIARY_REVIEW — Beneficiary not reviewed in 2+ years on any account."""
    cutoff = TODAY - timedelta(days=365 * 2)
    stale_accounts: list[str] = []

    for acct in client.get("accounts", []):
        # Flag if beneficiary not designated, or last review was >2 years ago
        if not acct.get("beneficiary_designated", True):
            stale_accounts.append(f"{acct.get('account_id', '?')} (no beneficiary)")
            continue
        review_str = acct.get("beneficiary_last_reviewed")
        if review_str:
            try:
                reviewed = date.fromisoformat(review_str)
                if reviewed < cutoff:
                    stale_accounts.append(
                        f"{acct.get('account_id', '?')} (last reviewed {review_str})"
                    )
            except ValueError:
                pass

    if not stale_accounts:
        return None

    bu, ri = TRIGGER_BASE_SCORES["BENEFICIARY_REVIEW"]
    return Trigger(
        trigger_type="BENEFICIARY_REVIEW",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"Beneficiary review needed on {len(stale_accounts)} account(s): "
            f"{', '.join(stale_accounts[:3])}{'...' if len(stale_accounts) > 3 else ''}."
        ),
        details={"stale_accounts": stale_accounts},
    )


def _detect_market_event(client: dict, market_events: list[dict]) -> Trigger | None:
    """MARKET_EVENT — A market event materially impacts this client's holdings."""
    if not market_events:
        return None

    client_allocation = client.get("current_allocation", {})
    affected: list[dict] = []

    for event in market_events:
        impacted_classes = event.get("impacted_asset_classes", [])
        for ac in impacted_classes:
            if ac in client_allocation and client_allocation[ac] > 5.0:
                affected.append(event)
                break  # count event once per client

    if not affected:
        return None

    bu, ri = TRIGGER_BASE_SCORES["MARKET_EVENT"]
    event_names = [e.get("name", e.get("type", "Market event")) for e in affected]
    return Trigger(
        trigger_type="MARKET_EVENT",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=(
            f"Market event(s) affect this client's holdings: {', '.join(event_names[:3])}. "
            "Review allocation impact and consider rebalancing or TLH."
        ),
        details={"affected_events": affected[:5]},
    )


def _detect_approaching_milestone(client: dict) -> Trigger | None:
    """APPROACHING_MILESTONE — Client approaching a key financial age within 12 months."""
    dob_str = client.get("date_of_birth", "")
    if not dob_str:
        return None

    try:
        dob = date.fromisoformat(dob_str)
    except ValueError:
        return None

    age_exact = (TODAY - dob).days / 365.25
    look_ahead = 1.0  # years

    upcoming: list[dict] = []
    for milestone in MILESTONE_AGES:
        years_away = milestone - age_exact
        if 0 < years_away <= look_ahead:
            upcoming.append({
                "age": milestone,
                "years_away": round(years_away, 2),
                "significance": _milestone_significance(milestone),
            })

    if not upcoming:
        return None

    bu, ri = TRIGGER_BASE_SCORES["APPROACHING_MILESTONE"]
    milestone_descs = [
        f"Age {m['age']} ({m['years_away']:.1f} yrs): {m['significance']}"
        for m in upcoming
    ]
    return Trigger(
        trigger_type="APPROACHING_MILESTONE",
        client_id=client["id"],
        base_urgency=bu,
        revenue_impact=ri,
        description=f"Approaching milestone(s): {'; '.join(milestone_descs)}.",
        details={"upcoming_milestones": upcoming},
    )


def _milestone_significance(age: float) -> str:
    sigs = {
        59.5: "Penalty-free IRA/401k withdrawals begin (IRC §72(t))",
        62:   "Earliest Social Security claiming age",
        65:   "Medicare eligibility begins",
        70.5: "QCD eligibility begins (IRC §408(d)(8))",
        73:   "RMD age for born 1951–1959 (SECURE 2.0)",
        75:   "RMD age for born 1960+ (SECURE 2.0)",
    }
    return sigs.get(age, f"Key planning age {age}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_safe(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Compound trigger detection
# ---------------------------------------------------------------------------

# Compound patterns: combinations that deserve special flagging
COMPOUND_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "RMD + QCD Combo",
        "requires": {"RMD_DUE", "QCD_OPPORTUNITY"},
        "description": (
            "Client owes RMD AND is QCD-eligible — route up to $111,000 of RMD directly "
            "to charity as QCD to eliminate taxable income on that amount (IRC §408(d)(8))."
        ),
        "urgency_boost": 10,
    },
    {
        "name": "RMD + TLH Coordination",
        "requires": {"RMD_DUE", "TLH_OPPORTUNITY"},
        "description": (
            "Client must take RMD (adding taxable income) AND has harvestable losses — "
            "harvest losses now to offset RMD income and minimize net tax impact."
        ),
        "urgency_boost": 8,
    },
    {
        "name": "Roth + Drift Rebalancing",
        "requires": {"ROTH_WINDOW", "PORTFOLIO_DRIFT"},
        "description": (
            "Gap-year Roth conversion opportunity coincides with needed rebalancing — "
            "rebalance inside IRA before converting to Roth to avoid taxable gain realization."
        ),
        "urgency_boost": 8,
    },
    {
        "name": "Life Event + Estate Review",
        "requires": {"LIFE_EVENT_RECENT", "ESTATE_REVIEW_OVERDUE"},
        "description": (
            "Recent major life event AND estate documents are outdated — "
            "urgent estate plan review needed (beneficiary changes, trust updates, POA)."
        ),
        "urgency_boost": 12,
    },
    {
        "name": "Life Event + Beneficiary",
        "requires": {"LIFE_EVENT_RECENT", "BENEFICIARY_REVIEW"},
        "description": (
            "Recent life event may invalidate existing beneficiary designations — "
            "update all accounts immediately."
        ),
        "urgency_boost": 10,
    },
    {
        "name": "Market Event + TLH",
        "requires": {"MARKET_EVENT", "TLH_OPPORTUNITY"},
        "description": (
            "Market downturn creates TLH opportunity — coordinate harvest trades "
            "with any rebalancing to maximize tax efficiency."
        ),
        "urgency_boost": 8,
    },
    {
        "name": "Market Event + Drift",
        "requires": {"MARKET_EVENT", "PORTFOLIO_DRIFT"},
        "description": (
            "Market event has pushed portfolio out of IPS bands — "
            "rebalance while also evaluating loss harvesting opportunities."
        ),
        "urgency_boost": 8,
    },
    {
        "name": "Full Retirement Transition",
        "requires": {"RMD_DUE", "QCD_OPPORTUNITY", "TLH_OPPORTUNITY"},
        "description": (
            "Triple retirement income planning moment: RMD due, QCD available, "
            "and losses to harvest — coordinate all three for maximum tax efficiency."
        ),
        "urgency_boost": 15,
    },
    {
        "name": "Milestone + Roth Window",
        "requires": {"APPROACHING_MILESTONE", "ROTH_WINDOW"},
        "description": (
            "Approaching a key age milestone AND currently in a Roth conversion window — "
            "act before the milestone triggers new obligations (RMD, Medicare, SS)."
        ),
        "urgency_boost": 10,
    },
]


def _detect_compound_triggers(triggers: list[Trigger]) -> list[dict[str, Any]]:
    """Identify compound trigger patterns from the set of individual triggers."""
    trigger_types = {t.trigger_type for t in triggers}
    compounds = []

    for pattern in COMPOUND_PATTERNS:
        if pattern["requires"].issubset(trigger_types):
            compounds.append({
                "name": pattern["name"],
                "triggers_involved": sorted(pattern["requires"]),
                "description": pattern["description"],
                "urgency_boost": pattern["urgency_boost"],
            })

    return compounds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_client(
    client: dict,
    holdings: list[dict] | None = None,
    market_events: list[dict] | None = None,
) -> ClientScanResult:
    """Scan a single client for all individual and compound triggers.

    Args:
        client: Client dict from clients.json (full record).
        holdings: Optional list of holding dicts for this client (from holdings.json).
                  Currently used to enrich context; trigger flags come from client record.
        market_events: Optional list of market event dicts.

    Returns:
        ClientScanResult with all triggers, compound detections, and priority score.
    """
    market_events = market_events or []

    # --- Run all individual detectors ---
    detectors = [
        _detect_rmd_due(client),
        _detect_rmd_approaching(client),
        _detect_portfolio_drift(client),
        _detect_tlh_opportunity(client),
        _detect_roth_window(client),
        _detect_qcd_opportunity(client),
        _detect_estate_review_overdue(client),
        _detect_meeting_overdue(client),
        _detect_life_event(client),
        _detect_beneficiary_review(client),
        _detect_market_event(client, market_events),
        _detect_approaching_milestone(client),
    ]
    triggers = [t for t in detectors if t is not None]

    # --- Compound trigger detection ---
    compounds = _detect_compound_triggers(triggers)

    # --- Priority scoring ---
    tier = str(client.get("tier", "C")).upper()
    final_priority = _compute_priority(triggers, tier)

    # Apply compound urgency boosts to final priority
    for compound in compounds:
        boost = compound.get("urgency_boost", 0)
        final_priority = min(100.0, final_priority + boost * TIER_MULTIPLIER.get(tier, 1.0))

    # --- Action items ---
    action_items = _build_action_items(triggers, compounds, client)

    return ClientScanResult(
        client_id=client["id"],
        client_name=client.get("name", "Unknown"),
        tier=tier,
        triggers=triggers,
        compound_triggers=compounds,
        final_priority=round(final_priority, 2),
        action_items=action_items,
    )


def scan_all_clients(
    all_clients: list[dict],
    all_holdings: dict[str, list[dict]] | None = None,
    market_events: list[dict] | None = None,
) -> list[ClientScanResult]:
    """Scan every client in the book of business and return prioritized results.

    Args:
        all_clients: List of all client dicts.
        all_holdings: Dict mapping client_id → list of holding dicts (optional).
        market_events: List of market event dicts (optional).

    Returns:
        List of ClientScanResult sorted by final_priority descending.
    """
    all_holdings = all_holdings or {}
    market_events = market_events or []

    results = []
    for client in all_clients:
        client_id = client.get("id", "")
        holdings = all_holdings.get(client_id, [])
        result = scan_client(client, holdings, market_events)
        if result.triggers:  # Only include clients with at least one trigger
            results.append(result)

    results.sort(key=lambda r: r.final_priority, reverse=True)
    return results


def detect_cohort_patterns(all_triggers: list[ClientScanResult]) -> list[dict[str, Any]]:
    """Identify patterns across the entire book of business.

    Finds cohort-level insights: groups of clients sharing the same trigger,
    trending compound patterns, and revenue concentration risks.

    Args:
        all_triggers: List of ClientScanResult from scan_all_clients().

    Returns:
        List of cohort pattern dicts with fields:
            pattern_type, trigger_type (or pattern_name), affected_clients,
            client_count, description, recommended_action.
    """
    from collections import defaultdict

    # Group clients by trigger type
    by_trigger: dict[str, list[str]] = defaultdict(list)
    by_compound: dict[str, list[str]] = defaultdict(list)
    tier_priority: dict[str, list[float]] = defaultdict(list)

    for result in all_triggers:
        for trigger in result.triggers:
            by_trigger[trigger.trigger_type].append(result.client_id)
        for compound in result.compound_triggers:
            by_compound[compound["name"]].append(result.client_id)
        tier_priority[result.tier].append(result.final_priority)

    cohort_patterns = []

    # Individual trigger cohorts (>1 client)
    for trigger_type, client_ids in sorted(by_trigger.items(), key=lambda x: -len(x[1])):
        if len(client_ids) < 2:
            continue
        cohort_patterns.append({
            "pattern_type": "trigger_cohort",
            "trigger_type": trigger_type,
            "affected_clients": client_ids,
            "client_count": len(client_ids),
            "description": (
                f"{len(client_ids)} clients share the {trigger_type} trigger — "
                "consider batch processing or proactive outreach campaign."
            ),
            "recommended_action": _cohort_action(trigger_type, len(client_ids)),
        })

    # Compound trigger cohorts (>0 clients)
    for compound_name, client_ids in sorted(by_compound.items(), key=lambda x: -len(x[1])):
        cohort_patterns.append({
            "pattern_type": "compound_cohort",
            "pattern_name": compound_name,
            "affected_clients": client_ids,
            "client_count": len(client_ids),
            "description": (
                f"{len(client_ids)} client(s) have the compound '{compound_name}' pattern — "
                "high-value multi-trigger coordination opportunity."
            ),
            "recommended_action": (
                f"Prioritize {compound_name} clients for immediate outreach. "
                "Prepare a coordinated action package addressing all involved triggers."
            ),
        })

    # Tier concentration: Tier A clients with high priority
    high_priority_a = [
        r.client_id for r in all_triggers
        if r.tier == "A" and r.final_priority >= 70
    ]
    if high_priority_a:
        cohort_patterns.append({
            "pattern_type": "revenue_risk",
            "trigger_type": "HIGH_PRIORITY_TIER_A",
            "affected_clients": high_priority_a,
            "client_count": len(high_priority_a),
            "description": (
                f"{len(high_priority_a)} Tier-A (>$1M AUM) client(s) have priority ≥70 — "
                "high revenue-at-risk. Advisor attention required immediately."
            ),
            "recommended_action": (
                "Schedule Tier-A clients within 48 hours. "
                "Auto-prepare action packages for each high-priority case."
            ),
        })

    return cohort_patterns


def _cohort_action(trigger_type: str, count: int) -> str:
    actions = {
        "RMD_DUE": f"Batch RMD calculations for {count} clients. Send RMD reminder letters.",
        "RMD_APPROACHING": f"Prepare Roth conversion / QCD intro packages for {count} pre-RMD clients.",
        "PORTFOLIO_DRIFT": f"Bulk rebalancing review for {count} clients. Prefer tax-advantaged accounts.",
        "TLH_OPPORTUNITY": f"Coordinate TLH sweep for {count} clients before market recovery erases losses.",
        "ROTH_WINDOW": f"Roth conversion analysis for {count} gap-year clients before SS/RMD begins.",
        "QCD_OPPORTUNITY": f"QCD setup for {count} eligible clients — maximize RMD tax exclusion.",
        "ESTATE_REVIEW_OVERDUE": f"Schedule estate attorney referrals for {count} clients with outdated docs.",
        "MEETING_OVERDUE": f"Block outreach week for {count} overdue clients.",
        "LIFE_EVENT_RECENT": f"Immediate outreach to {count} clients with recent unresolved life events.",
        "BENEFICIARY_REVIEW": f"Send beneficiary review forms to {count} clients.",
        "MARKET_EVENT": f"Market event briefing and portfolio review for {count} affected clients.",
        "APPROACHING_MILESTONE": f"Milestone prep packages for {count} clients approaching key ages.",
    }
    return actions.get(trigger_type, f"Review {trigger_type} for {count} clients.")


def _build_action_items(
    triggers: list[Trigger],
    compounds: list[dict],
    client: dict,
) -> list[dict[str, Any]]:
    """Build a prioritized action item list from detected triggers."""
    items = []
    priority_map = {
        "RMD_DUE": "critical",
        "LIFE_EVENT_RECENT": "critical",
        "PORTFOLIO_DRIFT": "high",
        "TLH_OPPORTUNITY": "high",
        "MARKET_EVENT": "high",
        "RMD_APPROACHING": "medium",
        "ROTH_WINDOW": "medium",
        "QCD_OPPORTUNITY": "medium",
        "ESTATE_REVIEW_OVERDUE": "medium",
        "MEETING_OVERDUE": "medium",
        "BENEFICIARY_REVIEW": "low",
        "APPROACHING_MILESTONE": "low",
    }

    for trigger in triggers:
        items.append({
            "trigger_type": trigger.trigger_type,
            "priority": priority_map.get(trigger.trigger_type, "medium"),
            "description": trigger.description,
            "details": trigger.details,
        })

    for compound in compounds:
        items.append({
            "trigger_type": "COMPOUND",
            "compound_name": compound["name"],
            "priority": "critical",
            "description": compound["description"],
            "urgency_boost": compound["urgency_boost"],
        })

    # Sort: critical > high > medium > low
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda x: order.get(x["priority"], 4))
    return items
