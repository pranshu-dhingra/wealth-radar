"""Unit tests for financial calculation tools.

Run with: pytest backend/tests/test_tools.py -v
from the wealth-radar project root.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Allow importing backend.app.tools from the project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.tools.rmd_calculator import (
    UNIFORM_LIFETIME_TABLE,
    _rmd_start_age,
    calculate_rmd,
)
from backend.app.tools.drift_calculator import (
    DRIFT_THRESHOLD_PCT,
    calculate_portfolio_drift,
)
from backend.app.tools.tlh_scanner import scan_tax_loss_harvesting
from backend.app.tools.roth_analyzer import analyze_roth_conversion
from backend.app.tools.qcd_calculator import calculate_qcd_opportunity


# ===========================================================================
# Helpers
# ===========================================================================

def _call(tool_fn, payload: dict) -> dict:
    """Call a @tool function with a dict payload and return parsed JSON."""
    result = tool_fn(json.dumps(payload))
    # Strands @tool may return a ToolResult object or a plain string
    if hasattr(result, "content"):
        raw = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
    else:
        raw = str(result)
    return json.loads(raw)


# ===========================================================================
# rmd_calculator tests
# ===========================================================================

class TestRmdCalculator:

    def test_secure2_age73_threshold_born_1952(self):
        """Client born 1952 has RMD threshold of 73 per SECURE Act 2.0."""
        assert _rmd_start_age(1952) == 73

    def test_secure2_age75_threshold_born_1960(self):
        """Client born 1960 has RMD threshold of 75 per SECURE Act 2.0."""
        assert _rmd_start_age(1960) == 75

    def test_pre_secure2_threshold_born_1949(self):
        """Client born 1949 has RMD threshold of 72 (pre-SECURE 2.0 cohort)."""
        assert _rmd_start_age(1949) == 72

    def test_ult_covers_ages_72_to_120(self):
        """Uniform Lifetime Table III must cover all ages from 72 to 120."""
        for age in range(72, 121):
            assert age in UNIFORM_LIFETIME_TABLE, f"ULT missing age {age}"

    def test_ult_period_decreases_with_age(self):
        """Distribution periods must decrease monotonically as age increases."""
        ages = sorted(UNIFORM_LIFETIME_TABLE.keys())
        for i in range(len(ages) - 1):
            assert UNIFORM_LIFETIME_TABLE[ages[i]] > UNIFORM_LIFETIME_TABLE[ages[i + 1]], (
                f"ULT period should decrease: age {ages[i]} -> {ages[i+1]}"
            )

    def test_not_eligible_below_threshold(self):
        """Client age 70 (born 1956, threshold 73) should not be eligible."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-001",
            "birth_year": 1956,
            "age": 70,
            "traditional_ira_balance": 500_000.0,
        })
        assert result["eligible"] is False
        assert result["rmd_required"] == 0.0
        assert result["rmd_age_threshold"] == 73

    def test_rmd_calculation_age_73(self):
        """RMD for $500,000 IRA at age 73 should use period 26.5."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-002",
            "birth_year": 1952,
            "age": 73,
            "traditional_ira_balance": 500_000.0,
            "rmd_taken_ytd": 0.0,
        })
        assert result["eligible"] is True
        assert result["distribution_period"] == 26.5
        expected = round(500_000.0 / 26.5, 2)
        assert result["rmd_required"] == pytest.approx(expected, abs=0.01)
        assert result["rmd_remaining"] == pytest.approx(expected, abs=0.01)

    def test_partial_rmd_already_taken(self):
        """If partial RMD already taken, remaining should reflect that."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-003",
            "birth_year": 1952,
            "age": 73,
            "traditional_ira_balance": 500_000.0,
            "rmd_taken_ytd": 10_000.0,
        })
        expected_total = round(500_000.0 / 26.5, 2)
        expected_remaining = round(max(0.0, expected_total - 10_000.0), 2)
        assert result["rmd_remaining"] == pytest.approx(expected_remaining, abs=0.01)

    def test_rmd_fully_satisfied(self):
        """If RMD already taken in full, remaining should be 0 and no penalty."""
        rmd_total = round(500_000.0 / 26.5, 2)
        result = _call(calculate_rmd, {
            "client_id": "TEST-004",
            "birth_year": 1952,
            "age": 73,
            "traditional_ira_balance": 500_000.0,
            "rmd_taken_ytd": rmd_total + 100,   # taken more than required
        })
        assert result["rmd_remaining"] == 0.0
        assert result["penalty"] is None

    def test_penalty_25pct_on_shortfall(self):
        """Shortfall should incur 25% excise tax per SECURE 2.0 Sec. 302."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-005",
            "birth_year": 1952,
            "age": 73,
            "traditional_ira_balance": 500_000.0,
            "rmd_taken_ytd": 0.0,
            "corrected_timely": False,
        })
        assert result["penalty"] is not None
        assert result["penalty"]["excise_tax_rate"] == "25%"
        shortfall = result["rmd_remaining"]
        assert result["penalty"]["excise_tax_amount"] == pytest.approx(shortfall * 0.25, abs=0.01)

    def test_penalty_10pct_when_corrected_timely(self):
        """Corrected-timely shortfall should use 10% excise tax."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-006",
            "birth_year": 1952,
            "age": 73,
            "traditional_ira_balance": 500_000.0,
            "rmd_taken_ytd": 0.0,
            "corrected_timely": True,
        })
        assert result["penalty"]["excise_tax_rate"] == "10%"

    def test_joint_life_table_for_younger_spouse(self):
        """Spouse >10 years younger should trigger Joint Life Table II (longer period)."""
        result_ult = _call(calculate_rmd, {
            "client_id": "TEST-007",
            "birth_year": 1951,
            "age": 74,
            "traditional_ira_balance": 800_000.0,
        })
        result_jlt = _call(calculate_rmd, {
            "client_id": "TEST-007",
            "birth_year": 1951,
            "age": 74,
            "traditional_ira_balance": 800_000.0,
            "spouse_age": 60,  # 14 years younger — triggers Joint Life Table
        })
        assert "Joint Life" in result_jlt["table_used"]
        # Joint Life period is longer => lower RMD
        assert result_jlt["distribution_period"] > result_ult["distribution_period"]
        assert result_jlt["rmd_required"] < result_ult["rmd_required"]

    def test_age_75_born_1960(self):
        """Client born 1960 needs age 75 for first RMD."""
        result = _call(calculate_rmd, {
            "client_id": "TEST-008",
            "birth_year": 1960,
            "age": 74,
            "traditional_ira_balance": 300_000.0,
        })
        assert result["eligible"] is False
        assert result["rmd_age_threshold"] == 75


# ===========================================================================
# drift_calculator tests
# ===========================================================================

def _make_holdings(class_pcts: dict, total: float = 1_000_000.0) -> list[dict]:
    """Build a holdings list from asset-class percentages."""
    holdings = []
    for ac, pct in class_pcts.items():
        holdings.append({
            "ticker": f"ETF_{ac[:3]}",
            "asset_class": ac,
            "current_value": total * pct / 100,
            "unrealized_gain_loss": 5_000.0,
            "holding_period_days": 400,
            "account_type": "taxable",
        })
    return holdings


class TestDriftCalculator:

    _TARGET = {
        "US_EQUITY": 60.0,
        "INTL_EQUITY": 15.0,
        "US_BOND": 15.0,
        "INTL_BOND": 5.0,
        "REAL_ESTATE": 3.0,
        "COMMODITIES": 2.0,
    }

    def test_no_drift_when_on_target(self):
        """Portfolio exactly matching target should have no drift and no rebalancing needed."""
        holdings = _make_holdings(self._TARGET)
        raw = calculate_portfolio_drift(
            json.dumps(holdings),
            json.dumps(self._TARGET),
        )
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert result["rebalancing_needed"] is False
        assert result["max_drift_pct"] == pytest.approx(0.0, abs=0.01)
        assert len(result["suggested_trades"]) == 0

    def test_drift_flag_over_threshold(self):
        """US Equity 8% overweight should trigger rebalancing flag."""
        drifted = dict(self._TARGET)
        drifted["US_EQUITY"] = 68.0       # +8% drift
        drifted["INTL_EQUITY"] = 7.0      # -8% drift (to keep total = 100)
        holdings = _make_holdings(drifted)
        raw = calculate_portfolio_drift(
            json.dumps(holdings),
            json.dumps(self._TARGET),
        )
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert result["rebalancing_needed"] is True
        rebalance_classes = [d["asset_class"] for d in result["drifts"] if d["action_required"]]
        assert "US_EQUITY" in rebalance_classes
        assert "INTL_EQUITY" in rebalance_classes

    def test_trade_suggestions_correct_direction(self):
        """Overweight asset should generate SELL; underweight should generate BUY."""
        drifted = dict(self._TARGET)
        drifted["US_EQUITY"] = 68.0
        drifted["INTL_EQUITY"] = 7.0
        holdings = _make_holdings(drifted)
        raw = calculate_portfolio_drift(
            json.dumps(holdings),
            json.dumps(self._TARGET),
        )
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        actions = {t["asset_class"]: t["action"] for t in result["suggested_trades"]}
        assert actions.get("US_EQUITY") == "SELL"
        assert actions.get("INTL_EQUITY") == "BUY"

    def test_total_value_aggregation(self):
        """Total portfolio value should equal sum of all holding values."""
        holdings = _make_holdings(self._TARGET, total=750_000.0)
        raw = calculate_portfolio_drift(
            json.dumps(holdings),
            json.dumps(self._TARGET),
        )
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert result["total_portfolio_value"] == pytest.approx(750_000.0, rel=1e-4)

    def test_short_term_gain_tax_note_generated(self):
        """Short-term gain position in taxable account should generate a tax impact note."""
        holdings = [
            {
                "ticker": "VTI",
                "asset_class": "US_EQUITY",
                "current_value": 600_000.0,
                "unrealized_gain_loss": 50_000.0,
                "holding_period_days": 180,       # short-term
                "account_type": "taxable",
            },
            {
                "ticker": "BND",
                "asset_class": "US_BOND",
                "current_value": 400_000.0,
                "unrealized_gain_loss": 1_000.0,
                "holding_period_days": 400,
                "account_type": "taxable",
            },
        ]
        target = {"US_EQUITY": 60.0, "US_BOND": 40.0, "INTL_EQUITY": 0.0,
                  "INTL_BOND": 0.0, "REAL_ESTATE": 0.0, "COMMODITIES": 0.0}
        raw = calculate_portfolio_drift(json.dumps(holdings), json.dumps(target))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        tax_notes = result["tax_impact_notes"]
        vti_note = next((n for n in tax_notes if n["ticker"] == "VTI"), None)
        assert vti_note is not None
        assert "SHORT-TERM" in vti_note["tax_note"]


# ===========================================================================
# tlh_scanner tests
# ===========================================================================

class TestTlhScanner:

    def _holdings_payload(self, holdings, bracket=24.0, client_id="TEST-TLH"):
        return json.dumps({
            "client_id": client_id,
            "tax_bracket_pct": bracket,
            "holdings": holdings,
        })

    def test_ira_holdings_excluded(self):
        """IRA and 401k holdings must never be flagged for TLH."""
        holdings = [
            {
                "ticker": "BND",
                "account_type": "traditional ira",
                "unrealized_gain_loss": -5_000.0,
                "current_value": 50_000.0,
                "holding_period_days": 400,
            },
            {
                "ticker": "VTI",
                "account_type": "401k",
                "unrealized_gain_loss": -8_000.0,
                "current_value": 80_000.0,
                "holding_period_days": 400,
            },
        ]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert len(result["opportunities"]) == 0
        assert result["total_harvestable_loss"] == 0.0
        # scanned count should be 0 (neither is taxable)
        assert result["account_scanned_count"] == 0

    def test_loss_below_threshold_not_flagged(self):
        """Loss under $1,000 in taxable account should not be flagged."""
        holdings = [{
            "ticker": "VTI",
            "account_type": "taxable",
            "unrealized_gain_loss": -800.0,
            "current_value": 10_000.0,
            "holding_period_days": 400,
        }]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert len(result["opportunities"]) == 0

    def test_opportunity_detected_in_taxable(self):
        """Loss >$1,000 in taxable account should be flagged with replacement suggestion."""
        holdings = [{
            "ticker": "IEMG",
            "account_type": "taxable",
            "unrealized_gain_loss": -8_200.0,
            "current_value": 40_000.0,
            "holding_period_days": 200,
        }]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings, bracket=32.0))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert len(result["opportunities"]) == 1
        opp = result["opportunities"][0]
        assert opp["ticker"] == "IEMG"
        assert opp["unrealized_loss"] == pytest.approx(8_200.0, abs=0.01)
        assert opp["replacement_ticker"] == "VWO"     # per REPLACEMENT_MAP
        assert opp["is_short_term"] is True           # 200 days < 365

    def test_tax_savings_calculation(self):
        """Tax savings should equal loss * marginal bracket rate."""
        holdings = [{
            "ticker": "BND",
            "account_type": "individual brokerage",
            "unrealized_gain_loss": -4_100.0,
            "current_value": 30_000.0,
            "holding_period_days": 400,
        }]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings, bracket=24.0))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        opp = result["opportunities"][0]
        expected_st_savings = round(4_100.0 * 0.24, 2)
        assert opp["tax_savings"]["st_loss_tax_savings"] == pytest.approx(expected_st_savings, abs=0.01)

    def test_wash_sale_flag_generates_warning(self):
        """Holding with wash_sale_flag=True should generate a wash-sale warning."""
        holdings = [{
            "ticker": "QQQ",
            "account_type": "taxable",
            "unrealized_gain_loss": -6_100.0,
            "current_value": 50_000.0,
            "holding_period_days": 400,
            "wash_sale_flag": True,
        }]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        assert len(result["warnings"]) == 1
        assert "WASH SALE" in result["warnings"][0]["warning"]
        # Should still appear as an opportunity, just flagged
        assert len(result["opportunities"]) == 1
        assert result["opportunities"][0]["wash_sale_risk"] is True

    def test_multiple_opportunities_sorted_by_loss(self):
        """Multiple opportunities should be sorted largest loss first."""
        holdings = [
            {"ticker": "VTI",  "account_type": "taxable", "unrealized_gain_loss": -2_000.0,
             "current_value": 20_000.0, "holding_period_days": 400},
            {"ticker": "IEMG", "account_type": "taxable", "unrealized_gain_loss": -8_200.0,
             "current_value": 40_000.0, "holding_period_days": 200},
            {"ticker": "BND",  "account_type": "taxable", "unrealized_gain_loss": -4_100.0,
             "current_value": 30_000.0, "holding_period_days": 400},
        ]
        raw = scan_tax_loss_harvesting(self._holdings_payload(holdings))
        if hasattr(raw, "content"):
            raw = raw.content[0].text
        result = json.loads(str(raw))

        losses = [o["unrealized_loss"] for o in result["opportunities"]]
        assert losses == sorted(losses, reverse=True)
        assert result["total_harvestable_loss"] == pytest.approx(8_200 + 4_100 + 2_000, abs=0.01)


# ===========================================================================
# roth_analyzer tests
# ===========================================================================

class TestRothAnalyzer:

    def test_optimal_conversion_fills_bracket(self):
        """Conversion amount should not exceed current bracket room."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-001",
            "age": 62,
            "filing_status": "married",
            "current_taxable_income": 150_000.0,   # In 22% bracket
            "traditional_ira_balance": 800_000.0,
        })
        # 22% bracket ceiling for MFJ 2026 ~ $201,050; room = 201050 - 150000 = 51050
        assert result["optimal_conversion_amount"] <= result["bracket_room"] + 0.01
        assert result["optimal_conversion_amount"] > 0

    def test_marginal_rate_22pct(self):
        """Income $150K MFJ should be in 22% bracket."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-002",
            "age": 60,
            "filing_status": "married",
            "current_taxable_income": 150_000.0,
            "traditional_ira_balance": 500_000.0,
        })
        assert result["current_marginal_rate"] == pytest.approx(0.22, abs=0.001)

    def test_pro_rata_warning_when_basis_exists(self):
        """Client with nondeductible IRA basis should receive pro-rata warning."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-003",
            "age": 58,
            "filing_status": "single",
            "current_taxable_income": 90_000.0,
            "traditional_ira_balance": 400_000.0,
            "nondeductible_ira_basis": 50_000.0,
        })
        assert result["pro_rata_warning"] is not None
        assert result["pro_rata_warning"]["taxable_fraction"] == pytest.approx(
            (400_000 - 50_000) / 400_000, abs=0.001
        )

    def test_no_pro_rata_warning_without_basis(self):
        """Client with no nondeductible basis should have no pro-rata warning."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-004",
            "age": 58,
            "filing_status": "single",
            "current_taxable_income": 90_000.0,
            "traditional_ira_balance": 400_000.0,
            "nondeductible_ira_basis": 0.0,
        })
        assert result["pro_rata_warning"] is None

    def test_irmaa_risk_detected_near_threshold(self):
        """Conversion that crosses an IRMAA tier should flag irmaa_risk=True and cap the amount.

        At income $220K (24% bracket, Tier 1 IRMAA), bracket room is ~$163,900.
        Full conversion MAGI = $383,900 → crosses Tier 2 ($258K) and Tier 3 ($322K).
        The tool should detect this risk and cap the conversion below the next IRMAA threshold.
        """
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-005",
            "age": 68,
            "filing_status": "married",
            "current_taxable_income": 220_000.0,   # In 24% bracket; already Tier 1 IRMAA
            "traditional_ira_balance": 500_000.0,   # Full bracket-fill => post-MAGI $383,900
        })
        # Post-conversion MAGI $383,900 crosses from Tier 1 to Tier 3 IRMAA
        assert result["irmaa_risk"] is True
        # Optimal conversion should be capped below the next IRMAA threshold ($258K)
        assert result["optimal_conversion_amount"] < 163_900.0

    def test_rmd_reduction_estimate_positive(self):
        """RMD reduction estimate should be a positive number for an RMD-eligible client."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-006",
            "age": 74,
            "filing_status": "married",
            "current_taxable_income": 120_000.0,
            "traditional_ira_balance": 1_200_000.0,
            "rmd_eligible": True,
            "rmd_age": 73,
            "years_to_rmd": 0,
        })
        assert result["rmd_reduction_estimate"] > 0

    def test_high_income_in_37pct_bracket(self):
        """Very high income should be in 37% bracket."""
        result = _call(analyze_roth_conversion, {
            "client_id": "TEST-ROTH-007",
            "age": 55,
            "filing_status": "married",
            "current_taxable_income": 800_000.0,
            "traditional_ira_balance": 2_000_000.0,
        })
        assert result["current_marginal_rate"] == pytest.approx(0.37, abs=0.001)


# ===========================================================================
# qcd_calculator tests
# ===========================================================================

class TestQcdCalculator:

    def _base(self, **kwargs):
        defaults = {
            "client_id": "TEST-QCD",
            "birth_year": 1952,
            "birth_month": 6,
            "birth_day": 15,
            "age": 73,
            "traditional_ira_balance": 800_000.0,
            "rmd_amount": 30_000.0,
            "qcd_taken_ytd": 0.0,
            "charitable_intent": 20_000.0,
            "filing_status": "married",
            "itemized_deductions": 15_000.0,
        }
        defaults.update(kwargs)
        return defaults

    def test_eligible_at_70_half(self):
        """Client clearly past 70½ should be eligible."""
        result = _call(calculate_qcd_opportunity, self._base())
        assert result["eligible"] is True

    def test_not_eligible_before_70_half(self):
        """Client age 69 (born 1956) should not be eligible."""
        result = _call(calculate_qcd_opportunity, self._base(
            birth_year=1956, birth_month=9, birth_day=1, age=69,
        ))
        assert result["eligible"] is False

    def test_qcd_limit_2026(self):
        """QCD annual limit for 2026 should be $111,000."""
        result = _call(calculate_qcd_opportunity, self._base())
        assert result["qcd_annual_limit"] == 111_000.0

    def test_recommended_qcd_capped_at_charitable_intent(self):
        """Recommended QCD should not exceed stated charitable intent."""
        result = _call(calculate_qcd_opportunity, self._base(charitable_intent=15_000.0))
        assert result["recommended_qcd_amount"] <= 15_000.0

    def test_qcd_satisfies_rmd(self):
        """QCD should satisfy the RMD up to the QCD amount."""
        intent = 20_000.0
        rmd = 30_000.0
        result = _call(calculate_qcd_opportunity, self._base(
            charitable_intent=intent, rmd_amount=rmd
        ))
        assert result["rmd_satisfied_by_qcd"] == pytest.approx(min(intent, rmd), abs=0.01)
        assert result["rmd_remaining_after_qcd"] == pytest.approx(
            max(0.0, rmd - result["rmd_satisfied_by_qcd"]), abs=0.01
        )

    def test_qcd_ytd_reduces_remaining_limit(self):
        """Prior QCDs taken this year should reduce the remaining QCD capacity."""
        result = _call(calculate_qcd_opportunity, self._base(
            qcd_taken_ytd=50_000.0, charitable_intent=100_000.0
        ))
        assert result["qcd_remaining_limit"] == pytest.approx(111_000.0 - 50_000.0, abs=0.01)
        assert result["recommended_qcd_amount"] <= result["qcd_remaining_limit"]

    def test_non_itemizer_gets_agi_advantage_note(self):
        """Non-itemizer should receive note that QCD is the ONLY way to get charity tax benefit."""
        result = _call(calculate_qcd_opportunity, self._base(itemized_deductions=5_000.0))
        tax_comp = result["tax_comparison"]
        assert tax_comp["itemizes"] is False
        assert "ONLY way" in tax_comp["agi_advantage_note"]

    def test_requirements_list_not_empty(self):
        """Response must include compliance requirements list."""
        result = _call(calculate_qcd_opportunity, self._base())
        assert len(result["requirements"]) >= 5
        # Donor-advised fund restriction must be mentioned
        daf_mentioned = any("donor-advised" in r.lower() for r in result["requirements"])
        assert daf_mentioned, "DAF restriction must be listed in QCD requirements"
