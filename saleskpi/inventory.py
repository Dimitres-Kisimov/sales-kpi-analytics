"""inventory.py — replenishment analytics that turn a forecast into a decision.

Safety stock and reorder points from the classic statistical formulas, plus
GMROI (the metric distributors watch most). Service levels are set per ABC class
(A-items get 99%, C-items less) so working capital follows value.

    Safety stock (demand variability):        SS = Z · σ_d · √L
    Safety stock (demand + lead-time var.):    SS = Z · √(L·σ_d² + d̄²·σ_L²)
    Reorder point:                             ROP = d̄·L + SS
    GMROI:                                     gross_margin_€ / avg_inventory_cost

Z comes from the target cycle service level via the inverse normal CDF
(statistics.NormalDist), so it is exact and stdlib-only.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import math
import statistics
from statistics import NormalDist

# service level by ABC class (higher value -> protect availability harder)
SERVICE_BY_ABC = {"A": 0.98, "B": 0.95, "C": 0.90}


def z_for_service(service_level: float) -> float:
    return NormalDist().inv_cdf(min(0.9999, max(0.5, service_level)))


def safety_stock(demand_std: float, lead_time: float, service_level: float = 0.95) -> float:
    return z_for_service(service_level) * demand_std * math.sqrt(max(0.0, lead_time))


def safety_stock_combined(avg_demand: float, demand_std: float, avg_lead: float,
                          lead_std: float, service_level: float = 0.95) -> float:
    z = z_for_service(service_level)
    return z * math.sqrt(avg_lead * demand_std ** 2 + (avg_demand ** 2) * lead_std ** 2)


def reorder_point(avg_demand: float, lead_time: float, ss: float) -> float:
    return avg_demand * lead_time + ss


def gmroi(gross_margin_eur: float, avg_inventory_cost: float) -> float:
    return round(gross_margin_eur / avg_inventory_cost, 2) if avg_inventory_cost else 0.0


def reorder_recommendation(demand_history: list[float], on_hand: float,
                           lead_time_periods: float, abc_class: str = "B",
                           lead_std: float = 0.0) -> dict:
    """Given a monthly demand history, current on-hand and a lead time, decide
    whether to reorder and how much (order-up-to ROP + one lead time of cover)."""
    if len(demand_history) < 2:
        return {"reorder": False, "reason": "insufficient history"}
    avg = statistics.mean(demand_history)
    sd = statistics.pstdev(demand_history)
    sl = SERVICE_BY_ABC.get(abc_class, 0.95)
    ss = (safety_stock_combined(avg, sd, lead_time_periods, lead_std, sl)
          if lead_std else safety_stock(sd, lead_time_periods, sl))
    rop = reorder_point(avg, lead_time_periods, ss)
    order_up_to = rop + avg * lead_time_periods         # cover + one more lead time
    qty = max(0.0, order_up_to - on_hand)
    return {
        "abc_class": abc_class, "service_level": sl,
        "avg_demand": round(avg, 1), "demand_std": round(sd, 1),
        "safety_stock": round(ss, 1), "reorder_point": round(rop, 1),
        "on_hand": round(on_hand, 1),
        "reorder": on_hand <= rop,
        "recommended_order_qty": round(qty, 1) if on_hand <= rop else 0.0,
    }
