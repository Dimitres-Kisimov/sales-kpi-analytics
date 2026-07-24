"""Shared fixtures: a tiny hand-built table plus the real 24-month dataset."""
from __future__ import annotations

import pytest

from saleskpi.dataset import load


def _row(**kw):
    """A transaction row with sensible defaults; override any field via kwargs."""
    base = {
        "order_id": "O0001",
        "date": "2025-01-15",
        "region": "West",
        "sales_rep": "Martin",
        "customer_id": "C001",
        "customer_segment": "SMB",
        "product_category": "fasteners",
        "channel": "e-shop",
        "units": 10,
        "list_price_eur": 1.0,
        "discount_pct": 0.0,
        "revenue_eur": 100.0,
        "cost_eur": 60.0,
        "promised_lead_days": 3,
        "actual_lead_days": 3,
        "on_time": 1,
        "in_full": 1,
        "returned": 0,
    }
    base.update(kw)
    base["margin_eur"] = round(base["revenue_eur"] - base["cost_eur"], 2)
    return base


@pytest.fixture
def tiny_rows():
    """Four orders, two customers — totals are easy to check by hand.

    revenue: 100 + 200 + 300 + 400 = 1000 ; cost 60+120+150+240 = 570
    margin = 430 ; margin% = 43.0 ; orders 4 ; units 10+20+30+40 = 100
    """
    return [
        _row(order_id="O1", customer_id="C1", region="West",
             units=10, revenue_eur=100.0, cost_eur=60.0, on_time=1, in_full=1),
        _row(order_id="O2", customer_id="C1", region="West",
             units=20, revenue_eur=200.0, cost_eur=120.0, on_time=1, in_full=0),
        _row(order_id="O3", customer_id="C2", region="East",
             units=30, revenue_eur=300.0, cost_eur=150.0, on_time=0, in_full=1),
        _row(order_id="O4", customer_id="C2", region="East",
             units=40, revenue_eur=400.0, cost_eur=240.0, on_time=1, in_full=1,
             returned=1),
    ]


@pytest.fixture(scope="session")
def real_rows():
    """The full generated 24-month dataset (skips if it hasn't been generated)."""
    rows = load()
    if not rows:
        pytest.skip("data/sales_transactions.csv is empty — run scripts/generate_data.py")
    return rows
