"""Portfolio Drift Calculator.

Rule: Alert when any major asset class drifts >5% absolute from target allocation.
Source: Standard IPS (Investment Policy Statement) drift thresholds.

Rebalancing trade suggestions consider:
  - Tax impact: prefer rebalancing in tax-advantaged accounts first
  - Short-term vs long-term capital gains in taxable accounts
  - Contribution/withdrawal routing before selling to minimize taxes
"""
from __future__ import annotations

import json
from typing import Any

from strands import tool

# Drift threshold per CLAUDE.md domain rules
DRIFT_THRESHOLD_PCT = 5.0

# Asset class labels used throughout the system
ASSET_CLASSES = [
    "US_EQUITY", "INTL_EQUITY", "US_BOND", "INTL_BOND", "REAL_ESTATE", "COMMODITIES",
]

# Typical representative ETFs per asset class (for trade suggestions)
_CLASS_ETFS: dict[str, list[str]] = {
    "US_EQUITY":    ["VTI", "SCHB", "IWV"],
    "INTL_EQUITY":  ["VXUS", "SPDW", "EFA"],
    "US_BOND":      ["BND", "AGG", "SCHZ"],
    "INTL_BOND":    ["BNDX", "IAGG", "IGIB"],
    "REAL_ESTATE":  ["VNQ", "SCHH", "IYR"],
    "COMMODITIES":  ["GLD", "IAU", "PDBC"],
}


def _tax_impact_note(gain_loss: float, holding_period_days: int, is_taxable: bool) -> str:
    """Return a plain-English note on the tax impact of selling this position."""
    if not is_taxable:
        return "No immediate tax impact (tax-advantaged account)"
    if gain_loss >= 0:
        # Gain — distinguish short vs long term
        if holding_period_days < 365:
            return (
                f"SHORT-TERM GAIN ${gain_loss:,.0f} — taxed as ordinary income. "
                "Consider deferring sale or rebalancing via new contributions."
            )
        return (
            f"LONG-TERM GAIN ${gain_loss:,.0f} — preferential LTCG rates apply. "
            "Rebalancing is tax-efficient relative to short-term gains."
        )
    return (
        f"UNREALIZED LOSS ${abs(gain_loss):,.0f} — selling realizes a loss "
        "that can offset gains (potential TLH opportunity)."
    )


def _suggest_trades(
    drifts: list[dict[str, Any]],
    total_portfolio_value: float,
) -> list[dict[str, Any]]:
    """Generate specific buy/sell trade suggestions to restore target allocation."""
    trades = []
    for d in drifts:
        if not d["action_required"]:
            continue
        asset_class = d["asset_class"]
        drift_pct = d["drift_pct"]          # positive = overweight, negative = underweight
        dollar_delta = abs(d["current_value"] - d["target_value"])
        etfs = _CLASS_ETFS.get(asset_class, [asset_class])

        if drift_pct > 0:
            # Overweight — sell
            trades.append({
                "action": "SELL",
                "asset_class": asset_class,
                "amount": round(dollar_delta, 2),
                "pct_of_portfolio": round(dollar_delta / total_portfolio_value * 100, 2),
                "suggested_ticker": etfs[0],
                "note": (
                    f"{asset_class} is {drift_pct:+.1f}% above target. "
                    f"Sell ~${dollar_delta:,.0f} of {etfs[0]} (or equivalent). "
                    "Prefer selling from tax-advantaged accounts to avoid taxable gains."
                ),
            })
        else:
            # Underweight — buy
            trades.append({
                "action": "BUY",
                "asset_class": asset_class,
                "amount": round(dollar_delta, 2),
                "pct_of_portfolio": round(dollar_delta / total_portfolio_value * 100, 2),
                "suggested_ticker": etfs[0],
                "note": (
                    f"{asset_class} is {drift_pct:+.1f}% below target. "
                    f"Buy ~${dollar_delta:,.0f} of {etfs[0]} (or equivalent). "
                    "Route new contributions here first before selling other positions."
                ),
            })
    return trades


@tool
def calculate_portfolio_drift(holdings_json: str, target_allocation_json: str) -> str:
    """Analyze portfolio drift versus the client's Investment Policy Statement target allocation.

    Computes the current percentage allocation per asset class from holdings, compares
    against the target, and flags any asset class with absolute drift > 5% (per IPS standard).
    Suggests specific rebalancing trades and notes the tax impact of selling positions
    in taxable accounts (short-term vs long-term capital gains, or loss harvesting).

    Args:
        holdings_json: JSON array of holding objects, each with fields:
            - ticker (str): Security ticker symbol.
            - asset_class (str): One of US_EQUITY, INTL_EQUITY, US_BOND, INTL_BOND,
              REAL_ESTATE, COMMODITIES.
            - current_value (float): Current market value in dollars.
            - unrealized_gain_loss (float, optional): Unrealized gain (positive) or
              loss (negative) on the position. Default 0.
            - holding_period_days (int, optional): Days held; used to determine
              short-term vs long-term classification for tax purposes. Default 365.
            - account_type (str, optional): "taxable" or any other value (tax-advantaged).
              Only taxable accounts trigger capital gain tax impact notes. Default "taxable".

        target_allocation_json: JSON object mapping asset class names to target percentages
            (must sum to 100). Example: {"US_EQUITY": 60, "INTL_EQUITY": 15, ...}

    Returns:
        JSON string with fields:
            - total_portfolio_value (float): Sum of all holding values.
            - drifts (list): Per-asset-class breakdown with fields:
                asset_class, target_pct, current_pct, drift_pct, current_value,
                target_value, drift_amount, action_required (bool), status (str).
            - rebalancing_needed (bool): True if any class exceeds 5% drift threshold.
            - max_drift_pct (float): Largest absolute drift observed.
            - suggested_trades (list): Buy/sell actions to restore target allocation.
            - tax_impact_notes (list): Tax impact per holding for positions in taxable accounts.
            - explanation (str): Plain-English summary for the advisor.
    """
    holdings: list[dict] = json.loads(holdings_json)
    targets: dict[str, float] = json.loads(target_allocation_json)

    # Aggregate current value per asset class
    class_values: dict[str, float] = {ac: 0.0 for ac in ASSET_CLASSES}
    total_value = 0.0
    tax_notes: list[dict] = []

    for h in holdings:
        ac = h.get("asset_class", "")
        val = float(h.get("current_value", 0.0))
        class_values[ac] = class_values.get(ac, 0.0) + val
        total_value += val

        # Tax impact note for meaningful positions in taxable accounts
        is_taxable = str(h.get("account_type", "taxable")).lower() == "taxable"
        gain_loss = float(h.get("unrealized_gain_loss", 0.0))
        if is_taxable and abs(gain_loss) > 100:
            period_days = int(h.get("holding_period_days", 365))
            tax_notes.append({
                "ticker": h.get("ticker", "?"),
                "asset_class": ac,
                "unrealized_gain_loss": gain_loss,
                "holding_period_days": period_days,
                "tax_note": _tax_impact_note(gain_loss, period_days, is_taxable),
            })

    if total_value == 0:
        return json.dumps({"error": "Portfolio has zero total value — cannot compute drift."})

    # Compute drift per asset class
    drifts: list[dict] = []
    max_drift = 0.0
    rebalancing_needed = False

    for ac in ASSET_CLASSES:
        target_pct = float(targets.get(ac, 0.0))
        current_pct = round(class_values.get(ac, 0.0) / total_value * 100, 2)
        drift_pct = round(current_pct - target_pct, 2)   # positive = overweight
        abs_drift = abs(drift_pct)
        target_value = round(total_value * target_pct / 100, 2)
        current_value = round(class_values.get(ac, 0.0), 2)
        action_required = abs_drift > DRIFT_THRESHOLD_PCT

        if abs_drift > max_drift:
            max_drift = abs_drift
        if action_required:
            rebalancing_needed = True

        if action_required:
            status = "REBALANCE — exceeds 5% drift threshold"
        elif abs_drift > 2.5:
            status = "MONITOR — approaching threshold"
        else:
            status = "OK"

        drifts.append({
            "asset_class": ac,
            "target_pct": target_pct,
            "current_pct": current_pct,
            "drift_pct": drift_pct,
            "current_value": current_value,
            "target_value": target_value,
            "drift_amount": round(current_value - target_value, 2),
            "action_required": action_required,
            "status": status,
        })

    suggested_trades = _suggest_trades(drifts, total_value)

    rebalance_classes = [d["asset_class"] for d in drifts if d["action_required"]]
    explanation = (
        f"Portfolio total value: ${total_value:,.2f}. "
        f"Max absolute drift: {max_drift:.1f}%. "
    )
    if rebalancing_needed:
        explanation += (
            f"REBALANCING REQUIRED for: {', '.join(rebalance_classes)}. "
            f"{len(suggested_trades)} trade(s) suggested to restore target allocation. "
            "Prefer rebalancing within tax-advantaged accounts first to minimize tax drag."
        )
    else:
        explanation += "All asset classes are within the 5% drift threshold. No rebalancing needed."

    return json.dumps({
        "total_portfolio_value": round(total_value, 2),
        "drifts": drifts,
        "rebalancing_needed": rebalancing_needed,
        "max_drift_pct": round(max_drift, 2),
        "suggested_trades": suggested_trades,
        "tax_impact_notes": tax_notes,
        "explanation": explanation,
    })
