"""Qualified Charitable Distribution (QCD) Calculator.

Rules (IRC §408(d)(8)):
  - Eligibility: age 70½ or older (not 70 — must be 70 and 6 months).
  - Annual limit: $105,000 (2024) / $108,000 (2025) / $111,000 (2026).
    Source: IRS Notice 2023-75; indexed for inflation under SECURE 2.0 Sec. 307.
  - QCD satisfies RMD without including the distribution in gross income.
  - QCD must go DIRECTLY from IRA to a qualified 501(c)(3) organization.
    Cannot go to donor-advised funds, supporting organizations, or private foundations.
    Source: IRC §408(d)(8)(B)(i).
  - Only from Traditional IRA (not Roth, not 401k, not SIMPLE IRA in first 2 years).
  - Cannot deduct QCD as charitable contribution (avoids double benefit).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from strands import tool

# QCD annual limits by year (indexed for inflation, SECURE 2.0 Sec. 307)
# Source: IRS Notice 2023-75; IRS Rev. Proc. (annual)
QCD_LIMITS: dict[int, float] = {
    2024: 105_000.0,
    2025: 108_000.0,
    2026: 111_000.0,
    2027: 114_000.0,  # projected ~3% inflation
}

# Standard deduction 2026 (approximate, assuming TCJA sunset)
STANDARD_DEDUCTION_MFJ_2026 = 30_000.0
STANDARD_DEDUCTION_SINGLE_2026 = 15_000.0


def _qcd_eligible(birth_year: int, birth_month: int, birth_day: int) -> bool:
    """Return True if client is age 70½ or older today.

    70½ birthday = 70th birthday + 183 days (IRS uses 6 calendar months).
    Source: IRS Pub. 590-B, "When Can You Make a QCD?"
    """
    today = date.today()
    try:
        seventieth = date(birth_year + 70, birth_month, birth_day)
    except ValueError:
        # Handle Feb 29 edge case
        seventieth = date(birth_year + 70, birth_month, 28)
    half_birthday = seventieth + timedelta(days=183)
    return today >= half_birthday


def _qcd_limit(year: int) -> float:
    """Return the QCD annual limit for the given year."""
    if year in QCD_LIMITS:
        return QCD_LIMITS[year]
    # Project forward: 3% annual increase beyond last known year
    last_year = max(QCD_LIMITS.keys())
    last_limit = QCD_LIMITS[last_year]
    return round(last_limit * (1.03 ** (year - last_year)), 0)


def _tax_benefit_vs_standard_deduction(
    qcd_amount: float,
    agi_before_qcd: float,
    filing_status: str,
    itemized_deductions: float,
) -> dict:
    """Compare QCD benefit versus taking a charitable deduction on Schedule A.

    A QCD reduces AGI dollar-for-dollar (excluded from gross income).
    A cash donation is deducted on Schedule A only if the client itemizes AND
    their itemized deductions exceed the standard deduction.
    """
    std_ded = STANDARD_DEDUCTION_MFJ_2026 if filing_status == "married" else STANDARD_DEDUCTION_SINGLE_2026
    itemizes = itemized_deductions > std_ded

    if itemizes:
        marginal_rate_cash = 0.24  # approximate; caller should provide actual bracket
        cash_deduction_benefit = round(qcd_amount * marginal_rate_cash, 2)
        qcd_benefit = round(qcd_amount * marginal_rate_cash, 2)  # Same tax $, but AGI is lower
        agi_advantage = (
            f"QCD reduces AGI by ${qcd_amount:,.2f}, which also reduces Medicare IRMAA base, "
            "ACA premium credits, taxation of Social Security benefits, and net investment "
            "income tax exposure — benefits beyond just the income deduction."
        )
    else:
        cash_deduction_benefit = 0.0  # Client cannot deduct cash charity (takes standard ded.)
        qcd_benefit = qcd_amount * 0.24  # QCD reduces AGI even when not itemizing — valuable!
        agi_advantage = (
            f"Client uses standard deduction (${std_ded:,.0f}) — a cash charitable donation "
            "provides NO additional tax benefit. QCD is the ONLY way to get a tax benefit from "
            "charitable giving. Reduces AGI by ${qcd_amount:,.2f}."
        )

    return {
        "itemizes": itemizes,
        "standard_deduction": std_ded,
        "itemized_deductions": itemized_deductions,
        "qcd_agi_reduction": qcd_amount,
        "cash_donation_benefit": cash_deduction_benefit,
        "qcd_benefit_estimate": round(qcd_benefit, 2),
        "agi_advantage_note": agi_advantage,
    }


@tool
def calculate_qcd_opportunity(client_data_json: str) -> str:
    """Calculate Qualified Charitable Distribution (QCD) opportunity for a client.

    Verifies eligibility (age 70½+), applies the annual QCD limit ($111,000 for 2026),
    shows how the QCD satisfies the client's RMD obligation without adding to taxable
    income, and compares the tax benefit of a QCD versus a standard cash charitable
    donation (which is only deductible if the client itemizes). QCDs must go directly
    from the IRA custodian to a qualified 501(c)(3) charity (not donor-advised funds).

    Args:
        client_data_json: JSON string with fields:
            - client_id (str): Client identifier.
            - birth_year (int): Year of birth.
            - birth_month (int): Month of birth (1-12).
            - birth_day (int): Day of birth (1-31).
            - age (int): Current age.
            - traditional_ira_balance (float): IRA balance (QCDs come from Traditional IRA).
            - rmd_amount (float, optional): Required Minimum Distribution for this year.
              QCD can satisfy all or part of the RMD. Default 0 (not yet RMD-eligible).
            - qcd_taken_ytd (float, optional): QCD amounts already distributed this year.
              Default 0.
            - charitable_intent (float, optional): Amount client intends to give to charity
              this year. Used to calculate optimal QCD. Default equals rmd_amount.
            - filing_status (str, optional): "married" or "single". Default "married".
            - itemized_deductions (float, optional): Total itemized deductions (mortgage,
              state taxes, etc.) excluding charitable contributions. Default 0.
            - agi_before_qcd (float, optional): AGI before any QCD distribution. Default 0.

    Returns:
        JSON string with fields:
            - client_id (str), eligible (bool), eligibility_reason (str),
            - qcd_annual_limit (float): QCD limit for the current year.
            - qcd_taken_ytd (float), qcd_remaining_limit (float),
            - recommended_qcd_amount (float): Optimal QCD given intent and limits.
            - rmd_satisfied_by_qcd (float): Portion of RMD covered by the recommended QCD.
            - rmd_remaining_after_qcd (float): RMD still needed as taxable distribution.
            - tax_comparison (dict): QCD vs cash donation comparison.
            - requirements (list): Key QCD compliance requirements.
            - explanation (str): Plain-English summary for the advisor.
    """
    data = json.loads(client_data_json)

    client_id = data.get("client_id", "unknown")
    birth_year = int(data["birth_year"])
    birth_month = int(data.get("birth_month", 1))
    birth_day = int(data.get("birth_day", 1))
    age = int(data["age"])
    ira_balance = float(data.get("traditional_ira_balance", 0.0))
    rmd_amount = float(data.get("rmd_amount", 0.0))
    qcd_taken = float(data.get("qcd_taken_ytd", 0.0))
    charitable_intent = float(data.get("charitable_intent", rmd_amount))
    filing_status = str(data.get("filing_status", "married")).lower()
    itemized = float(data.get("itemized_deductions", 0.0))
    agi_before = float(data.get("agi_before_qcd", 0.0))

    current_year = date.today().year

    # Eligibility check — must be 70½ (not just 70)
    eligible = _qcd_eligible(birth_year, birth_month, birth_day)
    if not eligible:
        return json.dumps({
            "client_id": client_id,
            "eligible": False,
            "eligibility_reason": (
                f"Client (born {birth_year}-{birth_month:02d}-{birth_day:02d}) has not "
                f"reached age 70½. QCDs are permitted only from age 70½ per IRC §408(d)(8). "
                f"Current age: {age}."
            ),
            "qcd_annual_limit": None,
            "qcd_taken_ytd": qcd_taken,
            "qcd_remaining_limit": 0.0,
            "recommended_qcd_amount": 0.0,
            "rmd_satisfied_by_qcd": 0.0,
            "rmd_remaining_after_qcd": rmd_amount,
            "tax_comparison": None,
            "requirements": [],
            "explanation": f"Client {client_id} is not yet 70½ and is ineligible for QCDs.",
        })

    annual_limit = _qcd_limit(current_year)
    remaining_limit = max(0.0, annual_limit - qcd_taken)

    # Recommended QCD = minimum of: charitable intent, remaining limit, IRA balance
    recommended_qcd = min(charitable_intent, remaining_limit, ira_balance)
    recommended_qcd = round(recommended_qcd, 2)

    # How much of the RMD does the QCD satisfy?
    rmd_satisfied = min(recommended_qcd, rmd_amount)
    rmd_remaining_after_qcd = max(0.0, round(rmd_amount - rmd_satisfied, 2))

    tax_comparison = _tax_benefit_vs_standard_deduction(
        recommended_qcd, agi_before, filing_status, itemized
    )

    requirements = [
        "QCD must be paid DIRECTLY from IRA custodian to the charity (no reimbursement method).",
        "Recipient must be a qualified 501(c)(3) public charity (NOT a donor-advised fund, "
        "supporting organization, or private foundation) — IRC §408(d)(8)(B)(i).",
        "QCD counts toward the annual limit ($111,000 for 2026) per person, per year.",
        "Cannot also claim a charitable deduction for the same QCD amount — no double benefit.",
        "Only from Traditional IRA (not Roth IRA, not 401k, not SIMPLE IRA in first 2 years).",
        "Request a direct transfer check made payable to the charity, not to the client.",
        "Obtain a written acknowledgment from the charity per IRC §170(f)(8) for your records.",
    ]

    explanation = (
        f"Client {client_id} (age {age}) is QCD-eligible (70½+ per IRC §408(d)(8)). "
        f"2026 annual QCD limit: ${annual_limit:,.0f}. "
        f"Already distributed: ${qcd_taken:,.2f}. "
        f"Remaining QCD capacity: ${remaining_limit:,.2f}. "
        f"Recommended QCD: ${recommended_qcd:,.2f} "
        f"(charitable intent: ${charitable_intent:,.2f}). "
    )
    if rmd_amount > 0:
        explanation += (
            f"This QCD satisfies ${rmd_satisfied:,.2f} of the ${rmd_amount:,.2f} RMD "
            f"obligation tax-free. Remaining RMD as taxable distribution: "
            f"${rmd_remaining_after_qcd:,.2f}. "
        )
    explanation += (
        f"Tax benefit: QCD reduces AGI by ${recommended_qcd:,.2f} without itemizing. "
        f"{'Cash donation provides no incremental benefit (standard deduction taken).' if not tax_comparison['itemizes'] else 'Client itemizes — QCD still preferred due to AGI reduction benefits.'}"
    )

    return json.dumps({
        "client_id": client_id,
        "eligible": True,
        "eligibility_reason": f"Client is age {age}, past age 70½ threshold per IRC §408(d)(8)",
        "qcd_annual_limit": annual_limit,
        "qcd_taken_ytd": qcd_taken,
        "qcd_remaining_limit": round(remaining_limit, 2),
        "recommended_qcd_amount": recommended_qcd,
        "rmd_satisfied_by_qcd": round(rmd_satisfied, 2),
        "rmd_remaining_after_qcd": rmd_remaining_after_qcd,
        "tax_comparison": tax_comparison,
        "requirements": requirements,
        "explanation": explanation,
    })
