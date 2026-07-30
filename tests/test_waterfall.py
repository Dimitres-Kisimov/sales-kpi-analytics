"""Waterfall visualization tests — the number on screen must equal the source.

The discount-leakage waterfall is rendered from `spend.waterfall_steps`, the same
model the PNG uses. These tests render the offline SVG, read the euro labels back
off it, and assert they equal the leakage computed straight from the rows — so a
cosmetic figure that didn't reconcile would fail the build.
"""
from __future__ import annotations

import re
from importlib.util import find_spec

from saleskpi import spend
from saleskpi.report import analyze, render_leakage_svg, write_deliverables

# every euro amount shown on the chart, e.g. "€24,449,996.47" or "−€680,724.98"
_EUR = re.compile(r"&#8364;([0-9,]+\.[0-9]{2})")


def _screen_numbers(svg: str) -> set[float]:
    return {round(float(m.replace(",", "")), 2) for m in _EUR.findall(svg)}


def _source(rows, policy_pct=spend.POLICY_DISCOUNT_PCT):
    """The waterfall totals computed directly from the rows (no drill-down dict)."""
    raw_leak = spend.discount_leakage(rows)
    raw_excess = sum(spend._split_leakage(r, policy_pct)[1] for r in rows)
    return {
        "gross": round(sum(r["units"] * r["list_price_eur"] for r in rows), 2),
        "net": round(sum(r["revenue_eur"] for r in rows), 2),
        "total": round(raw_leak, 2),
        "excess": round(raw_excess, 2),
        "within": round(raw_leak - raw_excess, 2),
    }


def test_waterfall_screen_equals_source(real_rows):
    dd = spend.leakage_drilldown(real_rows)
    shown = _screen_numbers(render_leakage_svg(dd))
    src = _source(real_rows)
    # every source total is present, to the cent, as a label on the rendered chart
    for name, value in src.items():
        assert value in shown, f"{name} ({value:,.2f}) not shown on the waterfall"


def test_waterfall_reconstructs_to_leakage(real_rows):
    wf = spend.waterfall(real_rows)
    g = wf["gross_list_value_eur"]
    w = wf["within_policy_discount_eur"]
    e = wf["excess_discount_eur"]
    n = wf["net_revenue_eur"]
    # the walk ties out exactly
    assert abs(g - w - e - n) < 0.01
    # both discount cuts together are the leakage, which equals the headline metric
    assert abs(w + e - wf["total_leakage_eur"]) < 0.01
    assert abs(wf["total_leakage_eur"] - spend.discount_leakage(real_rows)) < 0.01
    # net is the revenue the KPI layer reports
    assert abs(n - sum(r["revenue_eur"] for r in real_rows)) < 0.01
    # the step geometry reconstructs the same walk
    steps = wf["steps"]
    assert [s["label"] for s in steps] == [
        "Gross list value", "Within-policy discounts", "Excess discounts", "Net revenue"]
    assert abs(steps[1]["value"] + w) < 0.01 and abs(steps[2]["value"] + e) < 0.01


def test_waterfall_deterministic(real_rows):
    assert spend.waterfall(real_rows) == spend.waterfall(real_rows)
    dd = spend.leakage_drilldown(real_rows)
    assert render_leakage_svg(dd) == render_leakage_svg(dd)


def test_leakage_svg_written_and_self_contained(real_rows, tmp_path):
    made = write_deliverables(analyze(real_rows), outdir=tmp_path)
    assert "leakage_waterfall.svg" in made
    svg = (tmp_path / "leakage_waterfall.svg").read_text(encoding="utf-8")
    assert svg.strip() and svg.lstrip().startswith("<svg")
    # offline / self-contained: no external asset references, no network fetches
    assert "href" not in svg and "src=" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")  # only the xmlns
    if find_spec("matplotlib"):
        assert "leakage_waterfall.png" in made
