"""Tests for the expenditure / spend module."""
from __future__ import annotations

from saleskpi import spend


def test_category_spend_reconciles_to_total_cogs(real_rows):
    s = spend.spend_summary(real_rows)
    cat_total = sum(c["cogs_eur"] for c in s["cogs_by_category"])
    assert abs(cat_total - s["total_cogs_eur"]) < 1.0
    # region and channel splits must reconcile to the same total too
    reg_total = sum(c["cogs_eur"] for c in s["cogs_by_region"])
    ch_total = sum(c["cogs_eur"] for c in s["cogs_by_channel"])
    assert abs(reg_total - s["total_cogs_eur"]) < 1.0
    assert abs(ch_total - s["total_cogs_eur"]) < 1.0


def test_total_cogs_matches_kpi(real_rows):
    from saleskpi import metrics
    k = metrics.kpi_summary(real_rows)
    s = spend.spend_summary(real_rows)
    assert abs(s["total_cogs_eur"] - k["cost_eur"]) < 1.0


def test_spend_shares_sum_to_100(real_rows):
    s = spend.spend_summary(real_rows)
    share = sum(c["spend_share_pct"] for c in s["cogs_by_category"])
    assert abs(share - 100.0) < 0.5


def test_discount_leakage_positive_and_bounded(real_rows):
    s = spend.spend_summary(real_rows)
    assert s["discount_leakage_eur"] >= 0
    assert 0 <= s["discount_leakage_pct"] <= 100


def test_cost_to_serve_is_sum_of_parts():
    rows = [
        {"channel": "e-shop", "product_category": "x", "region": "W", "units": 10,
         "list_price_eur": 2.0, "revenue_eur": 18.0, "cost_eur": 12.0, "returned": 0},
        {"channel": "e-shop", "product_category": "x", "region": "W", "units": 5,
         "list_price_eur": 2.0, "revenue_eur": 9.0, "cost_eur": 6.0, "returned": 1},
    ]
    cts = spend.cost_to_serve_by_channel(rows)
    assert len(cts) == 1
    row = cts[0]
    expected = row["cogs_eur"] + row["returns_cost_eur"] + row["discount_leakage_eur"]
    assert abs(row["cost_to_serve_eur"] - round(expected, 2)) < 0.01
    # leakage = list value (10*2 + 5*2 = 30) - revenue (18+9 = 27) = 3
    assert abs(row["discount_leakage_eur"] - 3.0) < 0.01
