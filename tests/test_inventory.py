"""Tests for safety stock, reorder points and the reorder recommendation."""
from __future__ import annotations

from saleskpi import inventory as inv


def test_z_for_service_95():
    assert abs(inv.z_for_service(0.95) - 1.645) < 0.005


def test_z_monotonic_in_service_level():
    assert inv.z_for_service(0.90) < inv.z_for_service(0.95) < inv.z_for_service(0.99)


def test_safety_stock_monotonic_in_service_level():
    s90 = inv.safety_stock(demand_std=20.0, lead_time=1.0, service_level=0.90)
    s95 = inv.safety_stock(demand_std=20.0, lead_time=1.0, service_level=0.95)
    s99 = inv.safety_stock(demand_std=20.0, lead_time=1.0, service_level=0.99)
    assert s90 < s95 < s99


def test_reorder_point_monotonic_in_service_level():
    def rop(sl):
        ss = inv.safety_stock(demand_std=20.0, lead_time=2.0, service_level=sl)
        return inv.reorder_point(avg_demand=50.0, lead_time=2.0, ss=ss)

    assert rop(0.90) < rop(0.95) < rop(0.99)


def test_gmroi():
    assert inv.gmroi(1000.0, 250.0) == 4.0
    assert inv.gmroi(1000.0, 0.0) == 0.0


def test_reorder_recommendation_flags_reorder_when_below_rop():
    history = [100.0, 110.0, 90.0, 105.0, 95.0, 100.0, 108.0, 92.0]
    # very low on-hand -> must reorder
    low = inv.reorder_recommendation(history, on_hand=0.0, lead_time_periods=1.0, abc_class="A")
    assert low["reorder"] is True
    assert low["recommended_order_qty"] > 0
    # far above the reorder point -> no reorder
    high = inv.reorder_recommendation(history, on_hand=100000.0, lead_time_periods=1.0, abc_class="A")
    assert high["reorder"] is False
    assert high["recommended_order_qty"] == 0.0


def test_reorder_recommendation_needs_history():
    out = inv.reorder_recommendation([100.0], on_hand=0.0, lead_time_periods=1.0)
    assert out["reorder"] is False
