"""anomaly.py — the KPI exception monitor (robust statistical process control).

A dashboard full of numbers doesn't tell leadership *what to look at*. This module
is the "so what changed?" layer: it scans each monthly KPI series and flags the
months that are genuinely out of control — the exception report a distributor's
BI team circulates so management reads six numbers, not six hundred.

Method (pure stdlib, from scratch, deterministic):

  * robust centre  = median of the monthly series
  * robust scale   = MAD / 0.6745  (median absolute deviation, rescaled to a
                     normal-consistent sigma — the Iglewicz–Hoaglin estimator)
  * modified z     = 0.6745 · (x − median) / MAD
  * control limits = centre ± k · (MAD / 0.6745),  default k = 3.5

A point is an *exception* when |modified z| > k. Robust estimators are used on
purpose: a classic mean ± 3σ chart lets a single bad month inflate its own limits
and hide, whereas the median/MAD limits do not move when one point blows out.
The k = 3.5 cut-off is the standard Iglewicz–Hoaglin outlier threshold for the
modified z-score, so nothing here is hand-tuned to the data.

Each exception carries a **polarity** — whether the move is good or bad for the
business (returns rising is unfavourable; margin rising is favourable) — so the
report can separate "problems to fix" from "wins to bank".

Scope, honestly. The monitored KPIs are the quality/service/commercial *ratios*
(gross-margin %, OTIF %, returns %, discount-leakage %) plus AOV, where a monthly
control chart is trustworthy. The strongly-seasonal *volume* series (revenue,
orders) are deliberately **not** run through a level-anomaly detector: with only
24 monthly points, estimating a per-month seasonal profile well enough to avoid
false alarms isn't possible (the edge months come out as artefacts), so revenue
movement is left to the pieces built for it — the out-of-sample forecast CV and
the price/volume/mix bridge. A seasonal-adjustment path exists and is unit-tested
for completeness, but the shipped KPI set uses the raw robust chart where it is
sound.

    from saleskpi.anomaly import kpi_exceptions
    exc = kpi_exceptions(rows)
    for a in exc["alerts"]:
        print(a["kpi"], a["month"], a["value"], a["modified_z"])

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

Rows = list[dict[str, Any]]

# Iglewicz–Hoaglin: 0.6745 = Φ⁻¹(0.75), the scale that makes MAD a consistent
# estimator of σ for normal data; 3.5 is their recommended modified-z outlier cut.
_MAD_TO_SIGMA = 0.6745
DEFAULT_K = 3.5

# For a normal distribution E|X − μ| = σ·√(2/π); this rescales the mean absolute
# deviation to a σ estimate for the degenerate fallback when MAD == 0.
_MEANAD_TO_SIGMA = 0.7978845608


# --------------------------------------------------------------------------- #
# The KPIs we monitor, each with its polarity (is "up" good or bad?)
# --------------------------------------------------------------------------- #
# polarity: "higher_is_better" | "lower_is_better" | "neutral"
KPI_SPECS: list[dict[str, Any]] = [
    {"kpi": "gross_margin_pct", "label": "Gross margin %", "unit": "%",
     "polarity": "higher_is_better", "seasonal": False},
    {"kpi": "otif_pct", "label": "OTIF %", "unit": "%",
     "polarity": "higher_is_better", "seasonal": False},
    {"kpi": "returns_rate_pct", "label": "Returns rate %", "unit": "%",
     "polarity": "lower_is_better", "seasonal": False},
    {"kpi": "discount_leakage_pct", "label": "Discount leakage %", "unit": "%",
     "polarity": "lower_is_better", "seasonal": False},
    {"kpi": "aov_eur", "label": "Average order value", "unit": "EUR",
     "polarity": "neutral", "seasonal": False},
]


# --------------------------------------------------------------------------- #
# Robust statistics
# --------------------------------------------------------------------------- #
def median_abs_deviation(vals: list[float]) -> float:
    """MAD = median(|xᵢ − median(x)|). Zero for a (near-)constant series."""
    if not vals:
        return 0.0
    med = statistics.median(vals)
    return statistics.median([abs(v - med) for v in vals])


def robust_scale(vals: list[float]) -> float:
    """A normal-consistent σ estimate from the MAD, with a mean-absolute-deviation
    fallback for the tie-heavy case where MAD collapses to zero but the series is
    not actually constant. Returns 0.0 only for a genuinely flat series."""
    mad = median_abs_deviation(vals)
    if mad > 0:
        return mad / _MAD_TO_SIGMA
    med = statistics.median(vals) if vals else 0.0
    mean_ad = statistics.mean([abs(v - med) for v in vals]) if vals else 0.0
    return (mean_ad / _MEANAD_TO_SIGMA) if mean_ad > 0 else 0.0


def modified_z(vals: list[float]) -> list[float]:
    """Iglewicz–Hoaglin modified z-scores, robust to outliers. A flat series
    (no dispersion) yields all-zero scores rather than dividing by zero."""
    if not vals:
        return []
    med = statistics.median(vals)
    scale = robust_scale(vals)
    if scale == 0:
        return [0.0] * len(vals)
    return [(v - med) / scale for v in vals]


# --------------------------------------------------------------------------- #
# Seasonal adjustment (classical multiplicative; tested, off by default)
# --------------------------------------------------------------------------- #
def deseasonalize(vals: list[float], period: int = 12) -> list[float]:
    """Robust multiplicative seasonal adjustment: divide out a seasonal index
    estimated as the *median* detrended ratio per position-in-cycle (trend = a
    centred 2×period moving average). Series shorter than two full cycles are
    returned unchanged. Provided for completeness and unit-tested; the shipped
    KPI set does not use it (see the module docstring on the 24-point limit)."""
    n = len(vals)
    if n < 2 * period:
        return list(vals)
    trend: list[float | None] = [None] * n
    half = period // 2
    for i in range(half, n - half):
        window = vals[i - half:i + half + 1]
        weights = [0.5] + [1.0] * (period - 1) + [0.5]
        trend[i] = sum(w * x for w, x in zip(window, weights, strict=True)) / period
    ratios: dict[int, list[float]] = defaultdict(list)
    for i in range(n):
        t = trend[i]
        if t:
            ratios[i % period].append(vals[i] / t)
    index = {}
    for s in range(period):
        index[s] = statistics.median(ratios[s]) if ratios[s] else 1.0
    mean_index = statistics.mean(index.values()) or 1.0
    index = {s: index[s] / mean_index for s in index}
    return [vals[i] / (index[i % period] or 1.0) for i in range(n)]


# --------------------------------------------------------------------------- #
# Monthly KPI series straight from the transaction rows
# --------------------------------------------------------------------------- #
def monthly_kpi_table(rows: Rows) -> list[dict[str, Any]]:
    """Ordered [{month, revenue_eur, orders, gross_margin_pct, aov_eur, otif_pct,
    returns_rate_pct, discount_leakage_pct}] — one record per calendar month."""
    buckets: dict[str, Rows] = defaultdict(list)
    for r in rows:
        buckets[r["date"][:7]].append(r)
    out = []
    for month in sorted(buckets):
        grp = buckets[month]
        n = len(grp)
        rev = sum(r["revenue_eur"] for r in grp)
        cost = sum(r["cost_eur"] for r in grp)
        gross_list = sum(r["units"] * r["list_price_eur"] for r in grp)
        out.append({
            "month": month,
            "revenue_eur": round(rev, 2),
            "orders": n,
            "gross_margin_pct": round(100 * (rev - cost) / rev, 2) if rev else 0.0,
            "aov_eur": round(rev / n, 2) if n else 0.0,
            "otif_pct": round(100 * sum(r["on_time"] and r["in_full"] for r in grp) / n, 2)
            if n else 0.0,
            "returns_rate_pct": round(100 * sum(r["returned"] for r in grp) / n, 2) if n else 0.0,
            "discount_leakage_pct": round(100 * (gross_list - rev) / gross_list, 2)
            if gross_list else 0.0,
        })
    return out


# --------------------------------------------------------------------------- #
# Exception detection
# --------------------------------------------------------------------------- #
def _favorable(direction: str, polarity: str) -> bool | None:
    """Is an out-of-limit move good news? None when the KPI has no natural polarity."""
    if polarity == "neutral":
        return None
    good_up = polarity == "higher_is_better"
    return good_up if direction == "above" else not good_up


def _severity(abs_z: float, k: float) -> str:
    """Two bands above the control limit: 'severe' past ~1.5× the limit."""
    return "severe" if abs_z > 1.5 * k else "elevated"


def _detect_one(table: list[dict[str, Any]], spec: dict[str, Any],
                k: float) -> dict[str, Any]:
    """Run the robust control chart for one KPI over the monthly table."""
    months = [row["month"] for row in table]
    raw = [float(row[spec["kpi"]]) for row in table]
    basis = deseasonalize(raw, 12) if spec.get("seasonal") else raw
    center = statistics.median(basis)
    scale = robust_scale(basis)
    lower = center - k * scale
    upper = center + k * scale
    zs = modified_z(basis)

    points, flagged = [], 0
    for i, month in enumerate(months):
        z = zs[i]
        is_flag = abs(z) > k
        points.append({
            "month": month,
            "value": round(raw[i], 2),
            "modified_z": round(z, 3),
            "flagged": is_flag,
        })
        if is_flag:
            flagged += 1
    return {
        "kpi": spec["kpi"],
        "label": spec["label"],
        "unit": spec["unit"],
        "polarity": spec["polarity"],
        "seasonal": bool(spec.get("seasonal")),
        # limits/centre are on the (possibly adjusted) basis the z-scores use;
        # for the shipped non-seasonal KPIs the basis is the raw series, so these
        # limits are directly comparable to the values a reader sees.
        "center": round(center, 2),
        "sigma_robust": round(scale, 4),
        "lower_limit": round(lower, 2),
        "upper_limit": round(upper, 2),
        "n_flagged": flagged,
        "points": points,
    }


def kpi_exceptions(rows: Rows, specs: list[dict[str, Any]] | None = None,
                   k: float = DEFAULT_K) -> dict[str, Any]:
    """Scan every monitored KPI's monthly series for out-of-control months.

    Returns the per-KPI control-chart series (centre, robust sigma, limits, and
    each month's value + modified z + flag) plus a flat ``alerts`` list sorted
    worst-first (severity, then |z|, then month). The number of alerts for a KPI
    equals its ``n_flagged`` and equals the count of points outside its limits —
    the layer reconciles to itself, which a test enforces.
    """
    specs = specs or KPI_SPECS
    table = monthly_kpi_table(rows)
    series: dict[str, Any] = {}
    alerts: list[dict[str, Any]] = []
    for spec in specs:
        chart = _detect_one(table, spec, k)
        series[spec["kpi"]] = chart
        for p in chart["points"]:
            if not p["flagged"]:
                continue
            direction = "above" if p["modified_z"] > 0 else "below"
            fav = _favorable(direction, spec["polarity"])
            alerts.append({
                "kpi": spec["kpi"],
                "label": spec["label"],
                "unit": spec["unit"],
                "month": p["month"],
                "value": p["value"],
                "center": chart["center"],
                "lower_limit": chart["lower_limit"],
                "upper_limit": chart["upper_limit"],
                "modified_z": p["modified_z"],
                "delta_from_center": round(p["value"] - chart["center"], 2),
                "direction": direction,
                "favorable": fav,
                "severity": _severity(abs(p["modified_z"]), k),
            })
    # worst first: severe before elevated, then biggest |z|, then chronological
    sev_rank = {"severe": 0, "elevated": 1}
    alerts.sort(key=lambda a: (sev_rank.get(a["severity"], 9),
                               -abs(a["modified_z"]), a["month"]))

    unfavorable = sum(1 for a in alerts if a["favorable"] is False)
    favorable = sum(1 for a in alerts if a["favorable"] is True)
    by_kpi: dict[str, int] = defaultdict(int)
    for a in alerts:
        by_kpi[a["kpi"]] += 1
    in_control = [s["label"] for s in series.values() if s["n_flagged"] == 0]

    return {
        "method": "robust control chart (median ± k·MAD/0.6745, Iglewicz–Hoaglin modified z)",
        "k_sigma": k,
        "months": len(table),
        "period": f"{table[0]['month']}..{table[-1]['month']}" if table else "",
        "monitored_kpis": [s["kpi"] for s in specs],
        "series": series,
        "alerts": alerts,
        "summary": {
            "total_alerts": len(alerts),
            "unfavorable": unfavorable,
            "favorable": favorable,
            "by_kpi": dict(by_kpi),
            "kpis_in_control": in_control,
        },
    }


def plain_language(exc: dict[str, Any]) -> str:
    """One-line read of the exception scan, e.g.
    'KPI monitor: 6 exceptions in 24 months — 6 unfavourable (OTIF %); 4 KPIs in control.'"""
    s = exc["summary"]
    total = s["total_alerts"]
    if total == 0:
        return (f"KPI monitor: no exceptions across {len(exc['monitored_kpis'])} KPIs "
                f"over {exc['months']} months — every series inside its control limits.")
    worst = exc["alerts"][0]
    kpis_hit = ", ".join(sorted({a["label"] for a in exc["alerts"]}))
    return (f"KPI monitor: {total} exception{'s' if total != 1 else ''} in {exc['months']} "
            f"months — {s['unfavorable']} unfavourable, {s['favorable']} favourable "
            f"({kpis_hit}); worst {worst['label']} at {worst['month']} "
            f"({worst['value']}{'' if worst['unit'] == 'EUR' else worst['unit']}, "
            f"z={worst['modified_z']:+.1f}). {len(s['kpis_in_control'])} KPIs in control.")


def control_chart_steps(chart: dict[str, Any]) -> dict[str, Any]:
    """The single source of truth a control-chart figure draws: the ordered
    monthly points plus the centre and the two limit lines. The SVG renderer and
    the tests both consume this, so the picture cannot drift from the numbers."""
    return {
        "kpi": chart["kpi"],
        "label": chart["label"],
        "unit": chart["unit"],
        "center": chart["center"],
        "lower_limit": chart["lower_limit"],
        "upper_limit": chart["upper_limit"],
        "points": chart["points"],
    }
