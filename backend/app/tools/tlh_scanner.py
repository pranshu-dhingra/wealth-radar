"""Tax-Loss Harvesting Scanner.

Rules (IRC §1091 — Wash Sale):
  - Only applicable in taxable accounts (never IRAs or 401ks).
  - Wash sale window: 30 days BEFORE and 30 days AFTER the sale (61-day total).
  - Flag opportunities where unrealized loss > $1,000.
  - Suggest a replacement security from a different ETF family to avoid wash sale.
  - Calculate estimated tax savings at the client's marginal bracket.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from strands import tool

# Minimum unrealized loss to flag as a TLH opportunity (per CLAUDE.md)
TLH_THRESHOLD = 1_000.0

# Wash-sale window: 61 days total (30 before + day of sale + 30 after)
# Source: IRC §1091(a)
WASH_SALE_WINDOW_DAYS = 30

# Account types that are TAXABLE (TLH applies only here)
# Source: IRS Pub. 550; TLH in IRAs is irrelevant (no deductible losses in IRAs)
TAXABLE_ACCOUNT_TYPES = {"taxable", "individual brokerage", "joint brokerage", "trust account"}

# Replacement security map — "substantially identical" must be avoided.
# Different-family ETFs tracking similar-but-not-identical indexes are generally
# NOT substantially identical per IRS guidance (though some ambiguity exists for
# funds tracking the same index). Use these with client/advisor discretion.
# Source: IRS Rev. Rul. 2008-5; IRC §1091(a)
REPLACEMENT_MAP: dict[str, dict] = {
    "VTI":   {"replacement": "SCHB",  "description": "Schwab US Broad Market ETF (CRSP US Total Market)"},
    "SCHB":  {"replacement": "VTI",   "description": "Vanguard Total Stock Market ETF (CRSP US Total Market)"},
    "QQQ":   {"replacement": "QQQM",  "description": "Invesco Nasdaq 100 ETF (same index — confirm not substantially identical; consider VUG)"},
    "SCHD":  {"replacement": "VYM",   "description": "Vanguard High Dividend Yield ETF (similar factor exposure)"},
    "VYM":   {"replacement": "SCHD",  "description": "Schwab US Dividend Equity ETF"},
    "VXUS":  {"replacement": "SPDW",  "description": "SPDR Portfolio Developed World ex-US ETF"},
    "SPDW":  {"replacement": "VXUS",  "description": "Vanguard Total International Stock ETF"},
    "IEMG":  {"replacement": "VWO",   "description": "Vanguard FTSE Emerging Markets ETF (FTSE vs MSCI index — not substantially identical)"},
    "VWO":   {"replacement": "IEMG",  "description": "iShares Core MSCI Emerging Markets ETF"},
    "BND":   {"replacement": "AGG",   "description": "iShares Core US Aggregate Bond ETF (Bloomberg US Agg — similar but different provider)"},
    "AGG":   {"replacement": "BND",   "description": "Vanguard Total Bond Market ETF"},
    "SCHZ":  {"replacement": "BND",   "description": "Vanguard Total Bond Market ETF"},
    "BNDX":  {"replacement": "IAGG",  "description": "iShares Core International Aggregate Bond ETF"},
    "IAGG":  {"replacement": "BNDX",  "description": "Vanguard Total International Bond ETF"},
    "VNQ":   {"replacement": "SCHH",  "description": "Schwab US REIT ETF"},
    "SCHH":  {"replacement": "VNQ",   "description": "Vanguard Real Estate ETF"},
    "GLD":   {"replacement": "IAU",   "description": "iShares Gold Trust (same underlying — confirm not substantially identical; consider GLDM)"},
    "IAU":   {"replacement": "GLDM",  "description": "SPDR Gold MiniShares (lower cost gold ETF)"},
    "VTIP":  {"replacement": "STIP",  "description": "iShares 0-5 Year TIPS Bond ETF"},
    "VEA":   {"replacement": "SPDW",  "description": "SPDR Portfolio Developed World ex-US ETF"},
    "VO":    {"replacement": "IJH",   "description": "iShares Core S&P Mid-Cap ETF"},
    "VB":    {"replacement": "IJR",   "description": "iShares Core S&P Small-Cap ETF"},
    "IWM":   {"replacement": "VB",    "description": "Vanguard Small-Cap ETF (Russell 2000 vs CRSP — not substantially identical)"},
    "VIG":   {"replacement": "DGRO",  "description": "iShares Core Dividend Growth ETF"},
}


def _wash_sale_window(sale_date: date) -> tuple[date, date]:
    """Return the 61-day wash sale window (30 days before to 30 days after)."""
    return sale_date - timedelta(days=WASH_SALE_WINDOW_DAYS), sale_date + timedelta(days=WASH_SALE_WINDOW_DAYS)


def _tax_savings(loss_amount: float, tax_bracket_pct: float) -> dict:
    """Estimate tax savings from harvesting a loss at the given bracket."""
    # Short-term losses offset ordinary income at marginal rate.
    # Long-term losses offset LTCG first (at preferential rates) then ordinary income.
    st_savings = round(loss_amount * (tax_bracket_pct / 100), 2)
    ltcg_rate = 0.20 if tax_bracket_pct >= 37 else (0.15 if tax_bracket_pct >= 22 else 0.0)
    lt_savings = round(loss_amount * ltcg_rate, 2)
    return {
        "loss_amount": round(loss_amount, 2),
        "marginal_bracket_pct": tax_bracket_pct,
        "st_loss_tax_savings": st_savings,
        "lt_loss_tax_savings": lt_savings,
        "note": (
            f"Short-term loss saves ${st_savings:,.2f} at {tax_bracket_pct}% bracket. "
            f"Long-term loss saves ${lt_savings:,.2f} at {ltcg_rate * 100:.0f}% LTCG rate. "
            "Losses first offset same-type gains; excess offsets other gains, then up to "
            "$3,000/yr of ordinary income (IRC §1211(b)); remainder carries forward."
        ),
    }


@tool
def scan_tax_loss_harvesting(holdings_json: str) -> str:
    """Scan a client's portfolio holdings for tax-loss harvesting (TLH) opportunities.

    Only analyzes positions in TAXABLE accounts (not IRAs or 401ks — TLH in tax-deferred
    accounts provides no benefit and losses cannot be deducted there). Flags positions
    with unrealized losses exceeding $1,000. For each opportunity, suggests a replacement
    security from a different ETF family to maintain market exposure while avoiding the
    61-day wash-sale window (IRC §1091). Calculates estimated tax savings at the client's
    marginal bracket for both short-term and long-term loss scenarios.

    Args:
        holdings_json: JSON string with fields:
            - holdings (list): Array of holding objects, each with:
                - ticker (str): Security ticker symbol.
                - account_type (str): Account type — only "taxable", "joint brokerage",
                  "individual brokerage", or "trust account" are scanned for TLH.
                - unrealized_gain_loss (float): Negative = unrealized loss (opportunity).
                - current_value (float): Current market value in dollars.
                - holding_period_days (int, optional): Days held. Under 365 = short-term loss.
                - purchase_date (str, optional): ISO date string of purchase. Used to check
                  whether a recent purchase might trigger a wash sale on prior sale.
                - wash_sale_flag (bool, optional): True if a wash-sale violation is already
                  flagged on this holding. Default False.
            - tax_bracket_pct (float, optional): Client's marginal federal tax bracket (e.g.
              24.0). Used to estimate tax savings. Default 24.0.
            - client_id (str, optional): Client identifier for the response.

    Returns:
        JSON string with fields:
            - client_id (str)
            - account_scanned_count (int): Number of taxable accounts/holdings scanned.
            - opportunities (list): TLH opportunities with fields:
                ticker, account_type, unrealized_loss, current_value, holding_period_days,
                is_short_term (bool), wash_sale_risk (bool), replacement_ticker,
                replacement_description, tax_savings (dict).
            - total_harvestable_loss (float): Sum of all flagged unrealized losses.
            - estimated_total_tax_savings (float): Estimated tax savings at client bracket.
            - warnings (list): Any wash-sale risks detected.
            - explanation (str): Plain-English summary for the advisor.
    """
    payload = json.loads(holdings_json)
    holdings: list[dict] = payload.get("holdings", payload) if isinstance(payload, dict) else payload
    tax_bracket = float(
        payload.get("tax_bracket_pct", 24.0) if isinstance(payload, dict) else 24.0
    )
    client_id = payload.get("client_id", "unknown") if isinstance(payload, dict) else "unknown"

    opportunities = []
    warnings = []
    total_loss = 0.0
    total_savings = 0.0
    scanned = 0
    today = date.today()

    for h in holdings:
        acc_type = str(h.get("account_type", "taxable")).lower()
        if acc_type not in TAXABLE_ACCOUNT_TYPES:
            # Skip tax-advantaged accounts — TLH only in taxable accounts
            continue

        scanned += 1
        gain_loss = float(h.get("unrealized_gain_loss", 0.0))

        if gain_loss >= -TLH_THRESHOLD:
            # Loss does not meet the $1,000 threshold
            continue

        ticker = str(h.get("ticker", "?"))
        loss_amount = abs(gain_loss)
        period_days = int(h.get("holding_period_days", 365))
        is_short_term = period_days < 365
        wash_sale_flag = bool(h.get("wash_sale_flag", False))

        # Check for wash-sale risk from recent purchases
        purchase_date_str = h.get("purchase_date")
        wash_sale_risk = wash_sale_flag
        if purchase_date_str and not wash_sale_risk:
            try:
                pdate = date.fromisoformat(purchase_date_str)
                wstart, wend = _wash_sale_window(today)
                if wstart <= pdate <= wend:
                    wash_sale_risk = True
            except ValueError:
                pass

        if wash_sale_risk:
            warnings.append({
                "ticker": ticker,
                "account_type": acc_type,
                "warning": (
                    f"WASH SALE RISK on {ticker}: a substantially identical security "
                    "was purchased within the 61-day window (30 days before/after sale). "
                    "Selling now would disallow the loss under IRC §1091. "
                    "Wait until the window clears or use a non-substantially-identical replacement."
                ),
            })

        # Replacement security
        replacement = REPLACEMENT_MAP.get(ticker, {})
        rep_ticker = replacement.get("replacement", "Similar ETF — consult advisor")
        rep_desc = replacement.get("description", "Maintain exposure with a non-substantially-identical security")

        savings = _tax_savings(loss_amount, tax_bracket)
        total_loss += loss_amount
        # Use short-term savings estimate as base (conservative; advisor adjusts for LT)
        total_savings += savings["st_loss_tax_savings"]

        opportunities.append({
            "ticker": ticker,
            "account_type": acc_type,
            "unrealized_loss": round(loss_amount, 2),
            "current_value": round(float(h.get("current_value", 0.0)), 2),
            "holding_period_days": period_days,
            "is_short_term": is_short_term,
            "wash_sale_risk": wash_sale_risk,
            "replacement_ticker": rep_ticker,
            "replacement_description": rep_desc,
            "tax_savings": savings,
            "action": (
                "SKIP — wash sale risk" if wash_sale_risk
                else f"HARVEST — sell {ticker}, buy {rep_ticker} immediately to maintain exposure"
            ),
        })

    opportunities.sort(key=lambda x: x["unrealized_loss"], reverse=True)

    explanation = (
        f"Client {client_id}: Scanned {scanned} taxable account holding(s). "
        f"Found {len(opportunities)} TLH opportunit(y/ies) with total harvestable "
        f"loss of ${total_loss:,.2f}. "
        f"Estimated tax savings at {tax_bracket}% bracket: ${total_savings:,.2f}. "
    )
    if warnings:
        explanation += f"{len(warnings)} wash-sale risk(s) flagged — review before trading. "
    if not opportunities:
        explanation += "No positions meet the $1,000 loss threshold in taxable accounts."
    else:
        explanation += (
            "Sell losers and immediately buy replacement securities to maintain market exposure. "
            "Complete the swap within the same trading day to avoid being out of the market. "
            "Losses carry forward indefinitely and can offset future gains (IRC §1212)."
        )

    return json.dumps({
        "client_id": client_id,
        "account_scanned_count": scanned,
        "opportunities": opportunities,
        "total_harvestable_loss": round(total_loss, 2),
        "estimated_total_tax_savings": round(total_savings, 2),
        "warnings": warnings,
        "explanation": explanation,
    })
