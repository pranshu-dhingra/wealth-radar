"""Generate 50 synthetic client profiles for WealthRadar demo.

Outputs:
  backend/app/data/clients.json

Usage:
    cd wealth-radar
    python scripts/generate_synthetic_data.py

Requires:
    pip install faker  (already in backend/.venv)
"""
from __future__ import annotations

import json
import os
import random
from datetime import date, timedelta
from typing import Any

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Run:  pip install faker")

# ── Reproducible ──────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

TODAY = date(2026, 3, 8)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── IRS Uniform Lifetime Table III distribution periods (SECURE 2.0) ──────────
# Source: IRS Publication 590-B, Table III
ULT: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7,
    77: 22.9, 78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4,
    82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
}

# ── Risk profiles → target allocation (must sum to 100) ───────────────────────
RISK_PROFILES: dict[str, dict[str, float]] = {
    "conservative": {
        "US_EQUITY": 25.0, "INTL_EQUITY": 10.0,
        "US_BOND":   40.0, "INTL_BOND":   10.0,
        "REAL_ESTATE": 8.0, "COMMODITIES": 7.0,
    },
    "moderate": {
        "US_EQUITY": 40.0, "INTL_EQUITY": 15.0,
        "US_BOND":   28.0, "INTL_BOND":    7.0,
        "REAL_ESTATE": 6.0, "COMMODITIES": 4.0,
    },
    "balanced": {
        "US_EQUITY": 50.0, "INTL_EQUITY": 18.0,
        "US_BOND":   18.0, "INTL_BOND":    5.0,
        "REAL_ESTATE": 5.0, "COMMODITIES": 4.0,
    },
    "growth": {
        "US_EQUITY": 58.0, "INTL_EQUITY": 22.0,
        "US_BOND":   10.0, "INTL_BOND":    4.0,
        "REAL_ESTATE": 4.0, "COMMODITIES": 2.0,
    },
    "aggressive": {
        "US_EQUITY": 65.0, "INTL_EQUITY": 25.0,
        "US_BOND":    5.0, "INTL_BOND":    3.0,
        "REAL_ESTATE": 2.0, "COMMODITIES": 0.0,
    },
}

INSTITUTIONS = [
    "Fidelity", "Vanguard", "Schwab", "TD Ameritrade",
    "Merrill Lynch", "Morgan Stanley", "Edward Jones",
    "Raymond James", "LPL Financial", "Ameriprise",
]

# 2026 MFJ income tax brackets (approximate)
TAX_BRACKETS: list[tuple[int, int, str]] = [
    (0,        47_150,  "10%"),
    (47_150,   100_525, "12%"),
    (100_525,  191_950, "22%"),
    (191_950,  243_725, "24%"),
    (243_725,  609_350, "32%"),
    (609_350,  999_999_999, "37%"),
]

RELATIONSHIPS = ["spouse", "child", "sibling", "parent", "domestic partner",
                 "niece/nephew", "grandchild", "trust", "charity"]

# ── 50 client templates ────────────────────────────────────────────────────────
# Each tuple: (tier, birth_year, marital_status, risk_profile, special_flags: set)
#
# Age distribution target: 15 aged 65-85, 20 aged 45-64, 15 aged 30-44
# Tier distribution:  8-A  12-B  18-C  12-D
# Special story flags:
#   "overdue_rmd"     — RMD not yet taken in 2026 (3 required)
#   "drift"           — portfolio drift >5% in at least one class (5 required)
#   "recent_life"     — major life event in last 90 days (3 required)
#   "outdated_estate" — estate docs last updated >3 years ago (2 required)
#   "tlh"             — tax-loss harvesting opportunity >$1k (4 required)
#   "married"         — has spouse data (10 required)
#   "qcd"             — QCD donor flag (computed, also manually set on some)

CLIENT_TEMPLATES: list[tuple[str, int, str, str, set[str]]] = [
    # ── Tier A: 8 clients (ages spread across all brackets) ──────────────
    ("A", 1948, "married",  "conservative", {"overdue_rmd", "married", "qcd"}),          # 0  age 77
    ("A", 1951, "married",  "moderate",     {"drift", "married", "qcd"}),                # 1  age 74
    ("A", 1952, "widowed",  "conservative", {"overdue_rmd", "recent_life", "qcd"}),      # 2  age 73  (spouse died)
    ("A", 1958, "married",  "moderate",     {"drift", "married", "qcd"}),                # 3  age 67
    ("A", 1963, "married",  "balanced",     {"outdated_estate", "married", "tlh"}),      # 4  age 62
    ("A", 1968, "single",   "growth",       {"tlh"}),                                    # 5  age 57
    ("A", 1975, "married",  "growth",       {"married"}),                                # 6  age 50
    ("A", 1982, "single",   "aggressive",   {"drift"}),                                  # 7  age 43
    # ── Tier B: 12 clients ───────────────────────────────────────────────
    ("B", 1945, "widowed",  "conservative", {"overdue_rmd", "qcd"}),                     # 8  age 80
    ("B", 1950, "married",  "moderate",     {"drift", "married", "qcd"}),                # 9  age 75
    ("B", 1953, "divorced", "moderate",     {"qcd", "tlh"}),                             # 10 age 72
    ("B", 1957, "married",  "moderate",     {"married", "outdated_estate"}),             # 11 age 68
    ("B", 1960, "married",  "balanced",     {"married", "recent_life"}),                 # 12 age 65  (retirement)
    ("B", 1964, "single",   "balanced",     {"drift"}),                                  # 13 age 61
    ("B", 1966, "married",  "balanced",     {"married"}),                                # 14 age 59
    ("B", 1970, "single",   "growth",       {"tlh"}),                                    # 15 age 55
    ("B", 1973, "married",  "growth",       {"married"}),                                # 16 age 52
    ("B", 1977, "single",   "growth",       {}),                                         # 17 age 48
    ("B", 1980, "married",  "balanced",     {"married", "recent_life"}),                 # 18 age 45  (new baby)
    ("B", 1984, "single",   "growth",       {}),                                         # 19 age 41
    # ── Tier C: 18 clients ───────────────────────────────────────────────
    ("C", 1946, "married",  "conservative", {"qcd", "married"}),                         # 20 age 79
    ("C", 1952, "widowed",  "conservative", {"qcd"}),                                    # 21 age 73
    ("C", 1955, "married",  "moderate",     {"married", "qcd"}),                         # 22 age 70
    ("C", 1959, "single",   "moderate",     {}),                                         # 23 age 66
    ("C", 1961, "married",  "moderate",     {"married"}),                                # 24 age 64
    ("C", 1965, "divorced", "balanced",     {}),                                         # 25 age 60
    ("C", 1967, "married",  "balanced",     {"married", "recent_life"}),                 # 26 age 58  (job change)
    ("C", 1969, "single",   "balanced",     {}),                                         # 27 age 56
    ("C", 1972, "married",  "growth",       {"married"}),                                # 28 age 53
    ("C", 1974, "single",   "growth",       {}),                                         # 29 age 51
    ("C", 1976, "married",  "growth",       {"married"}),                                # 30 age 49
    ("C", 1979, "single",   "growth",       {}),                                         # 31 age 46
    ("C", 1981, "married",  "growth",       {"married"}),                                # 32 age 44
    ("C", 1984, "single",   "aggressive",   {}),                                         # 33 age 41
    ("C", 1987, "single",   "aggressive",   {}),                                         # 34 age 38
    ("C", 1990, "married",  "aggressive",   {"married"}),                                # 35 age 35
    ("C", 1993, "single",   "aggressive",   {}),                                         # 36 age 32
    ("C", 1996, "single",   "aggressive",   {}),                                         # 37 age 29 (just under 30, ~30)
    # ── Tier D: 12 clients ───────────────────────────────────────────────
    ("D", 1949, "widowed",  "conservative", {"qcd"}),                                    # 38 age 76
    ("D", 1956, "married",  "moderate",     {"married"}),                                # 39 age 69
    ("D", 1963, "divorced", "moderate",     {}),                                         # 40 age 62
    ("D", 1971, "single",   "balanced",     {}),                                         # 41 age 54
    ("D", 1975, "married",  "growth",       {"married"}),                                # 42 age 50
    ("D", 1980, "single",   "growth",       {}),                                         # 43 age 45
    ("D", 1985, "married",  "growth",       {"married"}),                                # 44 age 40
    ("D", 1988, "single",   "aggressive",   {}),                                         # 45 age 37
    ("D", 1991, "single",   "aggressive",   {}),                                         # 46 age 34
    ("D", 1994, "married",  "aggressive",   {"married"}),                                # 47 age 31
    ("D", 1997, "single",   "aggressive",   {}),                                         # 48 age 28
    ("D", 2000, "single",   "aggressive",   {}),                                         # 49 age 25
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _age(birth_year: int, birth_month: int = 6, birth_day: int = 15) -> int:
    bday = date(birth_year, birth_month, birth_day)
    return (TODAY - bday).days // 365


def _tax_bracket(income: float) -> str:
    for lo, hi, bracket in TAX_BRACKETS:
        if lo <= income < hi:
            return bracket
    return "37%"


def _rmd_age(birth_year: int) -> int:
    # SECURE Act 2.0: born 1951–1959 → RMD age 73; born 1960+ → RMD age 75
    # Pre-1951 clients were already under old rules; treat as 73 for simplicity
    return 73 if birth_year <= 1959 else 75


def _rmd_eligible(age: int, birth_year: int) -> bool:
    return age >= _rmd_age(birth_year)


def _qcd_eligible(birth_year: int, birth_month: int, birth_day: int) -> bool:
    # QCD eligible at age 70½ — IRS Pub 590-B
    # First compute the 70th birthday, then add 6 months (183 days)
    try:
        seventieth = date(birth_year + 70, birth_month, birth_day)
    except ValueError:
        seventieth = date(birth_year + 70, birth_month, 28)
    return (seventieth + timedelta(days=183)) <= TODAY


def _rand_date(days_min: int, days_max: int) -> str:
    d = TODAY - timedelta(days=random.randint(days_min, days_max))
    return d.isoformat()


def _next_meeting(tier: str, last_meeting: str) -> str:
    freq_days = {"A": 90, "B": 120, "C": 180, "D": 365}
    last = date.fromisoformat(last_meeting)
    nxt = last + timedelta(days=freq_days[tier] + random.randint(-10, 10))
    return nxt.isoformat()


def _drift_allocation(base: dict[str, float]) -> dict[str, float]:
    """Return a current allocation with >5% drift in US_EQUITY and US_BOND."""
    shifted = dict(base)
    # Equity ran up; bonds underweight
    equity_shift = random.uniform(6.5, 12.0)
    bond_shift   = random.uniform(4.0, 7.0)
    shifted["US_EQUITY"]   = round(min(95, shifted["US_EQUITY"]   + equity_shift), 1)
    shifted["US_BOND"]     = round(max(0,  shifted["US_BOND"]     - bond_shift),   1)
    shifted["INTL_EQUITY"] = round(max(0,  shifted["INTL_EQUITY"] - (equity_shift - bond_shift) / 2), 1)
    # Normalize to 100
    total = sum(shifted.values())
    return {k: round(v / total * 100, 1) for k, v in shifted.items()}


def _make_accounts(
    tier: str,
    birth_year: int,
    age: int,
    total_aum: float,
    flags: set[str],
) -> list[dict]:
    """Generate 2-5 accounts whose balances sum to approximately total_aum."""
    age_group = "senior" if age >= 60 else ("mid" if age >= 45 else "young")

    # Choose account types by life stage
    if age >= 70:
        pool = ["Roth IRA", "Joint Brokerage", "Trust Account"]
        mandatory = ["Traditional IRA"]          # always include for RMD calculation
    elif age >= 55:
        pool = ["401(k)", "Roth IRA", "Joint Brokerage", "Individual Brokerage"]
        mandatory = ["Traditional IRA"]
    elif age >= 45:
        pool = ["Traditional IRA", "Roth IRA", "Individual Brokerage", "Joint Brokerage"]
        mandatory = ["401(k)"]
    else:
        pool = ["Traditional IRA", "Individual Brokerage"]
        mandatory = ["Roth IRA", "401(k)"]

    num_accounts = {"A": random.randint(3, 5), "B": random.randint(2, 4),
                    "C": random.randint(2, 3),  "D": random.randint(2, 3)}[tier]
    num_extra = max(0, num_accounts - len(mandatory))
    extra = random.sample(pool, min(num_extra, len(pool)))
    chosen_types = mandatory + extra

    # Split AUM: first account gets the largest share
    raw = sorted([random.random() for _ in range(num_accounts)], reverse=True)
    raw_total = sum(raw)
    splits = [r / raw_total for r in raw]

    is_taxable_map = {
        "Traditional IRA": False, "Roth IRA": False, "401(k)": False,
        "403(b)": False, "SEP IRA": False,
        "Joint Brokerage": True, "Individual Brokerage": True, "Trust Account": True,
    }

    accounts: list[dict] = []
    for idx, (acct_type, split) in enumerate(zip(chosen_types, splits)):
        balance = round(total_aum * split, 2)
        institution = random.choice(INSTITUTIONS)
        last_bene_review = _rand_date(30, 4 * 365)
        bene_ok = random.random() > 0.15

        accounts.append({
            "account_id":               f"CLT{idx:03d}-placeholder",  # filled in by caller
            "account_type":             acct_type,
            "institution":              institution,
            "account_number":           f"****{random.randint(1000, 9999)}",
            "balance":                  balance,
            "is_taxable":               is_taxable_map.get(acct_type, False),
            "beneficiary_designated":   bene_ok,
            "beneficiary_last_reviewed": last_bene_review,
        })
    return accounts


def _make_beneficiaries(marital_status: str) -> list[dict]:
    primaries: list[dict] = []
    contingents: list[dict] = []

    if marital_status == "married":
        primaries.append({
            "name":         fake.name(),
            "relationship": "spouse",
            "percentage":   100,
            "type":         "primary",
        })
        # 1-2 contingent beneficiaries
        for _ in range(random.randint(1, 2)):
            rel = random.choice(["child", "sibling", "parent"])
            contingents.append({
                "name":         fake.name(),
                "relationship": rel,
                "percentage":   round(100 / random.randint(1, 2)),
                "type":         "contingent",
            })
    else:
        # 1-3 primary beneficiaries splitting 100%
        n = random.randint(1, 3)
        base_pct = 100 // n
        remainder = 100 - base_pct * n
        for i in range(n):
            rel = random.choice(["child", "sibling", "niece/nephew", "parent", "charity"])
            pct = base_pct + (remainder if i == 0 else 0)
            primaries.append({
                "name":         fake.name() if rel != "charity" else fake.company(),
                "relationship": rel,
                "percentage":   pct,
                "type":         "primary",
            })

    return primaries + contingents


def _make_estate_docs(flags: set[str]) -> dict:
    outdated = "outdated_estate" in flags

    def _doc_entry(years_min: int, years_max: int, can_be_missing: bool = False) -> dict:
        if can_be_missing and random.random() < 0.15:
            return {"status": "missing", "date_executed": None, "attorney": None}
        days = random.randint(max(30, years_min * 365), max(60, years_max * 365))
        executed = TODAY - timedelta(days=days)
        status = "outdated" if days > 3 * 365 else "current"
        return {
            "status":        status,
            "date_executed": executed.isoformat(),
            "attorney":      f"{fake.last_name()} & {fake.last_name()} LLP",
        }

    if outdated:
        # Force both will and trust to be outdated (>3 years)
        will_days   = random.randint(3 * 365 + 60, 8 * 365)
        trust_days  = random.randint(3 * 365 + 60, 8 * 365)
        poa_days    = random.randint(500, 4 * 365)
        hcd_days    = random.randint(500, 4 * 365)
        atty        = f"{fake.last_name()} & {fake.last_name()} LLP"
        return {
            "will": {
                "status":        "outdated",
                "date_executed": (TODAY - timedelta(days=will_days)).isoformat(),
                "attorney":      atty,
            },
            "trust": {
                "status":        "outdated",
                "date_executed": (TODAY - timedelta(days=trust_days)).isoformat(),
                "trust_type":    random.choice(["revocable", "irrevocable"]),
                "attorney":      atty,
            },
            "power_of_attorney": _doc_entry(1, 4),
            "healthcare_directive": _doc_entry(1, 4, can_be_missing=True),
        }
    else:
        # Non-flagged clients: docs reviewed within the past 1-3 years (current)
        return {
            "will":               _doc_entry(0, 3),
            "trust":              _doc_entry(0, 3) if random.random() > 0.3 else {"status": "missing", "date_executed": None, "attorney": None},
            "power_of_attorney":  _doc_entry(0, 3),
            "healthcare_directive": _doc_entry(0, 3, can_be_missing=True),
        }


def _make_life_events(
    age: int,
    flags: set[str],
    occupation: str,
    employer: str,
) -> list[dict]:
    events: list[dict] = []

    def _event(etype: str, days_min: int, days_max: int, resolved: bool = True) -> dict:
        evt_date = TODAY - timedelta(days=random.randint(days_min, days_max))
        descriptions = {
            "retirement":         f"Retired from {employer} after {random.randint(15, 35)} years of service.",
            "job_change":         f"Transitioned to new role as {occupation}.",
            "marriage":           f"Married {fake.first_name()} {fake.last_name()}.",
            "divorce":            "Finalized divorce settlement; assets divided per court order.",
            "death_of_spouse":    "Spouse passed away; estate in probate. Beneficiary updates required.",
            "death_of_parent":    "Parent passed away; potential inheritance pending estate settlement.",
            "new_child":          "New child welcomed into family; 529 plan funding discussion needed.",
            "college_start":      "Dependent started college; 529 distributions began.",
            "college_graduation": "Dependent graduated; 529 account to be wound down.",
            "home_purchase":      f"Purchased new primary residence in {fake.city()}, {fake.state_abbr()}.",
            "business_sale":      "Sold business interest — significant liquidity event requiring tax planning.",
            "inheritance":        "Received inheritance from family estate; assets need to be integrated.",
            "health_diagnosis":   "Received significant health diagnosis; long-term-care planning required.",
            "relocation":         f"Relocated to {fake.city()}, {fake.state_abbr()}.",
        }
        financial_impacts = {
            "retirement":         "Major income change — transitioning to distribution phase.",
            "job_change":         "Income change; 401(k) rollover may be needed.",
            "marriage":           "Beneficiary updates and combined financial plan required.",
            "divorce":            "QDRO processing needed; portfolio restructuring underway.",
            "death_of_spouse":    "Estate settlement ongoing; retitle accounts and update beneficiaries.",
            "death_of_parent":    "Inherited IRA rules apply; RMD schedule to be established.",
            "new_child":          "529 funding and life insurance review recommended.",
            "college_start":      "Coordinate 529 distributions with financial aid awards.",
            "college_graduation": "Review cash flow now that education costs are ending.",
            "home_purchase":      "Review liquidity and mortgage interest deductibility.",
            "business_sale":      "Capital gains planning and reinvestment strategy required.",
            "inheritance":        "Review step-up in basis; integrate with existing portfolio.",
            "health_diagnosis":   "Review long-term-care insurance and advance directives.",
            "relocation":         "Review state tax implications of new domicile.",
        }
        return {
            "type":             etype,
            "date":             evt_date.isoformat(),
            "description":      descriptions.get(etype, etype),
            "financial_impact": financial_impacts.get(etype, ""),
            "resolved":         resolved,
        }

    # Mandatory: major life event in last 90 days for flagged clients
    if "recent_life" in flags:
        if "death_of_spouse" in flags or "widowed" in str(flags):
            events.append(_event("death_of_spouse", 10, 88, resolved=False))
        elif age >= 60:
            events.append(_event("retirement", 10, 88, resolved=False))
        else:
            evt = random.choice(["new_child", "marriage", "job_change", "home_purchase"])
            events.append(_event(evt, 10, 88, resolved=False))

    # Background events from the past 1-3 years
    background_pool = [
        ("retirement",         365, 3 * 365, age >= 58),
        ("job_change",         180, 2 * 365, age < 60),
        ("college_start",      180, 2 * 365, 35 <= age <= 55),
        ("college_graduation", 180, 2 * 365, 35 <= age <= 55),
        ("home_purchase",      180, 3 * 365, True),
        ("death_of_parent",    180, 3 * 365, age >= 45),
        ("inheritance",        180, 3 * 365, age >= 45),
        ("relocation",         180, 2 * 365, True),
    ]
    eligible = [e for e in background_pool if e[3]]
    num_extra = random.randint(1, 3)
    for etype, dmin, dmax, _ in random.sample(eligible, min(num_extra, len(eligible))):
        # Skip if we already added a recent event of same type
        if not any(e["type"] == etype for e in events):
            events.append(_event(etype, dmin, dmax, resolved=True))

    # Sort newest first
    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:4]  # max 4 per spec


def _make_action_items(
    flags: set[str],
    age: int,
    rmd_eligible: bool,
    qcd_eligible: bool,
    tier: str,
) -> list[dict]:
    items: list[dict] = []
    ai_counter = [0]

    def _item(priority: str, category: str, description: str, days_due: int = 30) -> dict:
        ai_counter[0] += 1
        due = (TODAY + timedelta(days=days_due)).isoformat()
        return {
            "id":          f"AI{ai_counter[0]:03d}",
            "priority":    priority,
            "category":    category,
            "description": description,
            "due_date":    due,
            "status":      "pending",
        }

    if "overdue_rmd" in flags and rmd_eligible:
        items.append(_item("critical", "RMD",
            "2026 RMD not yet distributed — calculate amount and initiate withdrawal immediately.",
            days_due=7))

    if "drift" in flags:
        items.append(_item("high", "REBALANCING",
            "Portfolio allocation has drifted >5% from target. Prepare rebalancing trade list.",
            days_due=14))

    if "tlh" in flags:
        items.append(_item("high", "TAX_PLANNING",
            "Tax-loss harvesting opportunity identified — review unrealized losses in taxable accounts before year-end.",
            days_due=21))

    if "outdated_estate" in flags:
        items.append(_item("high", "ESTATE_PLANNING",
            "Estate documents (will, trust) last reviewed >3 years ago. Schedule attorney review.",
            days_due=60))

    if "recent_life" in flags:
        items.append(_item("high", "LIFE_EVENT",
            "Major life event requires immediate action: update beneficiaries, re-evaluate coverage, and adjust plan.",
            days_due=14))

    if qcd_eligible and age >= 71:
        items.append(_item("medium", "QCD",
            f"QCD strategy available — up to $111,000 (2026 limit) may be donated directly from IRA.",
            days_due=90))

    # Pad to 1-3 items with routine items
    routine = [
        ("low",    "REVIEW",       "Annual portfolio review and investment policy statement update.",  180),
        ("low",    "INSURANCE",    "Review life, disability, and long-term-care insurance coverage.", 90),
        ("medium", "BENEFICIARY",  "Verify beneficiary designations are current on all accounts.",    60),
        ("low",    "TAX_PLANNING", "Gather tax documents and coordinate with CPA for 2025 filing.",   45),
    ]
    random.shuffle(routine)
    while len(items) < 1:
        p, cat, desc, due = routine.pop()
        items.append(_item(p, cat, desc, due))

    return items[:3]  # cap at 3


def _estimate_rmd(ira_balance: float, age: int) -> float | None:
    period = ULT.get(age)
    if period is None:
        return None
    return round(ira_balance / period, 2)


# ── Main generator ────────────────────────────────────────────────────────────

def build_client(idx: int, template: tuple) -> dict:
    tier, birth_year, marital_status, risk_profile, flags = template

    # Randomise birth month/day for realism
    birth_month = random.randint(1, 12)
    birth_day   = random.randint(1, 28)
    age = _age(birth_year, birth_month, birth_day)

    # Personal identity
    gender = random.choice(["M", "F"])
    if gender == "M":
        first_name = fake.first_name_male()
    else:
        first_name = fake.first_name_female()
    last_name = fake.last_name()
    full_name = f"{first_name} {last_name}"

    # Spouse
    spouse: dict | None = None
    if "married" in flags:
        spouse_gender = "F" if gender == "M" else "M"
        spouse_fn     = fake.first_name_female() if spouse_gender == "F" else fake.first_name_male()
        spouse_by     = birth_year + random.randint(-5, 5)
        spouse_bm     = random.randint(1, 12)
        spouse_bd     = random.randint(1, 28)
        spouse = {
            "name":          f"{spouse_fn} {last_name}",
            "date_of_birth": date(spouse_by, spouse_bm, spouse_bd).isoformat(),
            "age":           _age(spouse_by, spouse_bm, spouse_bd),
        }

    # AUM range by tier
    aum_ranges = {
        "A": (1_000_000,  5_000_000),
        "B": (500_000,      999_000),
        "C": (200_000,      499_000),
        "D": (30_000,       199_000),
    }
    lo, hi = aum_ranges[tier]
    aum = round(random.uniform(lo, hi), 2)

    # Occupation / income by age
    if age >= 65:
        occupation = random.choice(["Retired", "Semi-Retired Consultant", "Retired Executive",
                                    "Retired Physician", "Retired Attorney", "Retired Engineer"])
        employer   = "Retired" if "Retired" in occupation else fake.company()
        income     = round(random.uniform(40_000, 200_000), 2)   # SS + pension + portfolio income
    elif age >= 45:
        occupation = random.choice(["VP Finance", "Senior Director", "Physician", "Attorney",
                                    "Business Owner", "Hospital Administrator", "CFO",
                                    "Software Engineering Manager", "Dentist", "Accountant"])
        employer   = fake.company()
        income     = round(random.uniform(120_000, 450_000), 2)
    else:
        occupation = random.choice(["Software Engineer", "Marketing Manager", "Nurse Practitioner",
                                    "Attorney", "Financial Analyst", "Sales Director",
                                    "Product Manager", "Architect", "Physician Resident"])
        employer   = fake.company()
        income     = round(random.uniform(60_000, 200_000), 2)

    # Risk score (1-10) aligned with profile
    risk_score_map = {
        "conservative": random.randint(1, 3),
        "moderate":     random.randint(3, 5),
        "balanced":     random.randint(4, 6),
        "growth":       random.randint(6, 8),
        "aggressive":   random.randint(8, 10),
    }
    risk_score = risk_score_map[risk_profile]

    # Allocations
    target_alloc  = RISK_PROFILES[risk_profile]
    if "drift" in flags:
        current_alloc = _drift_allocation(target_alloc)
        max_drift = max(abs(current_alloc.get(ac, 0) - target_alloc.get(ac, 0))
                        for ac in target_alloc)
    else:
        # Small random noise ±2% — within threshold
        noise = {ac: pct + random.uniform(-2, 2) for ac, pct in target_alloc.items()}
        total = sum(noise.values())
        current_alloc = {ac: round(v / total * 100, 1) for ac, v in noise.items()}
        max_drift = max(abs(current_alloc.get(ac, 0) - target_alloc.get(ac, 0))
                        for ac in target_alloc)

    portfolio_drift_details = {
        ac: round(current_alloc.get(ac, 0) - target_alloc.get(ac, 0), 1)
        for ac in target_alloc
    }

    # Accounts
    cid = f"CLT{idx + 1:03d}"
    accounts = _make_accounts(tier, birth_year, age, aum, flags)
    for i, acct in enumerate(accounts):
        acct["account_id"] = f"{cid}-{acct['account_type'].replace(' ', '_').replace('(', '').replace(')', '').upper()[:6]}-{i+1}"

    # RMD
    rmd_age_val = _rmd_age(birth_year)
    is_rmd_eligible = _rmd_eligible(age, birth_year)
    ira_balance = sum(
        a["balance"] for a in accounts
        if a["account_type"] in ("Traditional IRA", "SEP IRA")
    )
    rmd_amount = _estimate_rmd(ira_balance, age) if is_rmd_eligible else None
    rmd_taken  = False if "overdue_rmd" in flags else (
        random.random() < 0.7 if is_rmd_eligible else False
    )

    # QCD
    is_qcd = _qcd_eligible(birth_year, birth_month, birth_day) or "qcd" in flags
    qcd_amount_gifted = (
        round(random.uniform(5_000, 80_000), 2) if is_qcd and random.random() < 0.5 else 0
    )

    # Meetings
    meeting_freq_map = {"A": "quarterly", "B": "tri-annually", "C": "semi-annually", "D": "annually"}
    meeting_freq_days = {"A": 90, "B": 120, "C": 180, "D": 365}
    days_since = random.randint(20, meeting_freq_days[tier] + 10)
    last_meeting  = _rand_date(days_since, days_since)
    next_meeting  = _next_meeting(tier, last_meeting)
    client_since  = _rand_date(2 * 365, 15 * 365)

    # Subcomponents
    beneficiaries = _make_beneficiaries(marital_status)
    estate_docs   = _make_estate_docs(flags)
    life_events   = _make_life_events(age, flags, occupation, employer)

    any_doc_outdated = any(
        d.get("status") == "outdated"
        for d in estate_docs.values()
        if isinstance(d, dict)
    )

    is_roth_candidate = (
        is_rmd_eligible is False
        and age >= 55
        and income < 200_000
        and risk_profile in ("conservative", "moderate")
    )

    action_items = _make_action_items(flags, age, is_rmd_eligible, is_qcd, tier)

    advisor_notes_pool = [
        f"Client prefers {random.choice(['email', 'phone call', 'in-person'])} communication.",
        f"Met at {fake.company()} referral network event.",
        f"Client is very {random.choice(['hands-on', 'hands-off', 'detail-oriented'])} with portfolio decisions.",
        f"Spouse {random.choice(['is involved', 'is not involved'])} in financial discussions.",
        f"Tax returns filed with {fake.last_name()} CPA, {fake.city()}.",
    ]

    return {
        # Identity
        "id":                    cid,
        "name":                  full_name,
        "first_name":            first_name,
        "last_name":             last_name,
        "gender":                gender,
        "date_of_birth":         date(birth_year, birth_month, birth_day).isoformat(),
        "age":                   age,
        "marital_status":        marital_status,
        "spouse":                spouse,
        "address": {
            "street": fake.street_address(),
            "city":   fake.city(),
            "state":  fake.state_abbr(),
            "zip":    fake.zipcode(),
        },
        "email":                 f"{first_name.lower()}.{last_name.lower()}@{fake.free_email_domain()}",
        "phone":                 fake.phone_number(),
        # Financial profile
        "tier":                  tier,
        "aum":                   aum,
        "occupation":            occupation,
        "employer":              employer,
        "annual_income":         income,
        "tax_bracket":           _tax_bracket(income),
        "risk_tolerance":        risk_profile,
        "risk_score":            risk_score,
        # Allocations
        "target_allocation":     target_alloc,
        "current_allocation":    current_alloc,
        "portfolio_drift":       portfolio_drift_details,
        "max_drift_pct":         round(max_drift, 1),
        "has_portfolio_drift":   max_drift > 5.0,
        # Accounts
        "accounts":              accounts,
        "total_account_balance": round(sum(a["balance"] for a in accounts), 2),
        # RMD
        "rmd_eligible":          is_rmd_eligible,
        "rmd_age":               rmd_age_val,
        "rmd_amount_estimated":  rmd_amount,
        "rmd_taken_this_year":   rmd_taken,
        "rmd_overdue":           is_rmd_eligible and not rmd_taken,
        # QCD — IRS limit $111,000 (2026)
        "qcd_eligible":          is_qcd,
        "qcd_limit_2026":        111_000 if is_qcd else None,
        "qcd_amount_gifted_ytd": qcd_amount_gifted if is_qcd else None,
        # Planning flags
        "roth_conversion_candidate":       is_roth_candidate,
        "tax_loss_harvesting_opportunity": "tlh" in flags,
        # Beneficiaries & estate
        "beneficiaries":         beneficiaries,
        "estate_documents":      estate_docs,
        "estate_docs_outdated":  any_doc_outdated,
        # Life events & engagement
        "life_events":           life_events,
        "has_recent_life_event": any(
            (TODAY - date.fromisoformat(e["date"])).days <= 90
            for e in life_events
        ),
        "last_meeting_date":       last_meeting,
        "next_scheduled_meeting":  next_meeting,
        "meeting_frequency":       meeting_freq_map[tier],
        "client_since":            client_since,
        "open_action_items":       action_items,
        "advisor_notes":           random.choice(advisor_notes_pool),
    }


def main() -> None:
    clients: list[dict] = []
    for i, template in enumerate(CLIENT_TEMPLATES):
        client = build_client(i, template)
        clients.append(client)

    # ── Write output ──────────────────────────────────────────────────────
    out_path = os.path.join(DATA_DIR, "clients.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(clients, fh, indent=2, default=str)

    # ── Summary stats ─────────────────────────────────────────────────────
    tier_counts  = {t: sum(1 for c in clients if c["tier"] == t) for t in "ABCD"}
    rmd_count    = sum(1 for c in clients if c["rmd_eligible"])
    rmd_overdue  = sum(1 for c in clients if c.get("rmd_overdue"))
    qcd_count    = sum(1 for c in clients if c["qcd_eligible"])
    drift_count  = sum(1 for c in clients if c["has_portfolio_drift"])
    tlh_count    = sum(1 for c in clients if c["tax_loss_harvesting_opportunity"])
    estate_old   = sum(1 for c in clients if c["estate_docs_outdated"])
    life_recent  = sum(1 for c in clients if c["has_recent_life_event"])
    married_ct   = sum(1 for c in clients if c["marital_status"] == "married")

    age_30_44 = sum(1 for c in clients if 30 <= c["age"] <= 44)
    age_45_64 = sum(1 for c in clients if 45 <= c["age"] <= 64)
    age_65_85 = sum(1 for c in clients if 65 <= c["age"] <= 85)

    sep = "-" * 50
    print("\n" + sep)
    print(f"  clients.json -> {out_path}")
    print(sep)
    print(f"  Total clients:              {len(clients)}")
    print(f"  Tier A / B / C / D:         {tier_counts['A']} / {tier_counts['B']} / {tier_counts['C']} / {tier_counts['D']}")
    print(f"  Age 30-44 / 45-64 / 65-85:  {age_30_44} / {age_45_64} / {age_65_85}")
    print(f"  RMD-eligible:               {rmd_count}   (target >=8)")
    print(f"  RMD overdue:                {rmd_overdue}   (target >=3)")
    print(f"  QCD-eligible:               {qcd_count}   (target >=5)")
    print(f"  Portfolio drift >5%:        {drift_count}   (target >=5)")
    print(f"  TLH opportunities:          {tlh_count}   (target >=4)")
    print(f"  Outdated estate docs:       {estate_old}   (target >=2)")
    print(f"  Recent life events (90d):   {life_recent}   (target >=3)")
    print(f"  Married clients:            {married_ct}   (target >=10)")
    print(sep + "\n")


if __name__ == "__main__":
    main()
