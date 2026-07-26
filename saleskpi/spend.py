"""spend.py — the expenditure side of the ledger.

I built the KPI engine around revenue first, then realised a distributor cares
just as much about where the money *goes*. This module answers that: total COGS,
how spend splits by category / region / channel, and a rough "cost-to-serve" per
channel that adds two leaks most P&Ls hide — returns and discount give-away.

Definitions I settled on (all stdlib, all from the order table):

    COGS              = sum(cost_eur)
    discount leakage  = sum(units * list_price_eur - revenue_eur)   # money vs list
    returns cost      = returns_rate * avg_order_cost * orders       # per group
    cost-to-serve     = COGS + returns cost + discount leakage       # per channel

The returns figure is deliberately a *model* (rate x average cost), not the exact
COGS of returned lines — the dataset doesn't carry restocking/handling cost, so a
rate-based proxy is the honest thing to report.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

Rows = list[dict[str, Any]]

# Discount-policy threshold used by the leakage drill-down. The dataset carries no
# explicit contract terms, so this is a stated modeling assumption, not a measured
# fact: discounts up to 10% of list are treated as sanctioned ("within policy"),
# anything above is "excess". The drill-down labels the split accordingly and the
# threshold is a parameter everywhere, so a real policy can be dropped in.
POLICY_DISCOUNT_PCT = 0.10


def _list_value(r: dict[str, Any]) -> float:
    return r["units"] * r["list_price_eur"]


def discount_leakage(rows: Rows) -> float:
    """Money given away versus list price (list value minus actual revenue)."""
    return sum(_list_value(r) - r["revenue_eur"] for r in rows)


def _row_discount_pct(r: dict[str, Any]) -> float:
    """The row's discount fraction — from the column when present, else derived."""
    if "discount_pct" in r:
        return float(r["discount_pct"])
    lv = _list_value(r)
    return (lv - r["revenue_eur"]) / lv if lv else 0.0


def _split_leakage(r: dict[str, Any], policy_pct: float) -> tuple[float, float]:
    """(row leakage, excess part of it). The row's leakage — list value minus
    revenue, the exact same definition `discount_leakage()` uses — is split
    proportionally by how far the discount sits above the policy threshold, so
    within-policy + excess always reconstructs the row's leakage to the cent."""
    leak = _list_value(r) - r["revenue_eur"]
    d = _row_discount_pct(r)
    if d > policy_pct and d > 0:
        return leak, leak * (d - policy_pct) / d
    return leak, 0.0


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def _leakage_by(rows: Rows, dim: str, policy_pct: float) -> list[dict[str, Any]]:
    """Leakage decomposed along one dimension, ranked worst-offender-first
    (by excess-over-policy EUR, ties broken by name for determinism)."""
    groups: dict[str, Rows] = defaultdict(list)
    for r in rows:
        groups[r[dim]].append(r)
    out = []
    for key in sorted(groups):
        grp = groups[key]
        leak = excess = 0.0
        discounts = []
        above = 0
        revenue = 0.0
        for r in grp:
            row_leak, row_excess = _split_leakage(r, policy_pct)
            leak += row_leak
            excess += row_excess
            d = _row_discount_pct(r)
            discounts.append(d)
            if d > policy_pct:
                above += 1
            revenue += r["revenue_eur"]
        discounts.sort()
        rec = {
            dim: key,
            "leakage_eur": round(leak, 2),
            "excess_eur": round(excess, 2),
            "within_policy_eur": round(leak - excess, 2),
            "revenue_eur": round(revenue, 2),
            "leakage_pct_of_revenue": round(100 * leak / revenue, 2) if revenue else 0.0,
            "orders": len(grp),
            "orders_above_policy_pct": round(100 * above / len(grp), 2) if grp else 0.0,
            "avg_discount_pct": round(100 * sum(discounts) / len(discounts), 2) if grp else 0.0,
            "median_discount_pct": round(100 * _percentile(discounts, 0.5), 2),
            "p90_discount_pct": round(100 * _percentile(discounts, 0.9), 2),
        }
        if dim == "sales_rep":
            rec["region"] = " / ".join(sorted({r["region"] for r in grp}))
        out.append(rec)
    out.sort(key=lambda d: (-d["excess_eur"], d[dim]))
    return out


def leakage_drilldown(rows: Rows, policy_pct: float = POLICY_DISCOUNT_PCT) -> dict[str, Any]:
    """WHO is leaking margin, and WHERE.

    Decomposes the headline discount leakage (list value minus revenue — the same
    number `discount_leakage()` reports) by sales rep and by region, and splits it
    into a within-policy part and an excess part against `policy_pct`. The pieces
    reconstruct the totals exactly:

        within_policy + excess               == total leakage
        gross list value - both discount cuts == net revenue
        sum over reps == sum over regions    == total leakage
    """
    total_leak = discount_leakage(rows)
    excess = sum(_split_leakage(r, policy_pct)[1] for r in rows)
    gross = sum(_list_value(r) for r in rows)
    net = sum(r["revenue_eur"] for r in rows)
    return {
        "policy_discount_pct": round(100 * policy_pct, 2),
        "policy_note": ("assumed sanctioned-discount ceiling (no contract terms in the "
                        "dataset); within-policy vs excess split depends on it, the "
                        "total leakage does not"),
        "gross_list_value_eur": round(gross, 2),
        "within_policy_discount_eur": round(total_leak - excess, 2),
        "excess_discount_eur": round(excess, 2),
        "net_revenue_eur": round(net, 2),
        "total_leakage_eur": round(total_leak, 2),
        "by_sales_rep": _leakage_by(rows, "sales_rep", policy_pct),
        "by_region": _leakage_by(rows, "region", policy_pct),
    }


def returns_cost(rows: Rows) -> float:
    """Modeled returns cost for a set of orders: returns_rate x avg order cost x orders."""
    n = len(rows)
    if not n:
        return 0.0
    returns_rate = sum(r["returned"] for r in rows) / n
    avg_cost = sum(r["cost_eur"] for r in rows) / n
    return returns_rate * avg_cost * n


def spend_by(rows: Rows, dim: str) -> list[dict[str, Any]]:
    """COGS grouped by a dimension, sorted high→low, with share of total spend."""
    g: dict[str, dict[str, float]] = defaultdict(lambda: {"cogs_eur": 0.0, "orders": 0})
    for r in rows:
        g[r[dim]]["cogs_eur"] += r["cost_eur"]
        g[r[dim]]["orders"] += 1
    total = sum(v["cogs_eur"] for v in g.values()) or 1.0
    out = [
        {
            dim: k,
            "cogs_eur": round(v["cogs_eur"], 2),
            "spend_share_pct": round(100 * v["cogs_eur"] / total, 2),
            "orders": int(v["orders"]),
        }
        for k, v in g.items()
    ]
    out.sort(key=lambda d: -d["cogs_eur"])
    return out


def cost_to_serve_by_channel(rows: Rows) -> list[dict[str, Any]]:
    """Per-channel COGS plus its returns and discount-leakage leaks = cost-to-serve."""
    by_channel: dict[str, Rows] = defaultdict(list)
    for r in rows:
        by_channel[r["channel"]].append(r)
    out = []
    for ch, grp in by_channel.items():
        cogs = sum(r["cost_eur"] for r in grp)
        ret = returns_cost(grp)
        leak = discount_leakage(grp)
        out.append({
            "channel": ch,
            "cogs_eur": round(cogs, 2),
            "returns_cost_eur": round(ret, 2),
            "discount_leakage_eur": round(leak, 2),
            "cost_to_serve_eur": round(cogs + ret + leak, 2),
            "orders": len(grp),
        })
    out.sort(key=lambda d: -d["cost_to_serve_eur"])
    return out


def spend_summary(rows: Rows) -> dict[str, Any]:
    """The whole expenditure picture in one dict (what report.analyze() consumes)."""
    total_cogs = sum(r["cost_eur"] for r in rows)
    list_value = sum(_list_value(r) for r in rows)
    leak = discount_leakage(rows)

    ret_by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        ret_by_cat[r["product_category"]].append(r)
    returns_by_category = sorted(
        (
            {"product_category": c, "returns_cost_eur": round(returns_cost(g), 2)}
            for c, g in ret_by_cat.items()
        ),
        key=lambda d: -d["returns_cost_eur"],
    )

    return {
        "total_cogs_eur": round(total_cogs, 2),
        "list_value_eur": round(list_value, 2),
        "discount_leakage_eur": round(leak, 2),
        "discount_leakage_pct": round(100 * leak / list_value, 2) if list_value else 0.0,
        "returns_cost_total_eur": round(returns_cost(rows), 2),
        "cogs_by_category": spend_by(rows, "product_category"),
        "cogs_by_region": spend_by(rows, "region"),
        "cogs_by_channel": spend_by(rows, "channel"),
        "returns_cost_by_category": returns_by_category,
        "cost_to_serve_by_channel": cost_to_serve_by_channel(rows),
        "leakage_drilldown": leakage_drilldown(rows),
    }
