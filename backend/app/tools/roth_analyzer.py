"""Roth Conversion Optimizer.

Rules:
  - Pro-rata rule: applies across ALL Traditional IRA balances when client has any
    non-deductible basis in an IRA (IRC §408(d)(2)). Must warn when mixed balances exist.
  - Optimal conversion window: gap years — retired but pre-Social Security and pre-RMD.
  - IRMAA: Medicare premium surcharges apply at income thresholds 2 years after conversion
    (based on MAGI from 2 years prior). Consider 2-year lag.
  - Future RMD reduction: each dollar converted to Roth reduces future RMD obligations.
"""
from __future__ import annotations

import json
from typing import Any

from strands import tool

# 2026 Federal Income Tax Brackets (MFJ) — approximate, subject to IRS annual adjustment
# Note: TCJA provisions are scheduled to expire after 2025; brackets below reflect projected
# 2026 rates assuming TCJA sunset. Advisor should verify current-year IRS publication.
# Source: IRS Rev. Proc. (annual inflation adjustment); projected for 2026
TAX_BRACKETS_MFJ_2026 = [
    (23_200,   0.10),
    (94_300,   0.12),
    (201_050,  0.22),
    (383_900,  0.24),
    (487_450,  0.32),
    (731_200,  0.35),
    (float("inf"), 0.37),
]
TAX_BRACKETS_SINGLE_2026 = [
    (11_600,   0.10),
    (47_150,   0.12),
    (100_525,  0.22),
    (191_950,  0.24),
    (243_725,  0.32),
    (609_350,  0.35),
    (float("inf"), 0.37),
]

# IRMAA Income Thresholds for 2026 Medicare Part B
# Based on 2024 MAGI (2-year lookback); projected from 2025 published thresholds
# Source: CMS Medicare IRMAA adjustments; projected for 2026
# Format: (MFJ_threshold, Single_threshold, monthly_surcharge_per_person)
IRMAA_THRESHOLDS_2026 = [
    (206_000,  103_000,   0.0),     # Standard premium (~$185/month)
    (258_000,  129_000,  74.0),     # Tier 1 surcharge
    (322_000,  161_000, 187.0),     # Tier 2
    (386_000,  193_000, 280.0),     # Tier 3
    (750_000,  500_000, 374.0),     # Tier 4
    (float("inf"), float("inf"), 419.0),  # Tier 5 (highest)
]


def _marginal_rate(taxable_income: float, filing_status: str) -> float:
    """Return the marginal federal tax rate for the given taxable income."""
    brackets = TAX_BRACKETS_MFJ_2026 if filing_status == "married" else TAX_BRACKETS_SINGLE_2026
    prev = 0.0
    for ceiling, rate in brackets:
        if taxable_income <= ceiling:
            return rate
        prev = rate
    return prev


def _bracket_room(taxable_income: float, filing_status: str) -> float:
    """Return dollars of room remaining in the current tax bracket."""
    brackets = TAX_BRACKETS_MFJ_2026 if filing_status == "married" else TAX_BRACKETS_SINGLE_2026
    for ceiling, _ in brackets:
        if taxable_income < ceiling:
            return ceiling - taxable_income
    return 0.0


def _irmaa_surcharge(magi: float, filing_status: str) -> dict:
    """Return IRMAA surcharge info for the given MAGI."""
    idx = 1 if filing_status == "married" else 2  # 0=MFJ threshold, 1=Single threshold
    mfj_idx = 0
    single_idx = 1
    threshold_idx = mfj_idx if filing_status == "married" else single_idx

    for i, (mfj_thresh, single_thresh, monthly_surcharge) in enumerate(IRMAA_THRESHOLDS_2026):
        threshold = mfj_thresh if filing_status == "married" else single_thresh
        if magi <= threshold:
            annual = monthly_surcharge * 12
            return {
                "tier": i,
                "monthly_surcharge_per_person": monthly_surcharge,
                "annual_surcharge_per_person": annual,
                "magi_used": magi,
                "note": (
                    f"IRMAA Tier {i}: ${monthly_surcharge:.0f}/month surcharge per person "
                    f"(${annual:.0f}/yr). IRMAA is based on MAGI from 2 years prior — "
                    "a Roth conversion today affects Medicare premiums in 2028."
                ),
            }
    return {"tier": 5, "monthly_surcharge_per_person": 419.0, "annual_surcharge_per_person": 5028.0,
            "note": "Highest IRMAA tier applies."}


def _pro_rata_warning(trad_ira_balance: float, nondeductible_basis: float) -> dict | None:
    """Return a pro-rata rule warning if client has mixed IRA balances.

    Pro-rata rule (IRC §408(d)(2)): any conversion is treated as coming pro-rata
    from pre-tax and after-tax (basis) dollars. Cannot convert only the basis portion.
    """
    if nondeductible_basis <= 0:
        return None
    taxable_fraction = (trad_ira_balance - nondeductible_basis) / trad_ira_balance
    return {
        "nondeductible_basis": nondeductible_basis,
        "total_trad_ira_balance": trad_ira_balance,
        "taxable_fraction": round(taxable_fraction, 4),
        "after_tax_fraction": round(1 - taxable_fraction, 4),
        "warning": (
            f"PRO-RATA RULE (IRC §408(d)(2)): Client has ${nondeductible_basis:,.2f} of "
            f"nondeductible (after-tax) basis in a total Traditional IRA balance of "
            f"${trad_ira_balance:,.2f}. Only {(1 - taxable_fraction) * 100:.1f}% of any "
            "conversion is tax-free; the remaining "
            f"{taxable_fraction * 100:.1f}% is taxable. "
            "The only way to avoid pro-rata is to roll pre-tax IRA funds into an employer "
            "401(k) plan first (if the plan accepts rollovers), isolating the basis for conversion."
        ),
    }


@tool
def analyze_roth_conversion(client_data_json: str) -> str:
    """Analyze and recommend an optimal Roth IRA conversion strategy for a client.

    Calculates the maximum tax-efficient conversion amount that fills the current tax
    bracket without pushing into a higher bracket or crossing an IRMAA Medicare premium
    surcharge threshold. Warns about the pro-rata rule if the client has nondeductible
    IRA basis (IRC §408(d)(2)). Estimates the future RMD reduction from converting
    today, and notes the 2-year IRMAA lookback lag.

    Args:
        client_data_json: JSON string with fields:
            - client_id (str): Client identifier.
            - age (int): Client's current age.
            - filing_status (str): "married" or "single".
            - current_taxable_income (float): Estimated taxable income this year
              BEFORE any Roth conversion (after deductions and adjustments).
            - traditional_ira_balance (float): Total pre-tax Traditional IRA balance.
            - nondeductible_ira_basis (float, optional): After-tax contributions
              (Form 8606 basis). Used to calculate pro-rata rule impact. Default 0.
            - rmd_age (int, optional): Age at which RMDs begin per SECURE Act 2.0.
              Default 73. Used to estimate future RMD reduction.
            - years_to_rmd (int, optional): Years until RMD begins. Overrides rmd_age
              calculation if provided.
            - rmd_eligible (bool, optional): True if client is currently taking RMDs.
              If True, conversions reduce next year's RMD basis. Default False.
            - assumed_growth_rate (float, optional): Annual pre-tax growth rate for RMD
              projection. Default 0.06 (6%).

    Returns:
        JSON string with fields:
            - client_id (str), eligible_for_conversion (bool),
            - current_marginal_rate (float), bracket_room (float),
            - optimal_conversion_amount (float): Max conversion to fill current bracket.
            - tax_on_conversion (float): Estimated federal tax on the conversion.
            - effective_conversion_rate (float): Tax cost as a % of converted amount.
            - irmaa_analysis (dict): Medicare premium impact of the conversion MAGI.
            - irmaa_risk (bool): True if conversion would push into a higher IRMAA tier.
            - pro_rata_warning (dict|null): Pro-rata rule details if nondeductible basis exists.
            - rmd_reduction_estimate (float): Estimated reduction in future annual RMD
              if the full optimal conversion is completed today.
            - explanation (str): Plain-English summary for the advisor.
    """
    data = json.loads(client_data_json)

    client_id = data.get("client_id", "unknown")
    age = int(data.get("age", 65))
    filing_status = str(data.get("filing_status", "married")).lower()
    taxable_income = float(data.get("current_taxable_income", 0.0))
    trad_balance = float(data.get("traditional_ira_balance", 0.0))
    basis = float(data.get("nondeductible_ira_basis", 0.0))
    rmd_eligible = bool(data.get("rmd_eligible", False))
    growth_rate = float(data.get("assumed_growth_rate", 0.06))
    years_to_rmd = data.get("years_to_rmd")
    rmd_age_threshold = int(data.get("rmd_age", 73))

    if years_to_rmd is None:
        years_to_rmd = max(0, rmd_age_threshold - age)

    # Roth conversions are always allowed (no income limit since 2010 ROTH conversion rules)
    # Source: Tax Increase Prevention and Reconciliation Act of 2005
    marginal_rate = _marginal_rate(taxable_income, filing_status)
    bracket_room = _bracket_room(taxable_income, filing_status)

    # Optimal conversion = fill current bracket without spilling into next bracket
    # Cap at Traditional IRA balance
    optimal_conversion = min(bracket_room, trad_balance)

    # Tax on conversion (simplified: conversion amount taxed at marginal rate)
    # Actual calculation is more complex due to bracket stacking; this is a close approximation
    tax_on_conversion = round(optimal_conversion * marginal_rate, 2)
    effective_rate = round(marginal_rate * 100, 1)

    # IRMAA analysis — conversion adds to MAGI (with 2-year lookback)
    post_conversion_magi = taxable_income + optimal_conversion
    irmaa_before = _irmaa_surcharge(taxable_income, filing_status)
    irmaa_after = _irmaa_surcharge(post_conversion_magi, filing_status)
    irmaa_risk = irmaa_after["tier"] > irmaa_before["tier"]

    # If IRMAA risk exists, find the maximum conversion that stays in the same tier
    if irmaa_risk:
        # Binary-search for the IRMAA threshold
        brackets = IRMAA_THRESHOLDS_2026
        for mfj_t, single_t, _ in brackets:
            thresh = mfj_t if filing_status == "married" else single_t
            if taxable_income < thresh <= taxable_income + optimal_conversion:
                irmaa_safe_conversion = thresh - taxable_income - 1
                optimal_conversion = max(0.0, min(optimal_conversion, irmaa_safe_conversion))
                break
        tax_on_conversion = round(optimal_conversion * marginal_rate, 2)

    # Pro-rata rule warning
    pro_rata = _pro_rata_warning(trad_balance, basis)

    # Future RMD reduction estimate
    # Converting today reduces IRA balance by optimal_conversion.
    # Future RMD is calculated from a projected balance; reduction is the amount that
    # would have been distributed as RMD from that converted balance.
    # Using ULT period at RMD age (typically 26.5 at age 73)
    from app.tools.rmd_calculator import UNIFORM_LIFETIME_TABLE
    ult_at_rmd = UNIFORM_LIFETIME_TABLE.get(rmd_age_threshold, 26.5)
    projected_converted_value = optimal_conversion * ((1 + growth_rate) ** years_to_rmd)
    rmd_reduction_estimate = round(projected_converted_value / ult_at_rmd, 2)

    explanation = (
        f"Client {client_id} (age {age}, {filing_status}) — "
        f"current taxable income: ${taxable_income:,.2f}, marginal rate: {effective_rate}%. "
        f"Bracket room remaining: ${bracket_room:,.2f}. "
        f"Optimal Roth conversion: ${optimal_conversion:,.2f} "
        f"(estimated tax cost: ${tax_on_conversion:,.2f} at {effective_rate}% effective rate). "
    )
    if irmaa_risk:
        explanation += (
            f"IRMAA ALERT: full bracket-fill conversion would cross an IRMAA threshold. "
            f"Conversion capped at ${optimal_conversion:,.2f} to avoid Medicare surcharge. "
        )
    if pro_rata:
        explanation += f"PRO-RATA WARNING: {pro_rata['warning']} "
    explanation += (
        f"Estimated RMD reduction in {years_to_rmd} year(s): ${rmd_reduction_estimate:,.2f}/yr "
        f"(assumes {growth_rate * 100:.0f}% growth, ULT period {ult_at_rmd} at age {rmd_age_threshold})."
    )

    return json.dumps({
        "client_id": client_id,
        "eligible_for_conversion": True,
        "current_marginal_rate": marginal_rate,
        "bracket_room": round(bracket_room, 2),
        "optimal_conversion_amount": round(optimal_conversion, 2),
        "tax_on_conversion": tax_on_conversion,
        "effective_conversion_rate_pct": effective_rate,
        "irmaa_before_conversion": irmaa_before,
        "irmaa_after_conversion": irmaa_after,
        "irmaa_risk": irmaa_risk,
        "pro_rata_warning": pro_rata,
        "years_to_rmd": years_to_rmd,
        "rmd_reduction_estimate": rmd_reduction_estimate,
        "explanation": explanation,
    })
