"""build_star.py -- export the sales analytics as a Power BI star schema.

Power BI Desktop imports these CSVs and models them into a classic star:

    fact_sales_monthly  (grain = month x region x category x channel)
        |  date_key          -> dim_date[date_key]
        |  region            -> dim_region[region]
        |  product_category  -> dim_category[product_category]
        |  channel           -> dim_channel[channel]

plus a disconnected (metric, value) table `kpi_headline` for repo-level scalars
that have no cell grain (YoY, margin bridge, forecast CV-MASE, concentration).

Everything is computed by the repo's own modules (saleskpi.metrics, .spend,
.forecast) from the committed, seeded dataset -- SYNTHETIC data, deterministic
output. Run:

    python scripts/generate_data.py     # optional -- the CSV is committed
    python powerbi/build_star.py        # writes powerbi/data/*.csv

No Power BI licence or tenant is needed to *generate* the model -- the point of
this pack is to demonstrate dimensional modelling + DAX. See powerbi/README.md.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from saleskpi import metrics, spend  # noqa: E402
from saleskpi.dataset import load, month_of, monthly_series, months  # noqa: E402
from saleskpi.forecast import select_and_forecast  # noqa: E402

_OUT = Path(__file__).resolve().parent / "data"

_MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _date_key(label: str) -> int:
    return int(label.replace("-", "") + "01")


def _next_month(label: str) -> str:
    y, m = int(label[:4]), int(label[5:7])
    m += 1
    if m > 12:
        m, y = 1, y + 1
    return f"{y:04d}-{m:02d}"


def build() -> dict[str, Path]:
    rows = load()
    _OUT.mkdir(parents=True, exist_ok=True)

    history = months(rows)
    rev_series = [v for _, v in monthly_series(rows, "revenue_eur")]
    fc = select_and_forecast(rev_series, horizon=3)          # same call as report.analyze
    fc_months = []
    label = history[-1]
    for _ in range(fc.horizon):
        label = _next_month(label)
        fc_months.append(label)

    # ---- dim_date (24 history months + 3 forecast months) -----------------
    dim_date = _OUT / "dim_date.csv"
    with dim_date.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date_key", "date", "year", "month_num", "month_name",
                    "quarter", "is_forecast_month"])
        for lab in history + fc_months:
            y, m = int(lab[:4]), int(lab[5:7])
            w.writerow([_date_key(lab), f"{lab}-01", y, m, _MONTH_NAMES[m],
                        f"Q{(m - 1) // 3 + 1}", 1 if lab in fc_months else 0])

    # ---- dim_region --------------------------------------------------------
    reps_by: dict[str, set] = defaultdict(set)
    custs_by: dict[str, set] = defaultdict(set)
    for r in rows:
        reps_by[r["region"]].add(r["sales_rep"])
        custs_by[r["region"]].add(r["customer_id"])
    dim_region = _OUT / "dim_region.csv"
    with dim_region.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "n_sales_reps", "n_customers"])
        for reg in sorted(reps_by):
            w.writerow([reg, len(reps_by[reg]), len(custs_by[reg])])

    # ---- dim_category (carries the repo's ABC-XYZ classification) ----------
    dim_category = _OUT / "dim_category.csv"
    with dim_category.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_category", "abc", "xyz", "abc_xyz_class",
                    "demand_cv", "revenue_share_pct"])
        for a in sorted(metrics.abc_xyz(rows, "product_category"),
                        key=lambda d: d["product_category"]):
            w.writerow([a["product_category"], a["abc"], a["xyz"], a["class"],
                        a["cv"], a["revenue_share_pct"]])

    # ---- dim_channel (carries the repo's cost-to-serve model) --------------
    promised: dict[str, int] = {}
    for r in rows:
        ch = r["channel"]
        promised[ch] = max(promised.get(ch, 0), r["promised_lead_days"])
    dim_channel = _OUT / "dim_channel.csv"
    with dim_channel.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["channel", "promised_lead_days", "cogs_eur",
                    "returns_cost_eur", "discount_leakage_eur",
                    "cost_to_serve_eur"])
        for c in sorted(spend.cost_to_serve_by_channel(rows),
                        key=lambda d: d["channel"]):
            w.writerow([c["channel"], promised[c["channel"]], c["cogs_eur"],
                        c["returns_cost_eur"], c["discount_leakage_eur"],
                        c["cost_to_serve_eur"]])

    # ---- fact_sales_monthly (grain = month x region x category x channel) --
    cells: dict[tuple, dict[str, float]] = defaultdict(
        lambda: defaultdict(float))
    for r in rows:
        c = cells[(month_of(r), r["region"], r["product_category"],
                   r["channel"])]
        c["orders"] += 1
        c["units"] += r["units"]
        c["revenue_eur"] += r["revenue_eur"]
        c["cost_eur"] += r["cost_eur"]
        c["list_value_eur"] += r["units"] * r["list_price_eur"]
        c["on_time_orders"] += r["on_time"]
        c["in_full_orders"] += r["in_full"]
        c["otif_orders"] += 1 if (r["on_time"] and r["in_full"]) else 0
        c["returned_orders"] += r["returned"]
    fact = _OUT / "fact_sales_monthly.csv"
    with fact.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date_key", "month", "region", "product_category",
                    "channel", "orders", "units", "revenue_eur", "cost_eur",
                    "margin_eur", "list_value_eur", "on_time_orders",
                    "in_full_orders", "otif_orders", "returned_orders"])
        for (mo, reg, cat, ch) in sorted(cells):
            c = cells[(mo, reg, cat, ch)]
            w.writerow([_date_key(mo), mo, reg, cat, ch, int(c["orders"]),
                        int(c["units"]), round(c["revenue_eur"], 2),
                        round(c["cost_eur"], 2),
                        round(c["revenue_eur"] - c["cost_eur"], 2),
                        round(c["list_value_eur"], 2),
                        int(c["on_time_orders"]), int(c["in_full_orders"]),
                        int(c["otif_orders"]), int(c["returned_orders"])])

    # ---- kpi_headline (disconnected repo-level scalars) --------------------
    # These come straight from the KPI engine so the Power BI cards can be
    # cross-checked against deliverables/management_report.md.
    kpi = metrics.kpi_summary(rows)
    grow = metrics.growth(rows)
    bridge = metrics.margin_bridge(rows)
    conc = metrics.concentration(rows)
    sp = spend.spend_summary(rows)
    naive_mase = next(
        (r.mase for r in fc.leaderboard if r.model == "seasonal_naive"),
        float("nan"))
    headline = _OUT / "kpi_headline.csv"
    with headline.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for key in ("revenue_eur", "gross_margin_eur", "gross_margin_pct",
                    "orders", "units", "aov_eur", "discount_leakage_pct",
                    "otif_pct", "on_time_pct", "fill_rate_pct",
                    "returns_rate_pct", "active_customers"):
            w.writerow([key, kpi[key]])
        w.writerow(["yoy_pct", grow["yoy_pct"]])
        w.writerow(["mom_pct", grow["mom_pct"]])
        for key in ("price_effect_eur", "volume_effect_eur", "mix_effect_eur",
                    "total_change_eur"):
            w.writerow([f"bridge_{key}", bridge[key]])
        w.writerow(["top20_customer_share_pct", conc["top_share_pct"]])
        w.writerow(["total_cogs_eur", sp["total_cogs_eur"]])
        w.writerow(["discount_leakage_eur", round(sp["discount_leakage_eur"], 2)])
        w.writerow(["returns_cost_total_eur", sp["returns_cost_total_eur"]])
        w.writerow(["forecast_cv_mase", fc.cv_mase])
        w.writerow(["seasonal_naive_cv_mase", naive_mase])
        for i, v in enumerate(fc.values, start=1):
            w.writerow([f"forecast_revenue_m{i}", v])

    return {"fact_sales_monthly": fact, "dim_date": dim_date,
            "dim_region": dim_region, "dim_category": dim_category,
            "dim_channel": dim_channel, "kpi_headline": headline}


if __name__ == "__main__":
    paths = build()
    for name, p in paths.items():
        n = sum(1 for _ in p.open(encoding="utf-8")) - 1
        print(f"  ok {name:<20} {n:>5} rows  -> {p.relative_to(_ROOT).as_posix()}")
