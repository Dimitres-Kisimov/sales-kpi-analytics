"""Tests for the KPI / portfolio / customer metrics engine."""
from __future__ import annotations

from saleskpi import metrics


def test_kpi_summary_totals(tiny_rows):
    k = metrics.kpi_summary(tiny_rows)
    assert k["revenue_eur"] == 1000.0
    assert k["cost_eur"] == 570.0
    assert k["gross_margin_eur"] == 430.0
    assert k["gross_margin_pct"] == 43.0
    assert k["orders"] == 4
    assert k["units"] == 100
    assert k["aov_eur"] == 250.0
    assert k["active_customers"] == 2
    # OTIF = orders that are BOTH on_time and in_full -> only O1 and O4 -> 50%
    assert k["otif_pct"] == 50.0
    # one of four returned
    assert k["returns_rate_pct"] == 25.0


def test_kpi_summary_empty_is_safe():
    k = metrics.kpi_summary([])
    assert k["orders"] == 0
    assert k["revenue_eur"] == 0
    assert k["otif_pct"] == 0.0


def test_abc_xyz_classes_valid(real_rows):
    rows = metrics.abc_xyz(real_rows, "product_category")
    assert rows, "expected at least one category"
    for r in rows:
        assert r["abc"] in {"A", "B", "C"}
        assert r["xyz"] in {"X", "Y", "Z"}
        assert r["class"] == r["abc"] + r["xyz"]
        assert 0 <= r["revenue_share_pct"] <= 100
    # cumulative Pareto: the first (largest) category must be class A
    assert rows[0]["abc"] == "A"
    # every ABC band that exists is represented across the portfolio
    seen = {r["abc"] for r in rows}
    assert "A" in seen


def test_rfm_scores_and_segments(real_rows):
    custs = metrics.rfm(real_rows)
    assert custs
    valid_segments = {
        "Champions", "Loyal / high-value", "At risk",
        "Churned / dormant", "Developing",
    }
    for c in custs:
        for k in ("R", "F", "M"):
            assert 1 <= c[k] <= 5, f"{k} score out of range"
        assert c["rfm_score"] == c["R"] + c["F"] + c["M"]
        assert c["segment"] in valid_segments
    # at least two distinct segments should appear on real data
    assert len({c["segment"] for c in custs}) >= 2


def test_margin_bridge_reconciles(real_rows):
    b = metrics.margin_bridge(real_rows)
    assert b["available"] is True
    parts = b["price_effect_eur"] + b["volume_effect_eur"] + b["mix_effect_eur"]
    # price + volume + mix must reconstruct the total margin change
    assert abs(parts - b["total_change_eur"]) < 1.0
    assert abs((b["current_margin_eur"] - b["prior_margin_eur"]) - b["total_change_eur"]) < 1.0


def test_concentration_top_share_in_range(real_rows):
    c = metrics.concentration(real_rows)
    assert 0 < c["top_share_pct"] <= 100
    assert c["customers"] > 0


def test_by_dimension_sums_to_total(tiny_rows):
    total_rev = metrics.kpi_summary(tiny_rows)["revenue_eur"]
    by_region = metrics.by_dimension(tiny_rows, "region")
    assert round(sum(r["revenue_eur"] for r in by_region), 2) == total_rev
    # sorted descending by revenue
    revs = [r["revenue_eur"] for r in by_region]
    assert revs == sorted(revs, reverse=True)
