"""generate_data.py — synthesize a realistic B2B distributor sales dataset.

Deterministic (fixed seed) so KPIs, the forecast and the tests are reproducible.
Models ~24 months of orders with plausible seasonality (spring/autumn peaks in
construction supply), a gentle upward trend, per-category margins, a stable
customer base (so retention/RFM are meaningful), discount leakage, delivery
performance (OTIF) and returns — the fields real distributor analytics need.

    python scripts/generate_data.py
Out: data/sales_transactions.csv

Columns: order_id, date, region, sales_rep, customer_id, customer_segment,
         product_category, channel, units, list_price_eur, discount_pct,
         revenue_eur, cost_eur, promised_lead_days, actual_lead_days,
         on_time, in_full, returned

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

SEED = 42
OUT = Path(__file__).resolve().parents[1] / "data" / "sales_transactions.csv"
START = date(2024, 1, 1)
MONTHS = 24

REGIONS = ["DACH-North", "DACH-South", "West", "East", "Nordics"]
REPS = {
    "DACH-North": ["Weber", "Klein", "Braun"], "DACH-South": ["Huber", "Mayer", "Fischer"],
    "West": ["Dubois", "Martin"], "East": ["Nowak", "Kovac"], "Nordics": ["Berg", "Lindqvist"],
}
SEGMENTS = ["Enterprise", "SMB", "Trade"]
CHANNELS = ["field-sales", "e-shop", "branch", "phone"]
# category -> (avg unit list price EUR, gross margin fraction, popularity weight)
CATEGORIES = {
    "fasteners": (0.9, 0.42, 5), "power tools": (140.0, 0.28, 2), "chemicals": (6.5, 0.46, 3),
    "ppe": (3.4, 0.38, 3), "hand tools": (24.0, 0.34, 2), "abrasives": (1.1, 0.44, 3),
}
SEASON = [0.82, 0.85, 1.02, 1.12, 1.18, 1.10, 0.95, 0.90, 1.15, 1.20, 1.05, 0.78]


def _weighted(rng: random.Random, choices: dict[str, tuple]) -> str:
    names = list(choices)
    return rng.choices(names, weights=[choices[n][2] for n in names], k=1)[0]


def _build_customers(rng: random.Random) -> list[dict]:
    """A fixed base of ~400 customers with a home region/segment and a loyalty
    factor — some churn over time, some are heavy repeat buyers (for RFM)."""
    custs = []
    for i in range(400):
        region = rng.choice(REGIONS)
        segment = rng.choices(SEGMENTS, weights=[2, 4, 3], k=1)[0]
        custs.append({
            "id": f"C{i:04d}", "region": region, "segment": segment,
            "loyalty": rng.betavariate(2, 2),          # 0..1 repeat propensity
            "churn_month": rng.randint(8, 40) if rng.random() < 0.18 else 99,  # some leave
            "start_month": rng.randint(0, 6) if rng.random() < 0.85 else rng.randint(0, MONTHS - 1),
        })
    return custs


def main() -> None:
    rng = random.Random(SEED)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    customers = _build_customers(rng)
    rows: list[dict] = []
    oid = 0
    for m in range(MONTHS):
        y = START.year + (START.month - 1 + m) // 12
        mo = (START.month - 1 + m) % 12 + 1
        trend = 1.0 + 0.010 * m
        season = SEASON[mo - 1]
        # active customers this month
        active = [c for c in customers if c["start_month"] <= m < c["churn_month"]]
        n_orders = int(560 * trend * season * rng.uniform(0.92, 1.08))
        for _ in range(n_orders):
            # pick a customer weighted by loyalty (repeat buyers dominate)
            cust = rng.choices(active, weights=[0.2 + c["loyalty"] for c in active], k=1)[0]
            oid += 1
            day = rng.randint(1, 28)
            region = cust["region"]
            rep = rng.choice(REPS[region])
            segment = cust["segment"]
            channel = rng.choices(CHANNELS, weights=[3, 4, 2, 1], k=1)[0]
            cat = _weighted(rng, CATEGORIES)
            price, margin, _ = CATEGORIES[cat]
            base_units = {"Enterprise": 220, "SMB": 60, "Trade": 25}[segment]
            units = max(1, int(rng.gauss(base_units, base_units * 0.4)))
            list_price = round(price * rng.uniform(0.9, 1.15), 4)
            # discount: bigger for Enterprise + e-shop promos -> margin leakage
            discount = round(min(0.35, max(0.0, rng.gauss(
                {"Enterprise": 0.14, "SMB": 0.07, "Trade": 0.05}[segment], 0.05))), 3)
            gross = units * list_price
            revenue = round(gross * (1 - discount), 2)
            eff_margin = margin - (0.03 if channel == "e-shop" else 0.0) + rng.uniform(-0.04, 0.04)
            eff_margin = min(0.65, max(0.03, eff_margin))
            cost = round(units * list_price * (1 - margin) * rng.uniform(0.95, 1.05), 2)
            promised = {"field-sales": 3, "e-shop": 2, "branch": 1, "phone": 3}[channel]
            # delivery performance degrades a little in peak months
            late_p = 0.10 + (0.06 if season > 1.12 else 0.0)
            actual = promised + (rng.randint(1, 4) if rng.random() < late_p else 0)
            on_time = actual <= promised
            in_full = rng.random() > 0.04
            returned = rng.random() < (0.03 if cat != "power tools" else 0.06)
            rows.append({
                "order_id": f"O{oid:06d}", "date": date(y, mo, day).isoformat(),
                "region": region, "sales_rep": rep, "customer_id": cust["id"],
                "customer_segment": segment, "product_category": cat, "channel": channel,
                "units": units, "list_price_eur": list_price, "discount_pct": discount,
                "revenue_eur": revenue, "cost_eur": cost,
                "promised_lead_days": promised, "actual_lead_days": actual,
                "on_time": int(on_time), "in_full": int(in_full), "returned": int(returned),
            })
    rows.sort(key=lambda r: (r["date"], r["order_id"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    rev = sum(r["revenue_eur"] for r in rows)
    otif = sum(r["on_time"] and r["in_full"] for r in rows) / len(rows)
    print(f"{len(rows)} orders, {MONTHS} months, {len({r['customer_id'] for r in rows})} customers, "
          f"{rev/1e6:.1f} M EUR revenue, OTIF {otif:.1%} -> {OUT}")


if __name__ == "__main__":
    main()
