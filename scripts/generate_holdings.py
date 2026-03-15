"""Generate holdings, transactions, and market_events JSON data files.

Reads backend/app/data/clients.json, produces:
  backend/app/data/holdings.json      — one record per holding line item
  backend/app/data/transactions.json  — 5-10 recent transactions per client
  backend/app/data/market_events.json — 5 curated market events

Usage:
    cd wealth-radar
    python scripts/generate_holdings.py
"""
from __future__ import annotations

import json
import os
import random
from datetime import date, timedelta

SEED = 42
random.seed(SEED)

TODAY    = date(2026, 3, 8)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data")

# ── ETF universe: ticker → (name, asset_class, price_march_2026) ─────────────
ETFS: dict[str, tuple[str, str, float]] = {
    "VTI":  ("Vanguard Total Stock Market ETF",                 "US_EQUITY",   285.40),
    "SCHD": ("Schwab US Dividend Equity ETF",                   "US_EQUITY",    83.20),
    "QQQ":  ("Invesco QQQ Trust ETF",                           "US_EQUITY",   527.50),
    "VO":   ("Vanguard Mid-Cap ETF",                            "US_EQUITY",   267.30),
    "VB":   ("Vanguard Small-Cap ETF",                          "US_EQUITY",   231.80),
    "VIG":  ("Vanguard Dividend Appreciation ETF",              "US_EQUITY",   186.40),
    "IWM":  ("iShares Russell 2000 ETF",                        "US_EQUITY",   216.70),
    "VXUS": ("Vanguard Total International Stock ETF",          "INTL_EQUITY",  65.10),
    "VEA":  ("Vanguard FTSE Developed Markets ETF",             "INTL_EQUITY",  52.30),
    "IEMG": ("iShares Core MSCI Emerging Markets ETF",          "INTL_EQUITY",  57.80),
    "VWO":  ("Vanguard FTSE Emerging Markets ETF",              "INTL_EQUITY",  45.20),
    "BND":  ("Vanguard Total Bond Market ETF",                  "US_BOND",      73.80),
    "AGG":  ("iShares Core US Aggregate Bond ETF",              "US_BOND",      96.40),
    "VCSH": ("Vanguard Short-Term Corp Bond ETF",               "US_BOND",      78.20),
    "VGSH": ("Vanguard Short-Term Treasury ETF",                "US_BOND",      57.90),
    "BSV":  ("Vanguard Short-Term Bond ETF",                    "US_BOND",      77.40),
    "LQD":  ("iShares iBoxx IG Corp Bond ETF",                  "US_BOND",     108.30),
    "VTIP": ("Vanguard Short-Term TIPS ETF",                    "US_BOND",      50.10),
    "TIP":  ("iShares TIPS Bond ETF",                           "US_BOND",     110.20),
    "BNDX": ("Vanguard Total International Bond ETF",           "INTL_BOND",    48.30),
    "VNQ":  ("Vanguard Real Estate ETF",                        "REAL_ESTATE",  95.60),
    "VNQI": ("Vanguard Global ex-US Real Estate ETF",           "REAL_ESTATE",  47.80),
    "GLD":  ("SPDR Gold Shares ETF",                            "COMMODITIES", 221.40),
    "IAU":  ("iShares Gold Trust ETF",                          "COMMODITIES",  42.30),
    "PDBC": ("Invesco Optimum Yield Diversified Commodity ETF", "COMMODITIES",  14.70),
}

# Core ETF per asset class (always chosen first), then optionals
AC_CORE: dict[str, str] = {
    "US_EQUITY":   "VTI",
    "INTL_EQUITY": "VXUS",
    "US_BOND":     "BND",
    "INTL_BOND":   "BNDX",
    "REAL_ESTATE": "VNQ",
    "COMMODITIES": "GLD",
}
AC_OPTIONAL: dict[str, list[str]] = {
    "US_EQUITY":   ["SCHD", "VIG", "VO", "VB", "QQQ", "IWM"],
    "INTL_EQUITY": ["VEA", "IEMG", "VWO"],
    "US_BOND":     ["AGG", "VTIP", "VCSH", "VGSH", "BSV", "LQD", "TIP"],
    "INTL_BOND":   [],
    "REAL_ESTATE": ["VNQI"],
    "COMMODITIES": ["IAU", "PDBC"],
}

# Tickers that suffered losses in the Feb–Mar 2026 correction (for TLH)
# structure: asset_class → list of (ticker, target_loss_$)
TLH_LOSS_SEEDS: dict[str, list[tuple[str, float]]] = {
    "US_EQUITY":   [("QQQ", -5_800), ("IWM", -1_900), ("VB", -2_400)],
    "INTL_EQUITY": [("IEMG", -4_600), ("VWO", -3_100), ("VEA", -1_600)],
    "US_BOND":     [("BND", -3_400), ("LQD", -2_100)],
    "COMMODITIES": [("GLD", -4_100), ("PDBC", -2_300)],
}

ALL_ASSET_CLASSES = list(AC_CORE.keys())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rand_date(days_min: int, days_max: int) -> str:
    d = TODAY - timedelta(days=random.randint(days_min, days_max))
    return d.isoformat()


def _pick_etfs_for_class(ac: str, n_extra: int = 1) -> list[str]:
    """Return [core_etf] + up to n_extra optional ETFs."""
    core     = AC_CORE[ac]
    optional = AC_OPTIONAL.get(ac, [])
    chosen   = random.sample(optional, min(n_extra, len(optional)))
    return [core] + chosen


def _cost_ratio(is_taxable: bool, tlh: bool = False) -> float:
    """
    Return cost_basis / current_value ratio.
    - Normal (long-term gain):  0.55 – 0.90  → gain
    - Taxable with no TLH:      0.80 – 1.05  → small gains / flat
    - TLH (intentional loss):   caller sets directly
    """
    if tlh:
        return 1.0  # placeholder; caller overrides
    if is_taxable:
        return random.uniform(0.80, 1.05)
    return random.uniform(0.55, 0.90)


def _holding(
    client_id: str,
    account_id: str,
    account_type: str,
    is_taxable: bool,
    ticker: str,
    current_value: float,
    cost_ratio: float | None = None,
    holding_period_days: int | None = None,
    wash_sale: bool = False,
) -> dict:
    name, ac, price = ETFS[ticker]
    ratio = cost_ratio if cost_ratio is not None else _cost_ratio(is_taxable)
    cost  = round(current_value * ratio, 2)
    pnl   = round(current_value - cost, 2)
    days  = holding_period_days if holding_period_days is not None else random.randint(90, 2000)
    shares = round(current_value / price, 4)
    return {
        "client_id":           client_id,
        "account_id":          account_id,
        "account_type":        account_type,
        "ticker":              ticker,
        "name":                name,
        "asset_class":         ac,
        "shares":              shares,
        "price":               price,
        "cost_basis_per_share":round(cost / shares, 4) if shares else 0,
        "cost_basis_total":    cost,
        "current_value":       round(current_value, 2),
        "unrealized_gain_loss":pnl,
        "weight":              0.0,          # filled in after all holdings built
        "holding_period_days": days,
        "wash_sale_flag":      wash_sale,
    }


def _assign_weights(holdings: list[dict]) -> None:
    total = sum(h["current_value"] for h in holdings)
    if total == 0:
        return
    for h in holdings:
        h["weight"] = round(h["current_value"] / total * 100, 2)


# ── Per-account holdings builder ──────────────────────────────────────────────

def build_account_holdings(
    client_id:   str,
    account:     dict,
    alloc:       dict[str, float],   # current_allocation (may be drifted)
    is_tlh:      bool,
    wash_tickers: set[str],          # tickers that should get wash_sale_flag
) -> list[dict]:
    acct_id    = account["account_id"]
    acct_type  = account["account_type"]
    is_taxable = account["is_taxable"]
    balance    = account["balance"]

    holdings: list[dict] = []
    reserved_tickers: set[str] = set()  # prevent duplicate tickers

    # Track allocated value so we can assign the remainder to the last holding
    allocated_value = 0.0

    for ac, pct in alloc.items():
        if pct < 0.5:
            continue
        ac_value = balance * pct / 100.0
        if ac_value < 200:
            continue

        # How many ETFs for this class?
        n_extra = 0 if ac_value < 5_000 else random.randint(0, 2)
        tickers = [t for t in _pick_etfs_for_class(ac, n_extra) if t not in reserved_tickers]
        if not tickers:
            continue

        # Split ac_value among chosen tickers
        if len(tickers) == 1:
            splits = [1.0]
        else:
            raw    = [random.random() for _ in tickers]
            total  = sum(raw)
            splits = [r / total for r in raw]
            # Ensure core ETF gets the largest share
            splits[0] = max(splits)

        for ticker, split in zip(tickers, splits):
            etf_value = ac_value * split
            if etf_value < 100:
                continue
            reserved_tickers.add(ticker)
            ws = ticker in wash_tickers
            h = _holding(client_id, acct_id, acct_type, is_taxable,
                         ticker, etf_value, wash_sale=ws)
            holdings.append(h)
            allocated_value += etf_value

    # TLH: add specific loss positions in taxable accounts
    if is_tlh and is_taxable and holdings:
        # Pick 2 asset classes at random that had correction losses
        candidate_classes = [ac for ac in ["US_EQUITY", "INTL_EQUITY", "US_BOND", "COMMODITIES"]
                             if ac in alloc and alloc[ac] > 1.0]
        random.shuffle(candidate_classes)
        injected = 0
        for ac in candidate_classes[:2]:
            pool = [p for p in TLH_LOSS_SEEDS.get(ac, []) if p[0] not in reserved_tickers]
            if not pool:
                continue
            ticker, target_loss = random.choice(pool)
            reserved_tickers.add(ticker)
            # current_value between $8k-$30k; cost_basis = current + |loss|
            cv   = random.uniform(8_000, 30_000)
            cost = cv + abs(target_loss) * random.uniform(0.9, 1.1)
            ratio = cost / cv
            h = _holding(client_id, acct_id, acct_type, is_taxable,
                         ticker, cv, cost_ratio=ratio,
                         holding_period_days=random.randint(45, 400))
            h["unrealized_gain_loss"] = round(cv - cost, 2)  # ensure negative
            holdings.append(h)
            injected += 1

        # Optionally add a wash-sale flagged holding (sold at loss, repurchased)
        if injected and random.random() < 0.5:
            ws_pools = [p for ac in candidate_classes[:1]
                        for p in TLH_LOSS_SEEDS.get(ac, [])
                        if p[0] not in reserved_tickers]
            if ws_pools:
                ws_ticker, ws_loss = random.choice(ws_pools)
                reserved_tickers.add(ws_ticker)
                cv   = random.uniform(5_000, 15_000)
                cost = cv + abs(ws_loss) * random.uniform(0.8, 1.0)
                ratio = cost / cv
                h = _holding(client_id, acct_id, acct_type, is_taxable,
                             ws_ticker, cv, cost_ratio=ratio,
                             holding_period_days=random.randint(5, 55),
                             wash_sale=True)
                h["unrealized_gain_loss"] = round(cv - cost, 2)
                holdings.append(h)

    _assign_weights(holdings)
    return holdings


# ── Actual allocation per client (aggregated across all accounts) ─────────────

def compute_client_actual_alloc(all_holdings_for_client: list[dict]) -> dict[str, float]:
    total_val: float = sum(h["current_value"] for h in all_holdings_for_client)
    if total_val == 0:
        return {}
    ac_totals: dict[str, float] = {}
    for h in all_holdings_for_client:
        ac = h["asset_class"]
        ac_totals[ac] = ac_totals.get(ac, 0) + h["current_value"]
    return {ac: round(v / total_val * 100, 2) for ac, v in sorted(ac_totals.items())}


# ── Transactions ──────────────────────────────────────────────────────────────

def build_transactions(client: dict, all_account_ids: list[str]) -> list[dict]:
    count = random.randint(5, 10)
    txns: list[dict] = []
    all_tickers = list(ETFS.keys())

    for _ in range(count):
        ticker     = random.choice(all_tickers)
        name, ac, price = ETFS[ticker]
        price_used = round(price * random.uniform(0.93, 1.07), 2)

        tx_type = random.choices(
            ["buy", "sell", "dividend", "distribution"],
            weights=[40, 25, 30, 5],
        )[0]

        if tx_type in ("dividend", "distribution"):
            shares = round(random.uniform(0.10, 3.00), 4)
        else:
            shares = round(random.uniform(3, 100), 4)

        total  = round(shares * price_used, 2)
        days   = random.randint(1, 180)
        dt     = (TODAY - timedelta(days=days)).isoformat()

        txns.append({
            "client_id":    client["id"],
            "account_id":   random.choice(all_account_ids),
            "date":         dt,
            "ticker":       ticker,
            "name":         name,
            "asset_class":  ac,
            "type":         tx_type,
            "shares":       shares,
            "price":        price_used,
            "total_amount": total,
            "notes":        "",
        })

    return sorted(txns, key=lambda x: x["date"], reverse=True)


# ── Market events ─────────────────────────────────────────────────────────────

MARKET_EVENTS: list[dict] = [
    {
        "id":              "EVT001",
        "date":            "2026-02-18",
        "event_type":      "FED_RATE_DECISION",
        "title":           "Fed Holds at 4.50% — Signals Two Cuts in H2 2026",
        "description":     (
            "The Federal Reserve voted unanimously to hold the federal funds rate at "
            "4.25%–4.50%. Chair signaled two 25bp cuts likely in H2 2026. Bond markets "
            "rallied on the news: BND +0.4%, TIP +0.3%, VGSH +0.8%. REIT sector gained "
            "1.2% on lower rate expectations."
        ),
        "severity":        "MEDIUM",
        "affected_sectors":["US_BOND", "INTL_BOND", "REAL_ESTATE"],
        "affected_tickers":["BND", "AGG", "TIP", "VTIP", "BNDX", "VNQ"],
        "recommended_action": (
            "Review bond duration positioning for conservative/moderate clients. "
            "Roth conversion window may narrow if rate cuts push equities higher — "
            "accelerate conversions for ROTH_WINDOW clients now."
        ),
        "trigger_types":   ["ROTH_WINDOW", "PORTFOLIO_DRIFT"],
    },
    {
        "id":              "EVT002",
        "date":            "2026-02-28",
        "event_type":      "EQUITY_MARKET_CORRECTION",
        "title":           "S&P 500 -7.3% in Three Sessions — AI Valuation Reset",
        "description":     (
            "S&P 500 declined 7.3% over three sessions on AI chipmaker guidance cuts. "
            "QQQ fell 11.2%, IWM -4.1%, VTI -6.8%. Value and dividend stocks partially "
            "offset losses: SCHD -1.9%, VIG -2.4%. International equities outperformed "
            "on dollar weakness: VXUS -3.2%, VEA -2.8%."
        ),
        "severity":        "HIGH",
        "affected_sectors":["US_EQUITY", "INTL_EQUITY"],
        "affected_tickers":["VTI", "QQQ", "IWM", "VO", "VB", "VXUS", "IEMG", "VWO"],
        "recommended_action": (
            "Scan all taxable accounts for tax-loss harvesting — QQQ, IWM, VB "
            "are primary candidates. Review drift for growth/aggressive profiles. "
            "Accelerate Roth conversions for eligible clients at lower account values."
        ),
        "trigger_types":   ["TLH_OPPORTUNITY", "PORTFOLIO_DRIFT", "ROTH_WINDOW"],
    },
    {
        "id":              "EVT003",
        "date":            "2026-03-03",
        "event_type":      "INFLATION_DATA",
        "title":           "CPI 3.2% — Core Inflation Surprises to Upside",
        "description":     (
            "February CPI rose 3.2% YoY vs. 2.9% consensus. Core CPI ex-food/energy "
            "+3.6%. TIPS and VTIP rallied: TIP +0.9%, VTIP +0.6%. The 10-year Treasury "
            "yield spiked 18bp to 4.68%. Fixed income broadly sold off: BND -0.9%, "
            "AGG -1.0%, LQD -1.3%, BNDX -0.7%."
        ),
        "severity":        "HIGH",
        "affected_sectors":["US_BOND", "INTL_BOND", "COMMODITIES"],
        "affected_tickers":["BND", "AGG", "LQD", "BNDX", "TIP", "VTIP", "GLD", "IAU"],
        "recommended_action": (
            "Review TIPS/VTIP weighting for conservative clients — underweight "
            "inflation-protection is now a meaningful drag. Flag commodity allocation "
            "as inflation hedge. Re-evaluate near-term bond buys for clients with "
            "pending liquidity events (e.g. RMD proceeds)."
        ),
        "trigger_types":   ["PORTFOLIO_DRIFT", "RMD_DUE", "MARKET_EVENT"],
    },
    {
        "id":              "EVT004",
        "date":            "2026-03-05",
        "event_type":      "CURRENCY_MOVE",
        "title":           "Dollar Weakens 3.1% — DXY Falls to 102.4",
        "description":     (
            "US Dollar Index fell 3.1% on fiscal deficit concerns and hot CPI print. "
            "International equity positions received a currency tailwind: VXUS +2.8%, "
            "VEA +3.1%, IEMG +2.2%. Unhedged international bonds (BNDX) gained +1.6%. "
            "Dollar weakness also boosted commodity prices: GLD +1.4%."
        ),
        "severity":        "LOW",
        "affected_sectors":["INTL_EQUITY", "INTL_BOND", "COMMODITIES"],
        "affected_tickers":["VXUS", "VEA", "IEMG", "VWO", "BNDX", "VNQI", "GLD"],
        "recommended_action": (
            "Flag international equity rebalancing for clients underweight "
            "INTL_EQUITY — tailwind may reverse. Positive for clients already "
            "overweight international. Review rebalancing trigger thresholds."
        ),
        "trigger_types":   ["PORTFOLIO_DRIFT"],
    },
    {
        "id":              "EVT005",
        "date":            "2026-03-07",
        "event_type":      "GEOPOLITICAL_RISK",
        "title":           "Oil +8% on Strait of Hormuz Supply Disruption",
        "description":     (
            "Crude oil rose 8.2% to $89/barrel on reported supply disruptions. "
            "GLD rose 2.1% to $225/oz; IAU +2.0%. Energy-cost concerns hit REITs: "
            "VNQ -1.4%, VNQI -1.8%. Commodity positions outperformed broadly: "
            "PDBC +3.8%."
        ),
        "severity":        "MEDIUM",
        "affected_sectors":["COMMODITIES", "REAL_ESTATE"],
        "affected_tickers":["GLD", "IAU", "PDBC", "VNQ", "VNQI"],
        "recommended_action": (
            "Review commodity allocation for clients underweight GLD/IAU — recent "
            "rally highlights inflation-hedge gap. Re-examine REIT positions for "
            "income-focused clients given energy-cost headwinds. Flag inflation-hedge "
            "conversation for clients in or approaching retirement."
        ),
        "trigger_types":   ["PORTFOLIO_DRIFT", "MARKET_EVENT", "QCD_OPPORTUNITY"],
    },
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    clients_path = os.path.join(DATA_DIR, "clients.json")
    with open(clients_path, encoding="utf-8") as fh:
        clients: list[dict] = json.load(fh)

    all_holdings:    list[dict] = []
    all_transactions: list[dict] = []

    # Collect TLH and drift client IDs upfront
    tlh_client_ids  = {c["id"] for c in clients if c.get("tax_loss_harvesting_opportunity")}
    drift_client_ids = {c["id"] for c in clients if c.get("has_portfolio_drift")}

    # Wash-sale injection: pick 3 random TLH clients to also have wash-sale flags
    ws_client_ids = set(random.sample(sorted(tlh_client_ids), min(3, len(tlh_client_ids))))

    # Per-client actual allocation summary (written back to clients list for reference)
    client_alloc_summary: dict[str, dict[str, float]] = {}

    for client in clients:
        cid        = client["id"]
        is_tlh     = cid in tlh_client_ids
        alloc      = client["current_allocation"]   # may be drifted for drift clients
        accounts   = client["accounts"]
        ws_tickers: set[str] = set()

        client_holdings: list[dict] = []

        for acct in accounts:
            holdings = build_account_holdings(
                client_id    = cid,
                account      = acct,
                alloc        = alloc,
                is_tlh       = is_tlh,
                wash_tickers = ws_tickers,   # empty unless we assign below
            )
            # For wash-sale clients, flag one extra holding in their taxable account
            if cid in ws_client_ids and acct["is_taxable"] and not ws_tickers:
                # Pick the holding with the largest unrealised loss and flag it
                loss_holdings = [h for h in holdings if h["unrealized_gain_loss"] < -500]
                if loss_holdings:
                    target = min(loss_holdings, key=lambda h: h["unrealized_gain_loss"])
                    target["wash_sale_flag"] = True
                    ws_tickers.add(target["ticker"])

            all_holdings.extend(holdings)
            client_holdings.extend(holdings)

        client_alloc_summary[cid] = compute_client_actual_alloc(client_holdings)

        account_ids = [a["account_id"] for a in accounts]
        txns = build_transactions(client, account_ids)
        all_transactions.extend(txns)

    # ── Write files ───────────────────────────────────────────────────────────
    def write(filename: str, data: object) -> None:
        path = os.path.join(DATA_DIR, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        n = len(data) if isinstance(data, list) else "n/a"  # type: ignore[arg-type]
        print(f"  wrote {path}  ({n} records)")

    print("\nGenerating holdings, transactions, and market events...")
    write("holdings.json",      all_holdings)
    write("transactions.json",  all_transactions)
    write("market_events.json", MARKET_EVENTS)

    # ── Validation ────────────────────────────────────────────────────────────
    drift_accounts = {
        h["client_id"] for h in all_holdings
        if h["client_id"] in drift_client_ids
    }
    tlh_taxable_clients = {
        h["client_id"] for h in all_holdings
        if h["account_type"] in ("Joint Brokerage", "Individual Brokerage", "Trust Account")
        and h["unrealized_gain_loss"] < -1000
    }
    ws_count = sum(1 for h in all_holdings if h["wash_sale_flag"])

    sep = "-" * 52
    print("\n" + sep)
    print(f"  Total holding line items:       {len(all_holdings)}")
    print(f"  Total transactions:             {len(all_transactions)}")
    print(f"  Market events:                  {len(MARKET_EVENTS)}")
    print(f"  Avg holdings per account:       {len(all_holdings) / max(1, sum(len(c['accounts']) for c in clients)):.1f}")
    print(f"  Clients with portfolio drift:   {len(drift_accounts)}   (target >=5)")
    print(f"  Clients with TLH loss >$1k:     {len(tlh_taxable_clients)}   (target >=4)")
    print(f"  Wash-sale flagged holdings:     {ws_count}              (target >=1)")
    print(sep + "\n")


if __name__ == "__main__":
    main()
