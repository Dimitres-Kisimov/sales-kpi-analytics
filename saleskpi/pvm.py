"""pvm.py — the revenue price/volume/mix (PVM) bridge.

The "why did revenue move?" question every sales/finance team asks at a QBR.
This decomposes the **year-on-year revenue change** (last 12 months vs the prior
12) into three effects that reconcile *exactly* to the total change:

    price   = Σ (price_now − price_prior) · units_now          # realised-price change
    volume  = revenue_prior · (units_now / units_prior − 1)    # proportional growth
    mix     = total change − price − volume                    # the standard residual

where price per category is the *realised* average price, revenue ÷ units. The
"quantity effect" a two-way split would call volume — Σ (units_now − units_prior)
· price_prior — is here split into a **pure-volume** part (everything growing at
the prior blended price and mix) and a **mix** part (the reallocation of demand
towards higher- or lower-priced categories). Taking mix as the residual makes it
identically the textbook mix term Σ price_priorᵢ · (units_nowᵢ − λ·units_priorᵢ),
with λ = total-units_now / total-units_prior, and guarantees

    price + volume + mix == current_revenue − prior_revenue     (to the cent)

which a test asserts exactly.

This is a *revenue* bridge and is deliberately distinct from
`metrics.margin_bridge`, which decomposes the gross-*margin* change: revenue teams
and margin teams ask different questions, and the two bridges answer each.

All figures come from the synthetic 24-month order table; pure stdlib.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

Rows = list[dict[str, Any]]


def _yoy_split(rows: Rows) -> tuple[str, str, Rows, Rows]:
    """(prior_label, current_label, prior_rows, current_rows) for a last-12 vs
    prior-12 comparison, keyed off the latest month present in the data."""
    mx = max(r["date"] for r in rows)
    d = date.fromisoformat(mx)
    cut12 = f"{d.year - 1}-{d.month:02d}"     # last 12 months are strictly after this
    cut24 = f"{d.year - 2}-{d.month:02d}"     # prior 12 months are this-exclusive..cut12
    current = [r for r in rows if r["date"][:7] > cut12]
    prior = [r for r in rows if cut24 < r["date"][:7] <= cut12]

    def span(rs: Rows) -> str:
        ms = [r["date"][:7] for r in rs]
        return f"{min(ms)}..{max(ms)}" if ms else ""

    return span(prior), span(current), prior, current


def _agg(rows: Rows, dim: str) -> dict[str, dict[str, float]]:
    g: dict[str, dict[str, float]] = defaultdict(lambda: {"units": 0.0, "rev": 0.0})
    for r in rows:
        g[r[dim]]["units"] += r["units"]
        g[r[dim]]["rev"] += r["revenue_eur"]
    return g


def revenue_bridge(rows: Rows, dim: str = "product_category") -> dict[str, Any]:
    """Decompose the YoY revenue change into price / volume / mix, per `dim`.

    Returns rounded, JSON-ready euro figures plus a per-category breakdown whose
    columns sum to the headline effects. `mix` is the residual, so
    ``price + volume + mix == total_change`` holds exactly to the cent.
    """
    prior_label, current_label, prior, current = _yoy_split(rows)
    if not prior or not current:
        return {"available": False, "reason": "need 24 months (last-12 vs prior-12)"}

    a0, a1 = _agg(prior, dim), _agg(current, dim)
    q0_tot = sum(v["units"] for v in a0.values())
    q1_tot = sum(v["units"] for v in a1.values())
    r0_tot = sum(v["rev"] for v in a0.values())
    r1_tot = sum(v["rev"] for v in a1.values())
    lam = (q1_tot / q0_tot) if q0_tot else 1.0     # total-volume growth factor

    by_cat: list[dict[str, Any]] = []
    price_tot = volume_tot = 0.0
    for key in sorted(set(a0) | set(a1)):
        q0 = a0.get(key, {}).get("units", 0.0)
        q1 = a1.get(key, {}).get("units", 0.0)
        rev0 = a0.get(key, {}).get("rev", 0.0)
        rev1 = a1.get(key, {}).get("rev", 0.0)
        p0 = (rev0 / q0) if q0 else 0.0
        p1 = (rev1 / q1) if q1 else 0.0
        price_i = (p1 - p0) * q1               # realised-price change on current units
        volume_i = rev0 * (lam - 1.0)          # proportional growth at prior price+mix
        mix_i = (rev1 - rev0) - price_i - volume_i   # residual = standard mix term
        price_tot += price_i
        volume_tot += volume_i
        by_cat.append({
            dim: key,
            "prior_units": int(round(q0)),
            "current_units": int(round(q1)),
            "prior_price_eur": round(p0, 4),
            "current_price_eur": round(p1, 4),
            "prior_revenue_eur": round(rev0, 2),
            "current_revenue_eur": round(rev1, 2),
            "price_effect_eur": round(price_i, 2),
            "volume_effect_eur": round(volume_i, 2),
            "mix_effect_eur": round(mix_i, 2),
        })
    by_cat.sort(key=lambda d: -d["current_revenue_eur"])

    total = r1_tot - r0_tot
    price_r = round(price_tot, 2)
    volume_r = round(volume_tot, 2)
    total_r = round(total, 2)
    # mix as the residual of the *rounded* effects, so the three tie out to the
    # cent by construction (price_r + volume_r + mix_r == total_r exactly).
    mix_r = round(total_r - price_r - volume_r, 2)

    return {
        "available": True,
        "dimension": dim,
        "period_prior": prior_label,
        "period_current": current_label,
        "prior_revenue_eur": round(r0_tot, 2),
        "current_revenue_eur": round(r1_tot, 2),
        "total_change_eur": total_r,
        "total_change_pct": round(100 * total / r0_tot, 2) if r0_tot else 0.0,
        "price_effect_eur": price_r,
        "volume_effect_eur": volume_r,
        "mix_effect_eur": mix_r,
        "prior_units": int(round(q0_tot)),
        "current_units": int(round(q1_tot)),
        "volume_growth_pct": round(100 * (lam - 1.0), 2),
        "by_category": by_cat,
    }


def plain_language(bridge: dict[str, Any]) -> str:
    """A one-line read of the bridge in words, e.g.
    'Revenue rose €722,407: price +€16,048, volume +€1,381,732, mix −€675,373.'"""
    if not bridge.get("available"):
        return "Revenue bridge unavailable (needs 24 months of history)."
    t = bridge["total_change_eur"]
    verb = "rose" if t >= 0 else "fell"

    def eur(v: float) -> str:
        return f"{'+' if v >= 0 else '−'}€{abs(v):,.0f}"

    return (f"Revenue {verb} €{abs(t):,.0f} year-on-year: "
            f"price {eur(bridge['price_effect_eur'])}, "
            f"volume {eur(bridge['volume_effect_eur'])}, "
            f"mix {eur(bridge['mix_effect_eur'])}.")


def bridge_waterfall_steps(bridge: dict[str, Any]) -> list[dict[str, Any]]:
    """The ordered bars a revenue-bridge waterfall draws — the single source of
    truth the SVG and the tests consume, so the picture cannot drift from the
    numbers. Two totals sit on the baseline; the three effects float between the
    running totals:

        prior + price + volume + mix == current
    """
    prior = bridge["prior_revenue_eur"]
    price = bridge["price_effect_eur"]
    volume = bridge["volume_effect_eur"]
    mix = bridge["mix_effect_eur"]
    current = bridge["current_revenue_eur"]

    steps = [{"label": "Prior revenue", "kind": "total",
              "value": prior, "bottom": 0.0, "height": prior}]
    run = prior
    for label, val in (("Price", price), ("Volume", volume), ("Mix", mix)):
        nxt = run + val
        steps.append({
            "label": label,
            "kind": "increase" if val >= 0 else "decrease",
            "value": val,
            "bottom": min(run, nxt),
            "height": abs(val),
        })
        run = nxt
    steps.append({"label": "Current revenue", "kind": "total",
                  "value": current, "bottom": 0.0, "height": current})
    return steps
