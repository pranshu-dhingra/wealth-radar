"""Unit tests for the trigger detection engine.

Run with: pytest backend/tests/test_trigger_engine.py -v
from the wealth-radar project root.

Covers:
  - Individual trigger detectors (all 12)
  - Compound trigger pattern detection
  - Priority scoring formula with tier multipliers
  - scan_client() end-to-end
  - scan_all_clients() sorting
  - detect_cohort_patterns()
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.tools.trigger_engine import (
    TODAY,
    ClientScanResult,
    Trigger,
    _compute_priority,
    _detect_approaching_milestone,
    _detect_beneficiary_review,
    _detect_compound_triggers,
    _detect_estate_review_overdue,
    _detect_life_event,
    _detect_market_event,
    _detect_meeting_overdue,
    _detect_portfolio_drift,
    _detect_qcd_opportunity,
    _detect_rmd_approaching,
    _detect_rmd_due,
    _detect_roth_window,
    _detect_tlh_opportunity,
    detect_cohort_patterns,
    scan_all_clients,
    scan_client,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _base_client(**overrides) -> dict:
    """Minimal client dict that triggers no alarms by default."""
    base = {
        "id": "TEST001",
        "name": "Test Client",
        "tier": "C",
        "age": 55,
        "date_of_birth": "1970-01-01",
        "occupation": "Engineer",
        "rmd_eligible": False,
        "rmd_taken_this_year": True,
        "rmd_amount_estimated": 0.0,
        "rmd_overdue": False,
        "qcd_eligible": False,
        "qcd_limit_2026": 111_000.0,
        "qcd_amount_gifted_ytd": 0.0,
        "roth_conversion_candidate": False,
        "tax_loss_harvesting_opportunity": False,
        "has_portfolio_drift": False,
        "max_drift_pct": 1.0,
        "portfolio_drift": {},
        "current_allocation": {"US_EQUITY": 60.0, "INTL_EQUITY": 20.0, "US_BOND": 20.0},
        "estate_docs_outdated": False,
        "estate_documents": {},
        "has_recent_life_event": False,
        "life_events": [],
        "accounts": [],
        "last_meeting_date": TODAY.isoformat(),
        "next_scheduled_meeting": None,
        "meeting_frequency": "annual",
    }
    base.update(overrides)
    return base


def _make_trigger(ttype: str, client_id: str = "T1", bu: int = 70, ri: int = 60) -> Trigger:
    return Trigger(trigger_type=ttype, client_id=client_id, base_urgency=bu, revenue_impact=ri)


# ===========================================================================
# 1. Individual detector: RMD_DUE
# ===========================================================================

class TestRmdDue:

    def test_fires_when_rmd_eligible_and_not_taken(self):
        client = _base_client(
            rmd_eligible=True,
            rmd_taken_this_year=False,
            rmd_amount_estimated=25_000.0,
        )
        t = _detect_rmd_due(client)
        assert t is not None
        assert t.trigger_type == "RMD_DUE"
        assert t.base_urgency == 95
        assert "$25,000" in t.description

    def test_no_trigger_when_rmd_taken(self):
        client = _base_client(rmd_eligible=True, rmd_taken_this_year=True)
        assert _detect_rmd_due(client) is None

    def test_no_trigger_when_not_eligible(self):
        client = _base_client(rmd_eligible=False, rmd_taken_this_year=False)
        assert _detect_rmd_due(client) is None


# ===========================================================================
# 2. Individual detector: RMD_APPROACHING
# ===========================================================================

class TestRmdApproaching:

    def test_fires_for_born_1960_turning_75(self):
        # Born 1960, so RMD age = 75. NOW = 2026 → age 65/66. Not approaching within 1yr.
        # To trigger: age 74, born 1952 (RMD age 73 but we need approaching within 1yr)
        client = _base_client(
            age=72,
            date_of_birth="1953-06-15",  # birth_year 1953 → RMD age 73; years_to_rmd = 73-72 = 1
            rmd_eligible=False,
        )
        t = _detect_rmd_approaching(client)
        assert t is not None
        assert t.trigger_type == "RMD_APPROACHING"
        assert t.details["rmd_start_age"] == 73

    def test_fires_for_born_1960_at_age_74(self):
        client = _base_client(
            age=74,
            date_of_birth="1960-01-01",  # birth_year 1960 → RMD age 75; years_to_rmd = 1
            rmd_eligible=False,
        )
        t = _detect_rmd_approaching(client)
        assert t is not None
        assert t.details["rmd_start_age"] == 75

    def test_no_trigger_when_already_rmd_eligible(self):
        client = _base_client(age=75, date_of_birth="1951-01-01", rmd_eligible=True)
        assert _detect_rmd_approaching(client) is None

    def test_no_trigger_when_far_from_rmd_age(self):
        client = _base_client(age=60, date_of_birth="1966-01-01", rmd_eligible=False)
        assert _detect_rmd_approaching(client) is None


# ===========================================================================
# 3. Individual detector: PORTFOLIO_DRIFT
# ===========================================================================

class TestPortfolioDrift:

    def test_fires_when_has_portfolio_drift_flag(self):
        client = _base_client(
            has_portfolio_drift=True,
            max_drift_pct=7.5,
            portfolio_drift={"US_EQUITY": 7.5},
        )
        t = _detect_portfolio_drift(client)
        assert t is not None
        assert t.trigger_type == "PORTFOLIO_DRIFT"
        assert t.details["max_drift_pct"] == 7.5

    def test_fires_when_max_drift_exceeds_threshold(self):
        client = _base_client(
            has_portfolio_drift=False,
            max_drift_pct=6.2,
            portfolio_drift={"INTL_EQUITY": 6.2},
        )
        t = _detect_portfolio_drift(client)
        assert t is not None

    def test_no_trigger_within_threshold(self):
        client = _base_client(has_portfolio_drift=False, max_drift_pct=3.0)
        assert _detect_portfolio_drift(client) is None

    def test_urgency_scaled_with_severity(self):
        client = _base_client(
            has_portfolio_drift=True,
            max_drift_pct=15.0,
            portfolio_drift={"US_EQUITY": 15.0},
        )
        t = _detect_portfolio_drift(client)
        assert t is not None
        assert t.base_urgency > 70  # should be scaled up


# ===========================================================================
# 4. Individual detector: TLH_OPPORTUNITY
# ===========================================================================

class TestTlhOpportunity:

    def test_fires_when_flagged(self):
        client = _base_client(tax_loss_harvesting_opportunity=True)
        t = _detect_tlh_opportunity(client)
        assert t is not None
        assert t.trigger_type == "TLH_OPPORTUNITY"
        assert t.base_urgency == 60

    def test_no_trigger_when_not_flagged(self):
        client = _base_client(tax_loss_harvesting_opportunity=False)
        assert _detect_tlh_opportunity(client) is None


# ===========================================================================
# 5. Individual detector: ROTH_WINDOW
# ===========================================================================

class TestRothWindow:

    def test_fires_for_retired_pre_rmd_candidate(self):
        client = _base_client(
            roth_conversion_candidate=True,
            rmd_eligible=False,
            occupation="Retired",
        )
        t = _detect_roth_window(client)
        assert t is not None
        assert t.trigger_type == "ROTH_WINDOW"

    def test_no_trigger_when_rmd_eligible(self):
        # Once RMD starts, RMD_DUE is more relevant
        client = _base_client(roth_conversion_candidate=True, rmd_eligible=True)
        assert _detect_roth_window(client) is None

    def test_no_trigger_when_not_candidate(self):
        client = _base_client(roth_conversion_candidate=False)
        assert _detect_roth_window(client) is None


# ===========================================================================
# 6. Individual detector: QCD_OPPORTUNITY
# ===========================================================================

class TestQcdOpportunity:

    def test_fires_when_eligible_and_capacity_remains(self):
        client = _base_client(
            qcd_eligible=True,
            rmd_eligible=True,
            qcd_limit_2026=111_000.0,
            qcd_amount_gifted_ytd=10_000.0,
        )
        t = _detect_qcd_opportunity(client)
        assert t is not None
        assert t.trigger_type == "QCD_OPPORTUNITY"
        assert t.details["qcd_remaining"] == pytest.approx(101_000.0)

    def test_no_trigger_when_limit_exhausted(self):
        client = _base_client(
            qcd_eligible=True,
            rmd_eligible=True,
            qcd_limit_2026=111_000.0,
            qcd_amount_gifted_ytd=111_000.0,
        )
        assert _detect_qcd_opportunity(client) is None

    def test_no_trigger_when_not_qcd_eligible(self):
        client = _base_client(qcd_eligible=False, rmd_eligible=True)
        assert _detect_qcd_opportunity(client) is None

    def test_no_trigger_when_not_rmd_eligible(self):
        client = _base_client(qcd_eligible=True, rmd_eligible=False)
        assert _detect_qcd_opportunity(client) is None


# ===========================================================================
# 7. Individual detector: ESTATE_REVIEW_OVERDUE
# ===========================================================================

class TestEstateReviewOverdue:

    def test_fires_when_estate_docs_outdated_flag(self):
        client = _base_client(estate_docs_outdated=True)
        t = _detect_estate_review_overdue(client)
        assert t is not None
        assert t.trigger_type == "ESTATE_REVIEW_OVERDUE"

    def test_fires_when_doc_is_missing(self):
        client = _base_client(
            estate_docs_outdated=False,
            estate_documents={
                "trust": {"status": "missing", "date_executed": None, "attorney": None}
            },
        )
        t = _detect_estate_review_overdue(client)
        assert t is not None
        assert any("MISSING" in issue for issue in t.details["issues"])

    def test_fires_when_doc_older_than_3_years(self):
        old_date = (TODAY - timedelta(days=365 * 4)).isoformat()
        client = _base_client(
            estate_docs_outdated=False,
            estate_documents={
                "will": {"status": "current", "date_executed": old_date, "attorney": "Firm A"}
            },
        )
        t = _detect_estate_review_overdue(client)
        assert t is not None

    def test_no_trigger_for_recent_docs(self):
        recent_date = (TODAY - timedelta(days=365)).isoformat()
        client = _base_client(
            estate_docs_outdated=False,
            estate_documents={
                "will": {"status": "current", "date_executed": recent_date, "attorney": "Firm A"}
            },
        )
        assert _detect_estate_review_overdue(client) is None


# ===========================================================================
# 8. Individual detector: MEETING_OVERDUE
# ===========================================================================

class TestMeetingOverdue:

    def test_fires_for_tier_a_overdue_client(self):
        # Tier A: every 91 days. Last meeting 120 days ago.
        last = (TODAY - timedelta(days=120)).isoformat()
        client = _base_client(tier="A", last_meeting_date=last)
        t = _detect_meeting_overdue(client)
        assert t is not None
        assert t.trigger_type == "MEETING_OVERDUE"
        assert t.details["overdue_by_days"] == 120 - 91

    def test_no_trigger_when_recent_enough(self):
        last = (TODAY - timedelta(days=30)).isoformat()
        client = _base_client(tier="A", last_meeting_date=last)
        assert _detect_meeting_overdue(client) is None

    def test_fires_for_tier_d_overdue(self):
        # Tier D: every 365 days. Last meeting 400 days ago.
        last = (TODAY - timedelta(days=400)).isoformat()
        client = _base_client(tier="D", last_meeting_date=last)
        t = _detect_meeting_overdue(client)
        assert t is not None
        assert t.details["overdue_by_days"] == 35

    def test_fires_when_no_meeting_recorded(self):
        client = _base_client(last_meeting_date=None)
        t = _detect_meeting_overdue(client)
        assert t is not None


# ===========================================================================
# 9. Individual detector: LIFE_EVENT_RECENT
# ===========================================================================

class TestLifeEventRecent:

    def test_fires_when_has_recent_life_event_flag_with_event(self):
        recent_date = (TODAY - timedelta(days=30)).isoformat()
        client = _base_client(
            has_recent_life_event=True,
            life_events=[
                {
                    "type": "divorce",
                    "date": recent_date,
                    "description": "Divorce finalized.",
                    "resolved": False,
                }
            ],
        )
        t = _detect_life_event(client)
        assert t is not None
        assert t.trigger_type == "LIFE_EVENT_RECENT"

    def test_no_trigger_for_resolved_events(self):
        recent_date = (TODAY - timedelta(days=30)).isoformat()
        client = _base_client(
            has_recent_life_event=False,
            life_events=[
                {"type": "job_change", "date": recent_date, "resolved": True}
            ],
        )
        assert _detect_life_event(client) is None

    def test_no_trigger_for_old_events(self):
        old_date = (TODAY - timedelta(days=120)).isoformat()
        client = _base_client(
            has_recent_life_event=False,
            life_events=[
                {"type": "marriage", "date": old_date, "resolved": False}
            ],
        )
        assert _detect_life_event(client) is None


# ===========================================================================
# 10. Individual detector: BENEFICIARY_REVIEW
# ===========================================================================

class TestBeneficiaryReview:

    def test_fires_for_account_with_no_beneficiary(self):
        client = _base_client(
            accounts=[
                {
                    "account_id": "ACC001",
                    "account_type": "Traditional IRA",
                    "beneficiary_designated": False,
                    "beneficiary_last_reviewed": None,
                }
            ]
        )
        t = _detect_beneficiary_review(client)
        assert t is not None
        assert t.trigger_type == "BENEFICIARY_REVIEW"
        assert "no beneficiary" in t.description

    def test_fires_for_stale_beneficiary_review(self):
        old_review = (TODAY - timedelta(days=365 * 3)).isoformat()
        client = _base_client(
            accounts=[
                {
                    "account_id": "ACC002",
                    "account_type": "Roth IRA",
                    "beneficiary_designated": True,
                    "beneficiary_last_reviewed": old_review,
                }
            ]
        )
        t = _detect_beneficiary_review(client)
        assert t is not None

    def test_no_trigger_for_recent_review(self):
        recent = (TODAY - timedelta(days=365)).isoformat()
        client = _base_client(
            accounts=[
                {
                    "account_id": "ACC003",
                    "account_type": "Roth IRA",
                    "beneficiary_designated": True,
                    "beneficiary_last_reviewed": recent,
                }
            ]
        )
        assert _detect_beneficiary_review(client) is None


# ===========================================================================
# 11. Individual detector: MARKET_EVENT
# ===========================================================================

class TestMarketEvent:

    def test_fires_when_client_holds_impacted_asset_class(self):
        client = _base_client(
            current_allocation={"US_EQUITY": 60.0, "US_BOND": 40.0}
        )
        events = [
            {
                "name": "Tech Selloff",
                "type": "market_decline",
                "impacted_asset_classes": ["US_EQUITY"],
            }
        ]
        t = _detect_market_event(client, events)
        assert t is not None
        assert t.trigger_type == "MARKET_EVENT"

    def test_no_trigger_when_no_overlap(self):
        client = _base_client(
            current_allocation={"US_EQUITY": 60.0, "US_BOND": 40.0}
        )
        events = [{"name": "Crypto Crash", "impacted_asset_classes": ["COMMODITIES"]}]
        # COMMODITIES is 0% in current_allocation → no trigger
        t = _detect_market_event(client, events)
        assert t is None

    def test_no_trigger_with_no_events(self):
        client = _base_client()
        assert _detect_market_event(client, []) is None


# ===========================================================================
# 12. Individual detector: APPROACHING_MILESTONE
# ===========================================================================

class TestApproachingMilestone:

    def test_fires_approaching_age_73(self):
        # Born 1953-06-15, TODAY = 2026-03-08 → age ≈ 72.7 → age 73 is 0.3 yrs away
        client = _base_client(date_of_birth="1953-06-15", age=72)
        t = _detect_approaching_milestone(client)
        assert t is not None
        assert t.trigger_type == "APPROACHING_MILESTONE"
        assert any(m["age"] == 73 for m in t.details["upcoming_milestones"])

    def test_fires_approaching_age_70_5(self):
        # Born 1955-08-01 → age in 2026-03 ≈ 70.6. Already past 70.5? Let's use 1956-01-01
        # TODAY 2026-03-08, DOB 1956-04-01 → age ≈ 69.9 → 70.5 is 0.6 yrs away
        client = _base_client(date_of_birth="1956-04-01", age=69)
        t = _detect_approaching_milestone(client)
        assert t is not None
        milestones = [m["age"] for m in t.details["upcoming_milestones"]]
        assert 70.5 in milestones

    def test_no_trigger_when_milestones_far(self):
        # Age 40 → nearest milestone is 59.5 (19.5 years away)
        client = _base_client(date_of_birth="1986-01-01", age=40)
        assert _detect_approaching_milestone(client) is None


# ===========================================================================
# 13. Priority scoring formula
# ===========================================================================

class TestPriorityScoring:

    def test_single_trigger_no_compound_bonus(self):
        triggers = [_make_trigger("RMD_DUE", bu=95, ri=80)]
        # priority = 95*0.6 + 80*0.2 + 0*0.2 = 57 + 16 + 0 = 73
        # Tier C multiplier = 1.0
        result = _compute_priority(triggers, "C")
        assert result == pytest.approx(73.0, abs=0.1)

    def test_compound_bonus_applied_for_two_triggers(self):
        triggers = [
            _make_trigger("RMD_DUE", bu=95, ri=80),
            _make_trigger("QCD_OPPORTUNITY", bu=50, ri=60),
        ]
        # compound_bonus = 30 * (2-1) = 30
        # Anchored on RMD_DUE (highest urgency): 95*0.6 + 80*0.2 + 30*0.2 = 57+16+6 = 79
        # Tier C multiplier = 1.0
        result = _compute_priority(triggers, "C")
        assert result == pytest.approx(79.0, abs=0.1)

    def test_tier_a_multiplier_amplifies_priority(self):
        # Use a moderate-urgency trigger so Tier A doesn't hit the 100 cap
        # MEETING_OVERDUE: bu=45, ri=50 → raw = 45*0.6 + 50*0.2 = 27+10 = 37
        # Tier C: 37 * 1.0 = 37; Tier A: 37 * 1.5 = 55.5 (well below 100)
        triggers = [_make_trigger("MEETING_OVERDUE", bu=45, ri=50)]
        c_priority = _compute_priority(triggers, "C")
        a_priority = _compute_priority(triggers, "A")
        assert a_priority == pytest.approx(c_priority * 1.5, abs=0.1)

    def test_tier_d_multiplier_reduces_priority(self):
        triggers = [_make_trigger("RMD_DUE", bu=95, ri=80)]
        c_priority = _compute_priority(triggers, "C")
        d_priority = _compute_priority(triggers, "D")
        assert d_priority == pytest.approx(c_priority * 0.8, abs=0.1)

    def test_priority_capped_at_100(self):
        # Three high-urgency triggers for Tier A should cap at 100
        triggers = [
            _make_trigger("RMD_DUE", bu=95, ri=80),
            _make_trigger("LIFE_EVENT_RECENT", bu=75, ri=65),
            _make_trigger("PORTFOLIO_DRIFT", bu=70, ri=65),
        ]
        result = _compute_priority(triggers, "A")
        assert result <= 100.0

    def test_no_triggers_returns_zero(self):
        assert _compute_priority([], "A") == 0.0


# ===========================================================================
# 14. Compound trigger detection
# ===========================================================================

class TestCompoundTriggers:

    def test_detects_rmd_plus_qcd_combo(self):
        triggers = [
            _make_trigger("RMD_DUE"),
            _make_trigger("QCD_OPPORTUNITY"),
        ]
        compounds = _detect_compound_triggers(triggers)
        names = [c["name"] for c in compounds]
        assert "RMD + QCD Combo" in names

    def test_detects_life_event_plus_estate(self):
        triggers = [
            _make_trigger("LIFE_EVENT_RECENT"),
            _make_trigger("ESTATE_REVIEW_OVERDUE"),
        ]
        compounds = _detect_compound_triggers(triggers)
        names = [c["name"] for c in compounds]
        assert "Life Event + Estate Review" in names

    def test_detects_triple_retirement_pattern(self):
        triggers = [
            _make_trigger("RMD_DUE"),
            _make_trigger("QCD_OPPORTUNITY"),
            _make_trigger("TLH_OPPORTUNITY"),
        ]
        compounds = _detect_compound_triggers(triggers)
        names = [c["name"] for c in compounds]
        assert "Full Retirement Transition" in names
        # Should also detect the pair patterns
        assert "RMD + QCD Combo" in names

    def test_no_compounds_for_single_trigger(self):
        triggers = [_make_trigger("RMD_DUE")]
        assert _detect_compound_triggers(triggers) == []

    def test_no_compounds_for_unrelated_pair(self):
        triggers = [
            _make_trigger("MEETING_OVERDUE"),
            _make_trigger("APPROACHING_MILESTONE"),
        ]
        assert _detect_compound_triggers(triggers) == []

    def test_market_event_plus_tlh(self):
        triggers = [
            _make_trigger("MARKET_EVENT"),
            _make_trigger("TLH_OPPORTUNITY"),
        ]
        compounds = _detect_compound_triggers(triggers)
        names = [c["name"] for c in compounds]
        assert "Market Event + TLH" in names


# ===========================================================================
# 15. scan_client() end-to-end
# ===========================================================================

class TestScanClient:

    def test_scan_returns_client_result(self):
        client = _base_client()
        result = scan_client(client)
        assert isinstance(result, ClientScanResult)
        assert result.client_id == "TEST001"

    def test_scan_detects_rmd_due(self):
        client = _base_client(
            rmd_eligible=True,
            rmd_taken_this_year=False,
            rmd_amount_estimated=20_000.0,
        )
        result = scan_client(client)
        types = [t.trigger_type for t in result.triggers]
        assert "RMD_DUE" in types

    def test_compound_scenario_rmd_qcd_tlh(self):
        """Tier A client with RMD due + QCD eligible + TLH opportunity → compound triggers."""
        client = _base_client(
            id="COMPOUND001",
            tier="A",
            age=75,
            rmd_eligible=True,
            rmd_taken_this_year=False,
            rmd_amount_estimated=35_000.0,
            qcd_eligible=True,
            qcd_amount_gifted_ytd=0.0,
            tax_loss_harvesting_opportunity=True,
        )
        result = scan_client(client)
        types = [t.trigger_type for t in result.triggers]
        assert "RMD_DUE" in types
        assert "QCD_OPPORTUNITY" in types
        assert "TLH_OPPORTUNITY" in types

        compound_names = [c["name"] for c in result.compound_triggers]
        assert "Full Retirement Transition" in compound_names
        assert result.final_priority >= 80.0  # Tier A + compound should be very high

    def test_compound_scenario_life_event_estate_beneficiary(self):
        """Client with recent life event + outdated estate + stale beneficiary."""
        recent_date = (TODAY - timedelta(days=20)).isoformat()
        old_beneficiary = (TODAY - timedelta(days=365 * 3)).isoformat()
        client = _base_client(
            id="COMPOUND002",
            tier="B",
            has_recent_life_event=True,
            life_events=[
                {"type": "divorce", "date": recent_date, "resolved": False}
            ],
            estate_docs_outdated=True,
            accounts=[
                {
                    "account_id": "ACC-B1",
                    "beneficiary_designated": True,
                    "beneficiary_last_reviewed": old_beneficiary,
                }
            ],
        )
        result = scan_client(client)
        types = [t.trigger_type for t in result.triggers]
        assert "LIFE_EVENT_RECENT" in types
        assert "ESTATE_REVIEW_OVERDUE" in types
        assert "BENEFICIARY_REVIEW" in types

        compound_names = [c["name"] for c in result.compound_triggers]
        assert "Life Event + Estate Review" in compound_names
        assert "Life Event + Beneficiary" in compound_names

    def test_client_with_no_triggers_has_zero_priority(self):
        client = _base_client()
        result = scan_client(client)
        assert result.final_priority == 0.0
        assert result.triggers == []

    def test_action_items_sorted_critical_first(self):
        client = _base_client(
            rmd_eligible=True,
            rmd_taken_this_year=False,
            rmd_amount_estimated=30_000.0,
            estate_docs_outdated=True,
        )
        result = scan_client(client)
        if result.action_items:
            priorities = [item["priority"] for item in result.action_items]
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            ordered = [order[p] for p in priorities]
            assert ordered == sorted(ordered)


# ===========================================================================
# 16. scan_all_clients() — sorting and filtering
# ===========================================================================

class TestScanAllClients:

    def _make_clients(self) -> list[dict]:
        return [
            # High-priority Tier A: RMD + QCD
            _base_client(
                id="HIGH_A",
                name="High Priority A",
                tier="A",
                rmd_eligible=True,
                rmd_taken_this_year=False,
                rmd_amount_estimated=40_000.0,
                qcd_eligible=True,
                qcd_amount_gifted_ytd=0.0,
            ),
            # Low-priority Tier D: just meeting overdue
            _base_client(
                id="LOW_D",
                name="Low Priority D",
                tier="D",
                last_meeting_date=(TODAY - timedelta(days=400)).isoformat(),
            ),
            # No triggers
            _base_client(id="CLEAN", name="Clean Client", tier="C"),
        ]

    def test_returns_only_clients_with_triggers(self):
        results = scan_all_clients(self._make_clients())
        ids = [r.client_id for r in results]
        assert "CLEAN" not in ids
        assert "HIGH_A" in ids
        assert "LOW_D" in ids

    def test_sorted_by_priority_descending(self):
        results = scan_all_clients(self._make_clients())
        priorities = [r.final_priority for r in results]
        assert priorities == sorted(priorities, reverse=True)

    def test_tier_a_outranks_tier_d(self):
        results = scan_all_clients(self._make_clients())
        high_a = next(r for r in results if r.client_id == "HIGH_A")
        low_d = next(r for r in results if r.client_id == "LOW_D")
        assert high_a.final_priority > low_d.final_priority


# ===========================================================================
# 17. detect_cohort_patterns()
# ===========================================================================

class TestDetectCohortPatterns:

    def _make_scan_results(self) -> list[ClientScanResult]:
        clients = [
            _base_client(
                id=f"RMD{i:02d}",
                name=f"RMD Client {i}",
                tier="B",
                rmd_eligible=True,
                rmd_taken_this_year=False,
                rmd_amount_estimated=25_000.0,
            )
            for i in range(3)
        ]
        return scan_all_clients(clients)

    def test_detects_rmd_cohort(self):
        results = self._make_scan_results()
        patterns = detect_cohort_patterns(results)
        rmd_patterns = [p for p in patterns if p.get("trigger_type") == "RMD_DUE"]
        assert len(rmd_patterns) >= 1
        assert rmd_patterns[0]["client_count"] == 3

    def test_detects_tier_a_revenue_risk(self):
        # Create Tier A clients with high priority triggers
        clients = [
            _base_client(
                id=f"A{i:02d}",
                name=f"Tier A Client {i}",
                tier="A",
                rmd_eligible=True,
                rmd_taken_this_year=False,
                rmd_amount_estimated=50_000.0,
                qcd_eligible=True,
                qcd_amount_gifted_ytd=0.0,
            )
            for i in range(2)
        ]
        results = scan_all_clients(clients)
        patterns = detect_cohort_patterns(results)
        revenue_risk = [p for p in patterns if p.get("trigger_type") == "HIGH_PRIORITY_TIER_A"]
        assert len(revenue_risk) == 1
        assert revenue_risk[0]["client_count"] == 2

    def test_returns_list(self):
        results = self._make_scan_results()
        patterns = detect_cohort_patterns(results)
        assert isinstance(patterns, list)

    def test_compound_cohort_detected(self):
        clients = [
            _base_client(
                id=f"COMP{i}",
                name=f"Compound {i}",
                tier="A",
                rmd_eligible=True,
                rmd_taken_this_year=False,
                rmd_amount_estimated=30_000.0,
                qcd_eligible=True,
                qcd_amount_gifted_ytd=0.0,
            )
            for i in range(2)
        ]
        results = scan_all_clients(clients)
        patterns = detect_cohort_patterns(results)
        compound_cohorts = [p for p in patterns if p.get("pattern_type") == "compound_cohort"]
        assert len(compound_cohorts) >= 1
