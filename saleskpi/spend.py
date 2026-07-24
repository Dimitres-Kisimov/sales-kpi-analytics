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


def _list_value(r: dict[str, Any]) -> float:
    return r["units"] * r["list_price_eur"]


def discount_leakage(rows: Rows) -> float:
    """Money given away versus list price (list value minus actual revenue)."""
    return sum(_list_value(r) - r["revenue_eur"] for r in rows)


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
    }
