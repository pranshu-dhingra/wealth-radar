"""RMD Calculator — IRS Required Minimum Distribution tool.

Sources:
  - IRS Publication 590-B (2024): Distributions from IRAs
  - IRS Regulation §1.401(a)(9)-9: Life Expectancy Tables (effective 2022)
  - SECURE Act 2.0 (Div. T of Consolidated Appropriations Act 2023):
      RMD age 73 for born 1951-1959; age 75 for born 1960+
  - SECURE 2.0 Sec. 302 / IRC §4974: excise tax 25% (10% if corrected timely)
"""
from __future__ import annotations

import json
from datetime import date

from strands import tool

# IRS Uniform Lifetime Table III — Distribution Periods
# Source: IRS Reg. §1.401(a)(9)-9(c), Table III (effective for RMDs >= 2022)
UNIFORM_LIFETIME_TABLE: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6,
    76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
    80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7,
    84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4,
    88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5,
    92: 10.8, 93: 10.1, 94:  9.5, 95:  8.9,
    96:  8.4, 97:  7.8, 98:  7.3, 99:  6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2,
    104: 4.9, 105: 4.6, 106: 4.3, 107: 4.1,
    108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4,
    112: 3.3, 113: 3.1, 114: 3.0, 115: 2.9,
    116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3,
    120: 2.0,
}

# IRS Joint Life and Last Survivor Table II — selected pairs
# Used when sole beneficiary is a spouse >10 years younger than the owner.
# Source: IRS Reg. §1.401(a)(9)-9(d), Table II
_JOINT_LIFE_TABLE: dict[tuple[int, int], float] = {
    (72, 55): 33.2, (72, 56): 32.7, (72, 57): 32.2, (72, 58): 31.8,
    (72, 59): 31.3, (72, 60): 30.9, (72, 61): 30.5,
    (73, 56): 33.4, (73, 57): 32.9, (73, 58): 32.5, (73, 59): 32.0,
    (73, 60): 31.6, (73, 61): 31.2, (73, 62): 30.8,
    (74, 57): 33.6, (74, 58): 33.2, (74, 59): 32.7, (74, 60): 32.3,
    (74, 61): 31.9, (74, 62): 31.5, (74, 63): 31.1,
    (75, 58): 33.8, (75, 59): 33.4, (75, 60): 33.0, (75, 61): 32.5,
    (75, 62): 32.1, (75, 63): 31.7, (75, 64): 31.3,
    (76, 59): 34.0, (76, 60): 33.6, (76, 61): 33.2, (76, 62): 32.8,
    (77, 60): 34.2, (77, 61): 33.8, (77, 62): 33.4, (77, 63): 33.0,
    (80, 63): 34.3, (80, 64): 33.9, (80, 65): 33.5, (80, 66): 33.1,
    (80, 67): 32.7, (80, 68): 32.3, (80, 69): 31.9,
    (85, 68): 34.6, (85, 69): 34.3, (85, 70): 34.0, (85, 71): 33.7,
}


def _joint_period(owner_age: int, spouse_age: int) -> float:
    """Return Joint Life Table II period; approximate if exact pair not found."""
    if (owner_age, spouse_age) in _JOINT_LIFE_TABLE:
        return _JOINT_LIFE_TABLE[(owner_age, spouse_age)]
    ult = UNIFORM_LIFETIME_TABLE.get(min(owner_age, 120), 2.0)
    gap_bonus = max(0, owner_age - spouse_age - 10) * 0.3
    return round(ult + gap_bonus, 1)


def _rmd_start_age(birth_year: int) -> int:
    """Return RMD starting age per SECURE Act 2.0 (IRC §401(a)(9)(C) as amended).

    Born <=1950: age 72 (pre-SECURE 2.0 cohort)
    Born 1951-1959: age 73 (SECURE 2.0, Sec. 107(a))
    Born >=1960: age 75 (SECURE 2.0, Sec. 107(b))
    """
    if birth_year <= 1950:
        return 72
    if birth_year <= 1959:
        return 73
    return 75


def _rmd_deadline(age: int, birth_year: int, current_year: int) -> str:
    """Return plain-English RMD deadline.

    First RMD: may defer to April 1 of the following year (IRC §401(a)(9)(C)(i)).
    Subsequent RMDs: December 31 of the distribution year (IRC §401(a)(9)(C)(ii)).
    """
    threshold = _rmd_start_age(birth_year)
    turns_year = birth_year + threshold
    if current_year == turns_year:
        return (
            f"April 1, {turns_year + 1} (first-ever RMD — "
            f"taking in {turns_year} avoids stacking two RMDs next year)"
        )
    return f"December 31, {current_year}"


@tool
def calculate_rmd(client_data_json: str) -> str:
    """Calculate the Required Minimum Distribution (RMD) for a client's IRA accounts.

    Applies IRS Uniform Lifetime Table III (Reg. §1.401(a)(9)-9(c)) for most clients,
    or Joint Life and Last Survivor Table II when the sole beneficiary is a spouse more
    than 10 years younger (Reg. §1.401(a)(9)-9(d)). Enforces SECURE Act 2.0 thresholds
    (age 73 born 1951-1959; age 75 born 1960+). Computes 25% excise tax penalty on any
    shortfall, or 10% if corrected timely (SECURE 2.0 Sec. 302 / IRC §4974).

    Args:
        client_data_json: JSON string with fields:
            - client_id (str): Client identifier.
            - birth_year (int): Year of birth (determines RMD age threshold).
            - age (int): Current age.
            - traditional_ira_balance (float): Aggregate balance of all Traditional IRA /
              401(k) accounts as of December 31 of the prior year (the RMD calculation basis).
            - rmd_taken_ytd (float, optional): Amount already distributed this year. Default 0.
            - spouse_age (int, optional): Spouse's age. If sole beneficiary is a spouse
              more than 10 years younger, Joint Life Table II applies (lower RMD).
            - corrected_timely (bool, optional): True if correcting a prior missed RMD
              within the 2-year IRS correction window (reduces excise tax to 10%). Default False.

    Returns:
        JSON string with fields:
            - client_id (str), eligible (bool), rmd_age_threshold (int),
            - distribution_period (float|null), table_used (str|null),
            - rmd_required (float), rmd_taken_ytd (float), rmd_remaining (float),
            - deadline (str), penalty (dict|null), explanation (str).
    """
    data = json.loads(client_data_json)

    client_id = data.get("client_id", "unknown")
    birth_year = int(data["birth_year"])
    age = int(data["age"])
    ira_balance = float(data["traditional_ira_balance"])
    rmd_taken = float(data.get("rmd_taken_ytd", 0.0))
    spouse_age = data.get("spouse_age")
    corrected_timely = bool(data.get("corrected_timely", False))

    current_year = date.today().year
    threshold = _rmd_start_age(birth_year)

    if age < threshold:
        years_until = (birth_year + threshold) - current_year
        return json.dumps({
            "client_id": client_id,
            "eligible": False,
            "rmd_age_threshold": threshold,
            "distribution_period": None,
            "table_used": None,
            "rmd_required": 0.0,
            "rmd_taken_ytd": rmd_taken,
            "rmd_remaining": 0.0,
            "deadline": (
                f"RMDs begin at age {threshold} "
                f"(year {birth_year + threshold}, ~{years_until} year(s) away)"
            ),
            "penalty": None,
            "explanation": (
                f"Client {client_id} (born {birth_year}, age {age}) is below the "
                f"SECURE Act 2.0 RMD threshold of age {threshold}. "
                f"No RMD required this year. RMDs begin in {birth_year + threshold}."
            ),
        })

    # Joint Life Table II applies when sole beneficiary is a spouse >10 yrs younger
    # Source: IRS Reg. §1.401(a)(9)-5(d)(3)
    use_joint = spouse_age is not None and (age - int(spouse_age)) > 10
    if use_joint:
        period = _joint_period(age, int(spouse_age))
        table_used = "Joint Life and Last Survivor Table II (IRS Reg. §1.401(a)(9)-9(d))"
    else:
        period = UNIFORM_LIFETIME_TABLE.get(min(age, 120), 2.0)
        table_used = "Uniform Lifetime Table III (IRS Reg. §1.401(a)(9)-9(c))"

    # RMD = Prior-year Dec 31 balance / distribution period  [IRS Pub. 590-B, Worksheet 1-1]
    rmd_required = round(ira_balance / period, 2)
    rmd_remaining = round(max(0.0, rmd_required - rmd_taken), 2)
    deadline = _rmd_deadline(age, birth_year, current_year)

    # Excise tax on shortfall — IRC §4974(a); SECURE 2.0 Sec. 302 (reduced from 50% to 25%)
    penalty = None
    if rmd_remaining > 0:
        rate = 0.10 if corrected_timely else 0.25
        penalty = {
            "shortfall": rmd_remaining,
            "excise_tax_rate": f"{int(rate * 100)}%",
            "excise_tax_amount": round(rmd_remaining * rate, 2),
            "note": (
                "10% rate applies if corrected within the 2-year IRS window "
                "(SECURE 2.0 Sec. 302); otherwise 25% per IRC §4974(a)."
            ),
        }

    explanation = (
        f"Client {client_id} (born {birth_year}, age {age}) — "
        f"RMD threshold: age {threshold} (SECURE Act 2.0). "
        f"Using {table_used}, period {period}. "
        f"${ira_balance:,.2f} / {period} = RMD ${rmd_required:,.2f}. "
        f"Taken YTD: ${rmd_taken:,.2f}. Remaining: ${rmd_remaining:,.2f} due {deadline}."
    )
    if penalty:
        explanation += (
            f" PENALTY RISK: ${rmd_remaining:,.2f} shortfall => "
            f"{penalty['excise_tax_rate']} excise tax = ${penalty['excise_tax_amount']:,.2f}."
        )

    return json.dumps({
        "client_id": client_id,
        "eligible": True,
        "rmd_age_threshold": threshold,
        "distribution_period": period,
        "table_used": table_used,
        "rmd_required": rmd_required,
        "rmd_taken_ytd": rmd_taken,
        "rmd_remaining": rmd_remaining,
        "deadline": deadline,
        "penalty": penalty,
        "explanation": explanation,
    })
