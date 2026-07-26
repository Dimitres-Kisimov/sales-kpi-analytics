"""report.py — turn the analytics into DELIVERABLES a management team receives.

`analyze()` runs the whole pipeline (KPIs, mix, ABC-XYZ, RFM, margin bridge,
per-series forecast selection, reorder recommendations, auto decision cards).
`write_deliverables()` emits:

    deliverables/management_report.md   a Quarterly-Business-Review write-up
    deliverables/kpi_workbook.xlsx      multi-sheet Excel (openpyxl, optional)
    deliverables/reorder_list.csv       below-ROP SKUs to order now
    deliverables/analysis.json          machine-readable everything
    deliverables/forecast.png           revenue history + forecast (matplotlib, optional)

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from . import metrics
from .dataset import load, monthly_series
from .forecast import select_and_forecast
from .inventory import reorder_recommendation
from .spend import spend_summary

OUT = Path(__file__).resolve().parents[1] / "deliverables"
LEAD_MONTHS = 1.0          # modeling assumption: ~1 month supplier replenishment lead


def analyze(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load()
    kpi = metrics.kpi_summary(rows)
    grow = metrics.growth(rows)
    regions = metrics.by_dimension(rows, "region")
    categories = metrics.by_dimension(rows, "product_category")
    channels = metrics.by_dimension(rows, "channel")
    reps = metrics.by_dimension(rows, "sales_rep")
    abcxyz = metrics.abc_xyz(rows, "product_category")
    abc_by_cat = {a["product_category"]: a for a in abcxyz}
    rfm_all = metrics.rfm(rows)
    seg_counts: dict[str, int] = {}
    for c in rfm_all:
        seg_counts[c["segment"]] = seg_counts.get(c["segment"], 0) + 1
    bridge = metrics.margin_bridge(rows)
    conc = metrics.concentration(rows)
    expenditure = spend_summary(rows)

    # headline revenue forecast (total monthly revenue) with CV model selection
    rev_series = [v for _, v in monthly_series(rows, "revenue_eur")]
    rev_fc = select_and_forecast(rev_series, horizon=3)

    # per (region x category) unit-demand forecast + reorder decision
    region_names = [r["region"] for r in regions]
    cat_names = [c["product_category"] for c in categories]
    forecasts, reorders = [], []
    for reg in region_names:
        for cat in cat_names:
            sub = [r for r in rows if r["region"] == reg and r["product_category"] == cat]
            if len(sub) < 6:
                continue
            units = [v for _, v in monthly_series(sub, "units")]
            sel = select_and_forecast(units, horizon=1)
            abc = abc_by_cat.get(cat, {}).get("abc", "B")
            on_hand = round(sum(units[-3:]) / 3 * (1.3 if abc == "A" else 0.7), 1)
            rec = reorder_recommendation(units, on_hand, LEAD_MONTHS, abc_class=abc)
            forecasts.append({"region": reg, "category": cat, "winner": sel.winner,
                              "cv_mase": sel.cv_mase, "pattern": sel.demand["pattern"],
                              "next_units": sel.values[0]})
            if rec.get("reorder"):
                reorders.append({"region": reg, "category": cat, **rec})
    reorders.sort(key=lambda d: -d["recommended_order_qty"])

    cards = _decision_cards(kpi, grow, bridge, abcxyz, seg_counts, regions, conc, rev_fc,
                            expenditure)
    return {
        "kpi": kpi, "growth": grow, "regions": regions, "categories": categories,
        "channels": channels, "reps": reps, "abc_xyz": abcxyz,
        "rfm_segments": seg_counts, "rfm_top": rfm_all[:10],
        "margin_bridge": bridge, "concentration": conc, "expenditure": expenditure,
        "revenue_forecast": {"winner": rev_fc.winner, "cv_mase": rev_fc.cv_mase,
                             "history": rev_series, "forecast": rev_fc.values,
                             "leaderboard": [vars(r) for r in rev_fc.leaderboard]},
        "series_forecasts": forecasts, "reorder_list": reorders,
        "decision_cards": cards,
    }


def _decision_cards(kpi, grow, bridge, abcxyz, seg_counts, regions, conc, rev_fc,
                    expenditure=None) -> list[str]:
    cards = []
    dd = (expenditure or {}).get("leakage_drilldown")
    if dd and dd.get("by_sales_rep"):
        w = dd["by_sales_rep"][0]
        cards.append(f"Discount drill-down: {w['sales_rep']} ({w['region']}) leads the leakage "
                     f"table - {w['leakage_eur']:,.0f} EUR vs list, {w['excess_eur']:,.0f} EUR of "
                     f"it above the {dd['policy_discount_pct']:.0f}% policy assumption - review "
                     f"discount authority there first.")
    yoy = grow.get("yoy_pct")
    if yoy is not None:
        cards.append(f"Revenue is {'up' if yoy >= 0 else 'down'} {abs(yoy):.1f}% YoY; "
                     f"gross margin sits at {kpi['gross_margin_pct']:.1f}%.")
    if bridge.get("available"):
        drivers = {"price": bridge["price_effect_eur"], "volume": bridge["volume_effect_eur"],
                   "mix": bridge["mix_effect_eur"]}
        worst = min(drivers, key=drivers.get)
        best = max(drivers, key=drivers.get)
        cards.append(f"Margin bridge: {best} added {drivers[best]:,.0f} EUR while {worst} "
                     f"cost {abs(drivers[worst]):,.0f} EUR - steer commercial focus accordingly.")
    cz = [a["product_category"] for a in abcxyz if a["class"] in ("CZ", "CY", "BZ")]
    if cz:
        cards.append(f"Long-tail/erratic categories ({', '.join(cz)}) tie up working "
                     f"capital - move to min-stock or make-to-order.")
    at_risk = seg_counts.get("At risk", 0) + seg_counts.get("Churned / dormant", 0)
    cards.append(f"{at_risk} customers are At-risk/Churned (of {sum(seg_counts.values())}); "
                 f"hand the named list to sales for win-back.")
    cards.append(f"Top-20% of customers drive {conc['top_share_pct']:.0f}% of revenue - "
                 f"concentration risk to monitor.")
    cards.append(f"Next-quarter revenue forecast (model: {rev_fc.winner}, CV-MASE "
                 f"{rev_fc.cv_mase:.2f}): {', '.join(f'{v:,.0f}' for v in rev_fc.values)} EUR.")
    if kpi["otif_pct"] < 90:
        cards.append(f"OTIF is {kpi['otif_pct']:.0f}% (below the 90% service bar) - "
                     f"investigate peak-month delivery reliability.")
    return cards


# --------------------------------------------------------------------------- #
# Deliverable writers
# --------------------------------------------------------------------------- #
def write_deliverables(analysis: dict[str, Any], outdir: Path | None = None) -> list[str]:
    out = outdir or OUT
    out.mkdir(parents=True, exist_ok=True)
    made = []
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    made.append("analysis.json")
    made.append(_write_reorder_csv(analysis, out))
    made.append(_write_markdown(analysis, out))
    x = _write_xlsx(analysis, out)
    if x:
        made.append(x)
    p = _write_chart(analysis, out)
    if p:
        made.append(p)
    lw = _write_leakage_chart(analysis, out)
    if lw:
        made.append(lw)
    return made


def _write_reorder_csv(a: dict, out: Path) -> str:
    rows = a["reorder_list"]
    cols = ["region", "category", "abc_class", "service_level", "avg_demand",
            "safety_stock", "reorder_point", "on_hand", "recommended_order_qty"]
    with (out / "reorder_list.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return "reorder_list.csv"


def _write_markdown(a: dict, out: Path) -> str:
    k, g = a["kpi"], a["growth"]
    b = a["margin_bridge"]
    lines = [
        "# Quarterly Business Review — Sales & Demand Analytics",
        "",
        "*Auto-generated from 24 months of order data. Author: Dimitres Kisimov.*",
        "",
        "## 1. Headline KPIs",
        f"- Revenue: **{k['revenue_eur']:,.0f} EUR** "
        + (f"({g['yoy_pct']:+.1f}% YoY)" if g.get("yoy_pct") is not None else ""),
        f"- Gross margin: **{k['gross_margin_pct']:.1f}%** ({k['gross_margin_eur']:,.0f} EUR)",
        f"- Orders: {k['orders']:,} · AOV: {k['aov_eur']:,.0f} EUR · Active customers: {k['active_customers']}",
        f"- Service: OTIF {k['otif_pct']:.0f}% · on-time {k['on_time_pct']:.0f}% · "
        f"fill rate {k['fill_rate_pct']:.0f}% · returns {k['returns_rate_pct']:.1f}%",
        f"- Discount leakage: {k['discount_leakage_pct']:.1f}% of list value",
        "",
        "## 2. What the numbers say (decision cards)",
    ]
    lines += [f"- {c}" for c in a["decision_cards"]]
    lines += ["", "## 3. Margin bridge (YoY, price / volume / mix)"]
    if b.get("available"):
        lines += [
            f"- Prior 12m margin: {b['prior_margin_eur']:,.0f} EUR → current {b['current_margin_eur']:,.0f} EUR "
            f"(**{b['total_change_eur']:+,.0f} EUR**)",
            f"- Price effect: {b['price_effect_eur']:+,.0f} EUR · Volume: {b['volume_effect_eur']:+,.0f} EUR · "
            f"Mix: {b['mix_effect_eur']:+,.0f} EUR",
        ]
    lines += ["", "## 4. Portfolio (ABC × XYZ)",
              "| Category | Revenue | Share | Class | CV |", "|---|--:|--:|:--:|--:|"]
    for r in a["abc_xyz"]:
        lines.append(f"| {r['product_category']} | {r['revenue_eur']:,.0f} | "
                     f"{r['revenue_share_pct']:.1f}% | {r['class']} | {r['cv']} |")
    rf = a["revenue_forecast"]
    lines += ["", "## 5. Revenue forecast (next 3 months)",
              f"- Model selected by rolling-origin cross-validation: **{rf['winner']}** "
              f"(CV-MASE {rf['cv_mase']:.2f}; <1 beats the seasonal-naive baseline)",
              f"- Forecast: {', '.join(f'{v:,.0f}' for v in rf['forecast'])} EUR",
              "", "## 6. Replenishment — reorder now",
              f"- {len(a['reorder_list'])} region×category cells are at/below their reorder point.",
              "  See `reorder_list.csv` for quantities (safety stock at per-ABC service levels)."]
    sp = a.get("expenditure")
    if sp:
        lines += ["", "## 7. Expenditure & spend",
                  f"- Total COGS: **{sp['total_cogs_eur']:,.0f} EUR** "
                  f"on {sp['list_value_eur']:,.0f} EUR of list value.",
                  f"- Discount leakage: **{sp['discount_leakage_eur']:,.0f} EUR** "
                  f"({sp['discount_leakage_pct']:.1f}% of list) given away versus list price.",
                  f"- Modeled returns cost: {sp['returns_cost_total_eur']:,.0f} EUR.",
                  "",
                  "| Channel | COGS | Returns cost | Discount leakage | Cost-to-serve |",
                  "|---|--:|--:|--:|--:|"]
        for c in sp["cost_to_serve_by_channel"]:
            lines.append(f"| {c['channel']} | {c['cogs_eur']:,.0f} | "
                         f"{c['returns_cost_eur']:,.0f} | {c['discount_leakage_eur']:,.0f} | "
                         f"{c['cost_to_serve_eur']:,.0f} |")
        dd = sp.get("leakage_drilldown")
        if dd:
            lines += [
                "", "### 7.1 Discount-leakage drill-down — who, where",
                f"Waterfall: gross list value {dd['gross_list_value_eur']:,.0f} EUR "
                f"− within-policy discounts {dd['within_policy_discount_eur']:,.0f} EUR "
                f"− excess discounts {dd['excess_discount_eur']:,.0f} EUR "
                f"= net revenue {dd['net_revenue_eur']:,.0f} EUR. "
                f"Both discount cuts together are the {dd['total_leakage_eur']:,.0f} EUR leakage.",
                "",
                f"*Policy threshold: {dd['policy_discount_pct']:.0f}% of list — "
                f"{dd['policy_note']}.*",
                "",
                "Top 5 reps by excess-over-policy (see `leakage_waterfall.png`):",
                "",
                "| Rep | Region | Leakage | Excess >policy | % of own revenue | "
                "Orders >policy | Median / p90 discount |",
                "|---|---|--:|--:|--:|--:|--:|",
            ]
            for r in dd["by_sales_rep"][:5]:
                lines.append(
                    f"| {r['sales_rep']} | {r['region']} | {r['leakage_eur']:,.0f} | "
                    f"{r['excess_eur']:,.0f} | {r['leakage_pct_of_revenue']:.1f}% | "
                    f"{r['orders_above_policy_pct']:.0f}% | "
                    f"{r['median_discount_pct']:.1f}% / {r['p90_discount_pct']:.1f}% |")
            lines += ["", "| Region | Leakage | Excess >policy | % of region revenue | "
                          "Orders >policy |", "|---|--:|--:|--:|--:|"]
            for r in dd["by_region"]:
                lines.append(
                    f"| {r['region']} | {r['leakage_eur']:,.0f} | {r['excess_eur']:,.0f} | "
                    f"{r['leakage_pct_of_revenue']:.1f}% | "
                    f"{r['orders_above_policy_pct']:.0f}% |")
    (out / "management_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "management_report.md"


def _write_xlsx(a: dict, out: Path) -> str | None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return None
    wb = Workbook()
    hdr = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="2F6BFF")

    ws = wb.active
    ws.title = "KPIs"
    ws.append(["Sales & Demand Analytics — KPI summary"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    for key, val in a["kpi"].items():
        ws.append([key, val])

    def sheet(name, rows, cols):
        s = wb.create_sheet(name)
        s.append(cols)
        for c in s[1]:
            c.font, c.fill = hdr, fill
        for r in rows:
            s.append([r.get(c) for c in cols])

    sheet("Mix by region", a["regions"], ["region", "revenue_eur", "margin_pct", "orders"])
    sheet("ABC-XYZ", a["abc_xyz"],
          ["product_category", "revenue_eur", "revenue_share_pct", "abc", "cv", "xyz", "class"])
    sheet("RFM top", a["rfm_top"],
          ["customer_id", "recency_days", "frequency", "monetary_eur", "rfm_score", "segment"])
    sheet("Forecasts", a["series_forecasts"],
          ["region", "category", "winner", "cv_mase", "pattern", "next_units"])
    sheet("Reorder list", a["reorder_list"],
          ["region", "category", "abc_class", "safety_stock", "reorder_point",
           "on_hand", "recommended_order_qty"])
    sp = a.get("expenditure")
    if sp:
        sheet("Spend", sp["cost_to_serve_by_channel"],
              ["channel", "cogs_eur", "returns_cost_eur", "discount_leakage_eur",
               "cost_to_serve_eur", "orders"])
        s = wb["Spend"]
        s.append([])
        s.append(["Total COGS", sp["total_cogs_eur"]])
        s.append(["Discount leakage EUR", sp["discount_leakage_eur"]])
        s.append(["Discount leakage %", sp["discount_leakage_pct"]])
        s.append(["Returns cost total", sp["returns_cost_total_eur"]])
        dd = sp.get("leakage_drilldown")
        if dd:
            sheet("Leakage drill-down", dd["by_sales_rep"],
                  ["sales_rep", "region", "leakage_eur", "excess_eur", "within_policy_eur",
                   "leakage_pct_of_revenue", "orders", "orders_above_policy_pct",
                   "median_discount_pct", "p90_discount_pct"])
            s = wb["Leakage drill-down"]
            s.append([])
            s.append(["By region"])
            s.append(["region", "leakage_eur", "excess_eur", "leakage_pct_of_revenue",
                      "orders_above_policy_pct"])
            for r in dd["by_region"]:
                s.append([r["region"], r["leakage_eur"], r["excess_eur"],
                          r["leakage_pct_of_revenue"], r["orders_above_policy_pct"]])
            s.append([])
            s.append(["Policy threshold %", dd["policy_discount_pct"]])
            s.append(["Note", dd["policy_note"]])
    wb.save(out / "kpi_workbook.xlsx")
    return "kpi_workbook.xlsx"


def _write_chart(a: dict, out: Path) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rf = a["revenue_forecast"]
    hist = rf["history"]
    fc = rf["forecast"]
    fig, ax = plt.subplots(figsize=(10, 4))
    xh = list(range(len(hist)))
    xf = list(range(len(hist) - 1, len(hist) + len(fc)))
    ax.plot(xh, hist, color="#2f6bff", label="actual revenue")
    ax.plot(xf, [hist[-1]] + fc, color="#ea4b71", ls="--", marker="o",
            label=f"forecast ({rf['winner']}, CV-MASE {rf['cv_mase']:.2f})")
    band = max(hist) * 0.06
    ax.fill_between(xf, [hist[-1]] + [v - band for v in fc],
                    [hist[-1]] + [v + band for v in fc], color="#ea4b71", alpha=0.15)
    ax.set_title("Monthly revenue — 24 months actual + 3-month forecast")
    ax.set_xlabel("month index")
    ax.set_ylabel("EUR")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "forecast.png", dpi=140)
    plt.close(fig)
    return "forecast.png"


def _write_leakage_chart(a: dict, out: Path) -> str | None:
    """Discount-leakage waterfall (gross -> within-policy -> excess -> net) plus
    the per-region leakage split. Same decomposition the drill-down reports."""
    dd = (a.get("expenditure") or {}).get("leakage_drilldown")
    if not dd:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    ink, blue, pink, mute = "#1a1f2b", "#2f6bff", "#ea4b71", "#8b8f99"
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.4), width_ratios=[3, 2])

    gross = dd["gross_list_value_eur"] / 1e6
    within = dd["within_policy_discount_eur"] / 1e6
    excess = dd["excess_discount_eur"] / 1e6
    net = dd["net_revenue_eur"] / 1e6
    labels = ["Gross\nlist value", "Within-policy\ndiscounts", "Excess\ndiscounts", "Net\nrevenue"]
    # totals sit on the baseline; the two discount cuts float between running totals
    bars = [(0.0, gross, mute), (gross - within, within, blue),
            (net, excess, pink), (0.0, net, mute)]
    for i, (bottom, height, color) in enumerate(bars):
        ax.bar(i, height, bottom=bottom, color=color, width=0.62,
               edgecolor="white", linewidth=1.5)
        val = [gross, -within, -excess, net][i]
        ax.annotate(f"{val:+,.2f}M" if 0 < i < 3 else f"{val:,.2f}M",
                    (i, bottom + height), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=9.5, color=ink)
    # connectors between running totals
    for i, lvl in enumerate([gross, gross - within, net]):
        ax.plot([i + 0.31, i + 1 - 0.31], [lvl, lvl], color=mute, lw=1, ls=":")
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("EUR (millions)")
    ax.set_title(f"Discount leakage {dd['total_leakage_eur'] / 1e6:,.2f}M EUR = "
                 f"both discount cuts vs list", fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)

    regs = dd["by_region"]
    names = [r["region"] for r in regs][::-1]
    wp = [r["within_policy_eur"] / 1e6 for r in regs][::-1]
    ex = [r["excess_eur"] / 1e6 for r in regs][::-1]
    ax2.barh(names, wp, color=blue, label="within policy", edgecolor="white", linewidth=1)
    ax2.barh(names, ex, left=wp, color=pink, label="excess", edgecolor="white", linewidth=1)
    for i, r in enumerate(regs[::-1]):
        ax2.text(wp[i] + ex[i], i, f" {r['leakage_eur'] / 1e6:,.2f}M",
                 va="center", fontsize=9, color=ink)
    ax2.set_xlim(0, max(w + e for w, e in zip(wp, ex, strict=False)) * 1.22)
    ax2.set_xlabel("EUR (millions)")
    ax2.set_title(f"Leakage by region (policy = {dd['policy_discount_pct']:.0f}% of list, "
                  f"assumed)", fontsize=11)
    ax2.legend(fontsize=8, frameon=False, loc="lower right")
    ax2.grid(axis="x", alpha=0.3)
    ax2.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "leakage_waterfall.png", dpi=140)
    plt.close(fig)
    return "leakage_waterfall.png"
