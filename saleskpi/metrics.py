"""metrics.py — the distributor KPI engine.

Industry metrics a wholesale/MRO distributor actually manages, computed from the
transaction table:

  * headline: revenue, gross margin & margin %, contribution, AOV, orders, units
  * growth: YoY and MoM on the monthly revenue series
  * mix: revenue + margin % by region / category / channel / rep
  * commercial quality: discount leakage, returns rate
  * service: OTIF (on-time-in-full), on-time %, fill rate
  * portfolio: ABC (Pareto by revenue) x XYZ (demand variability) classification
  * customers: RFM segmentation + concentration (Pareto share)
  * margin bridge: price / volume / mix decomposition of a YoY margin change

Pure stdlib. Every function takes the loaded rows (see dataset.load).

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from .dataset import month_of, monthly_series


# --------------------------------------------------------------------------- #
# Headline KPIs
# --------------------------------------------------------------------------- #
def kpi_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rev = sum(r["revenue_eur"] for r in rows)
    cost = sum(r["cost_eur"] for r in rows)
    margin = rev - cost
    orders = len(rows)
    units = sum(r["units"] for r in rows)
    gross_list = sum(r["units"] * r["list_price_eur"] for r in rows)
    discount_leak = (gross_list - rev) / gross_list if gross_list else 0.0
    otif = sum(r["on_time"] and r["in_full"] for r in rows) / orders if orders else 0.0
    return {
        "revenue_eur": round(rev, 2),
        "cost_eur": round(cost, 2),
        "gross_margin_eur": round(margin, 2),
        "gross_margin_pct": round(100 * margin / rev, 2) if rev else 0.0,
        "orders": orders,
        "units": units,
        "aov_eur": round(rev / orders, 2) if orders else 0.0,
        "avg_order_margin_eur": round(margin / orders, 2) if orders else 0.0,
        "discount_leakage_pct": round(100 * discount_leak, 2),
        "otif_pct": round(100 * otif, 2),
        "on_time_pct": round(100 * sum(r["on_time"] for r in rows) / orders, 2) if orders else 0.0,
        "fill_rate_pct": round(100 * sum(r["in_full"] for r in rows) / orders, 2) if orders else 0.0,
        "returns_rate_pct": round(100 * sum(r["returned"] for r in rows) / orders, 2) if orders else 0.0,
        "active_customers": len({r["customer_id"] for r in rows}),
    }


def growth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """YoY (last 12m vs prior 12m) and latest MoM revenue growth."""
    series = monthly_series(rows, "revenue_eur")
    vals = [v for _, v in series]
    out: dict[str, Any] = {"months": len(series)}
    if len(vals) >= 2:
        out["mom_pct"] = round(100 * (vals[-1] - vals[-2]) / vals[-2], 2) if vals[-2] else None
    if len(vals) >= 24:
        last12, prev12 = sum(vals[-12:]), sum(vals[-24:-12])
        out["yoy_pct"] = round(100 * (last12 - prev12) / prev12, 2) if prev12 else None
    return out


# --------------------------------------------------------------------------- #
# Mix by dimension
# --------------------------------------------------------------------------- #
def by_dimension(rows: list[dict[str, Any]], dim: str) -> list[dict[str, Any]]:
    g: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue_eur": 0.0, "margin_eur": 0.0, "orders": 0})
    for r in rows:
        g[r[dim]]["revenue_eur"] += r["revenue_eur"]
        g[r[dim]]["margin_eur"] += r["margin_eur"]
        g[r[dim]]["orders"] += 1
    out = []
    for k, v in g.items():
        out.append({dim: k, "revenue_eur": round(v["revenue_eur"], 2),
                    "margin_pct": round(100 * v["margin_eur"] / v["revenue_eur"], 2) if v["revenue_eur"] else 0.0,
                    "orders": int(v["orders"])})
    out.sort(key=lambda d: -d["revenue_eur"])
    return out


# --------------------------------------------------------------------------- #
# ABC x XYZ portfolio classification
# --------------------------------------------------------------------------- #
def abc_xyz(rows: list[dict[str, Any]], entity: str = "product_category",
            abc_cuts: tuple[float, float] = (0.8, 0.95),
            xyz_cuts: tuple[float, float] = (0.5, 1.0)) -> list[dict[str, Any]]:
    """ABC (Pareto share of revenue: A up to 80%, B to 95%, C rest) x
    XYZ (coefficient of variation of monthly demand: X<0.5 steady, Y<1.0, Z erratic)."""
    rev: dict[str, float] = defaultdict(float)
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        e = r[entity]
        rev[e] += r["revenue_eur"]
        monthly[e][month_of(r)] += r["revenue_eur"]
    total = sum(rev.values())
    ranked = sorted(rev.items(), key=lambda kv: -kv[1])
    out, cum = [], 0.0
    n_months = len({month_of(r) for r in rows})
    for e, v in ranked:
        cum += v
        share = cum / total if total else 1.0
        abc = "A" if share <= abc_cuts[0] else "B" if share <= abc_cuts[1] else "C"
        vals = [monthly[e].get(m, 0.0) for m in sorted({month_of(r) for r in rows})]
        # pad to full month count so absent months count as zero demand
        vals += [0.0] * (n_months - len(vals))
        mean = statistics.mean(vals) if vals else 0.0
        cv = (statistics.pstdev(vals) / mean) if mean else float("inf")
        xyz = "X" if cv < xyz_cuts[0] else "Y" if cv < xyz_cuts[1] else "Z"
        out.append({entity: e, "revenue_eur": round(v, 2),
                    "revenue_share_pct": round(100 * v / total, 2) if total else 0.0,
                    "abc": abc, "cv": round(cv, 3), "xyz": xyz, "class": abc + xyz})
    return out


# --------------------------------------------------------------------------- #
# Customer analytics — RFM + concentration
# --------------------------------------------------------------------------- #
def rfm(rows: list[dict[str, Any]], as_of: str | None = None) -> list[dict[str, Any]]:
    """Recency (days since last order), Frequency (orders), Monetary (revenue)
    per customer, each scored 1-5 by quintile, with a segment label."""
    from datetime import date
    all_dates = [r["date"] for r in rows]
    ref = date.fromisoformat(as_of or max(all_dates))
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"last": "0000-01-01", "freq": 0, "mon": 0.0})
    for r in rows:
        c = agg[r["customer_id"]]
        c["freq"] += 1
        c["mon"] += r["revenue_eur"]
        if r["date"] > c["last"]:
            c["last"] = r["date"]
    custs = []
    for cid, c in agg.items():
        recency = (ref - date.fromisoformat(c["last"])).days
        custs.append({"customer_id": cid, "recency_days": recency,
                      "frequency": c["freq"], "monetary_eur": round(c["mon"], 2)})

    def score(values: list[float], reverse: bool) -> dict[int, int]:
        order = sorted(range(len(values)), key=lambda i: values[i], reverse=reverse)
        out = {}
        n = len(order)
        for rank, idx in enumerate(order):
            out[idx] = 5 - min(4, rank * 5 // n)     # 5 best .. 1 worst
        return out

    r_s = score([c["recency_days"] for c in custs], reverse=True)   # low recency = better
    f_s = score([c["frequency"] for c in custs], reverse=False)
    m_s = score([c["monetary_eur"] for c in custs], reverse=False)
    for i, c in enumerate(custs):
        c["R"], c["F"], c["M"] = r_s[i], f_s[i], m_s[i]
        c["rfm_score"] = c["R"] + c["F"] + c["M"]
        if c["R"] >= 4 and c["F"] >= 4:
            c["segment"] = "Champions"
        elif c["R"] >= 3 and c["M"] >= 4:
            c["segment"] = "Loyal / high-value"
        elif c["R"] <= 2 and c["F"] >= 3:
            c["segment"] = "At risk"
        elif c["R"] <= 2:
            c["segment"] = "Churned / dormant"
        else:
            c["segment"] = "Developing"
    custs.sort(key=lambda c: -c["monetary_eur"])
    return custs


def concentration(rows: list[dict[str, Any]], top_pct: float = 0.2) -> dict[str, Any]:
    """Share of revenue from the top X% of customers (Pareto concentration)."""
    rev: dict[str, float] = defaultdict(float)
    for r in rows:
        rev[r["customer_id"]] += r["revenue_eur"]
    ranked = sorted(rev.values(), reverse=True)
    total = sum(ranked)
    k = max(1, int(len(ranked) * top_pct))
    return {"customers": len(ranked), "top_pct": top_pct,
            "top_share_pct": round(100 * sum(ranked[:k]) / total, 2) if total else 0.0}


# --------------------------------------------------------------------------- #
# Margin bridge — price / volume / mix decomposition (YoY)
# --------------------------------------------------------------------------- #
def margin_bridge(rows: list[dict[str, Any]], dim: str = "product_category") -> dict[str, Any]:
    """Decompose the YoY gross-margin change into price, volume and mix effects,
    comparing the last 12 months to the prior 12. A classic commercial bridge."""
    from datetime import date
    mx = max(r["date"] for r in rows)
    cutoff = date.fromisoformat(mx).replace(day=1)
    y_cut = f"{cutoff.year - 1}-{cutoff.month:02d}"
    last = [r for r in rows if r["date"][:7] > _minus12(mx)]
    prev = [r for r in rows if _minus24(mx) < r["date"][:7] <= _minus12(mx)]
    if not prev or not last:
        return {"available": False, "reason": "need 24 months"}

    def agg(rs):
        g = defaultdict(lambda: {"units": 0, "margin": 0.0, "rev": 0.0})
        for r in rs:
            g[r[dim]]["units"] += r["units"]
            g[r[dim]]["margin"] += r["margin_eur"]
            g[r[dim]]["rev"] += r["revenue_eur"]
        return g

    a0, a1 = agg(prev), agg(last)
    price = volume = mix = 0.0
    for k in set(a0) | set(a1):
        u0, u1 = a0.get(k, {}).get("units", 0), a1.get(k, {}).get("units", 0)
        mpu0 = (a0.get(k, {}).get("margin", 0.0) / u0) if u0 else 0.0
        mpu1 = (a1.get(k, {}).get("margin", 0.0) / u1) if u1 else 0.0
        price += (mpu1 - mpu0) * u1                        # unit-margin change on new volume
        volume += mpu0 * (u1 - u0)                         # volume change at old unit margin
    m0 = sum(v["margin"] for v in a0.values())
    m1 = sum(v["margin"] for v in a1.values())
    mix = (m1 - m0) - price - volume                       # residual = mix/other
    return {"available": True, "period_from": y_cut, "prior_margin_eur": round(m0, 2),
            "current_margin_eur": round(m1, 2), "total_change_eur": round(m1 - m0, 2),
            "price_effect_eur": round(price, 2), "volume_effect_eur": round(volume, 2),
            "mix_effect_eur": round(mix, 2)}


def _minus12(ymd: str) -> str:
    from datetime import date
    d = date.fromisoformat(ymd)
    return f"{d.year - 1}-{d.month:02d}"


def _minus24(ymd: str) -> str:
    from datetime import date
    d = date.fromisoformat(ymd)
    return f"{d.year - 2}-{d.month:02d}"
