"""dataset.py — load and shape the sales transactions.

Typed CSV loader plus the aggregation helpers every metric/forecast builds on
(monthly series, group-by rollups). Pure stdlib.

    from saleskpi.dataset import load, monthly_series
    rows = load()
    rev_by_month = monthly_series(rows, "revenue_eur")   # ordered [(YYYY-MM, value)]

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "sales_transactions.csv"

_INT = {"units", "promised_lead_days", "actual_lead_days", "on_time", "in_full", "returned"}
_FLOAT = {"list_price_eur", "discount_pct", "revenue_eur", "cost_eur"}


def load(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else _DATA
    rows: list[dict[str, Any]] = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            for k in _INT:
                if k in r:
                    r[k] = int(r[k])
            for k in _FLOAT:
                if k in r:
                    r[k] = float(r[k])
            r["margin_eur"] = round(r["revenue_eur"] - r["cost_eur"], 2)
            rows.append(r)
    return rows


def month_of(row: dict[str, Any]) -> str:
    return row["date"][:7]                       # "YYYY-MM"


def months(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({month_of(r) for r in rows})


def monthly_series(rows: list[dict[str, Any]], field: str = "revenue_eur",
                   agg: str = "sum") -> list[tuple[str, float]]:
    """Ordered monthly aggregate of `field`. agg in {"sum","mean","count"}."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        buckets[month_of(r)].append(float(r[field]))
    out = []
    for m in sorted(buckets):
        vals = buckets[m]
        if agg == "sum":
            v = sum(vals)
        elif agg == "mean":
            v = sum(vals) / len(vals)
        elif agg == "count":
            v = float(len(vals))
        else:
            raise ValueError(f"unknown agg {agg!r}")
        out.append((m, round(v, 2)))
    return out


def group_sum(rows: list[dict[str, Any]], by: str, field: str = "revenue_eur",
              extra: Callable[[list[dict]], dict] | None = None) -> list[dict[str, Any]]:
    """Sum `field` grouped by `by`, sorted descending. Optional `extra` adds
    computed columns from each group's rows."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[by]].append(r)
    out = []
    for key, grp in groups.items():
        rec = {by: key, field: round(sum(g[field] for g in grp), 2), "orders": len(grp)}
        if extra:
            rec.update(extra(grp))
        out.append(rec)
    out.sort(key=lambda d: -d[field])
    return out
