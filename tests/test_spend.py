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


def _leak_row(rep, region, units, price, discount):
    """A minimal order row whose leakage is hand-computable: units*price*discount."""
    gross = units * price
    return {"sales_rep": rep, "region": region, "units": units, "list_price_eur": price,
            "discount_pct": discount, "revenue_eur": round(gross * (1 - discount), 2),
            "cost_eur": gross * 0.6}


def test_drilldown_decomposition_sums_to_total_leakage(real_rows):
    dd = spend.leakage_drilldown(real_rows)
    total = spend.discount_leakage(real_rows)
    assert abs(dd["total_leakage_eur"] - total) < 0.01
    # by-rep and by-region decompositions must each sum back to the total
    assert abs(sum(r["leakage_eur"] for r in dd["by_sales_rep"]) - total) < 1.0
    assert abs(sum(r["leakage_eur"] for r in dd["by_region"]) - total) < 1.0
    # and the policy split reconstructs it too
    assert abs(dd["within_policy_discount_eur"] + dd["excess_discount_eur"] - total) < 0.01


def test_drilldown_waterfall_segments_sum_to_gross(real_rows):
    dd = spend.leakage_drilldown(real_rows)
    walk = (dd["gross_list_value_eur"] - dd["within_policy_discount_eur"]
            - dd["excess_discount_eur"])
    assert abs(walk - dd["net_revenue_eur"]) < 0.01
    # net in the waterfall is the same revenue the KPI layer reports
    assert abs(dd["net_revenue_eur"] - sum(r["revenue_eur"] for r in real_rows)) < 0.01


def test_drilldown_covers_whole_dataset_no_orphans(real_rows):
    dd = spend.leakage_drilldown(real_rows)
    assert sum(r["orders"] for r in dd["by_sales_rep"]) == len(real_rows)
    assert sum(r["orders"] for r in dd["by_region"]) == len(real_rows)
    assert {r["sales_rep"] for r in dd["by_sales_rep"]} == {r["sales_rep"] for r in real_rows}
    assert {r["region"] for r in dd["by_region"]} == {r["region"] for r in real_rows}


def test_drilldown_offender_ranking_hand_checked():
    # 10 units x 10 EUR list each; policy 10%:
    #   Deep   25% discount -> leakage 25, excess 25*(0.15/0.25) = 15
    #   Mid    12% discount -> leakage 12, excess 12*(0.02/0.12) =  2
    #   Clean   5% discount -> leakage  5, excess 0
    rows = [_leak_row("Deep", "North", 10, 10.0, 0.25),
            _leak_row("Mid", "South", 10, 10.0, 0.12),
            _leak_row("Clean", "South", 10, 10.0, 0.05)]
    dd = spend.leakage_drilldown(rows, policy_pct=0.10)
    reps = [r["sales_rep"] for r in dd["by_sales_rep"]]
    assert reps == ["Deep", "Mid", "Clean"]
    top = dd["by_sales_rep"][0]
    assert abs(top["leakage_eur"] - 25.0) < 0.01
    assert abs(top["excess_eur"] - 15.0) < 0.01
    assert abs(top["within_policy_eur"] - 10.0) < 0.01
    assert top["orders_above_policy_pct"] == 100.0
    assert dd["by_sales_rep"][2]["excess_eur"] == 0.0
    assert abs(dd["total_leakage_eur"] - 42.0) < 0.01
    # South region aggregates Mid + Clean
    south = next(r for r in dd["by_region"] if r["region"] == "South")
    assert abs(south["leakage_eur"] - 17.0) < 0.01
    assert south["orders"] == 2


def test_drilldown_deterministic(real_rows):
    assert spend.leakage_drilldown(real_rows) == spend.leakage_drilldown(real_rows)


def test_drilldown_policy_at_cap_means_zero_excess(real_rows):
    # with the policy at 100% every discount is sanctioned: excess must vanish
    dd = spend.leakage_drilldown(real_rows, policy_pct=1.0)
    assert dd["excess_discount_eur"] == 0.0
    assert abs(dd["within_policy_discount_eur"] - dd["total_leakage_eur"]) < 0.01
    assert all(r["excess_eur"] == 0.0 for r in dd["by_sales_rep"])


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
