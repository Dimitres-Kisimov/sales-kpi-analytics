"""Tests for the revenue price/volume/mix (PVM) bridge.

The load-bearing invariant is that the three effects reconstruct the total
revenue change *exactly* — that's what makes a PVM bridge trustworthy rather
than decorative. These tests pin price and volume to their stated formulas,
force the three effects to sum to the total to the cent, check the per-category
rows tie back to the headline, and read the euro labels off the rendered SVG to
assert the picture equals the source.
"""
from __future__ import annotations

import re
from collections import defaultdict
from importlib.util import find_spec

from saleskpi import pvm

# every euro amount shown on the chart, e.g. "€722,407.10" or "−€675,373.38"
_EUR = re.compile(r"&#8364;([0-9,]+\.[0-9]{2})")


def _screen_numbers(svg: str) -> set[float]:
    return {round(float(m.replace(",", "")), 2) for m in _EUR.findall(svg)}


def _formula_price_volume(rows):
    """Price = Σ(Δprice·units_now) and pure-volume = revenue_prior·(λ−1),
    recomputed independently of the module from the raw rows."""
    _, _, prior, current = pvm._yoy_split(rows)

    def agg(rs):
        g = defaultdict(lambda: {"u": 0.0, "r": 0.0})
        for r in rs:
            g[r["product_category"]]["u"] += r["units"]
            g[r["product_category"]]["r"] += r["revenue_eur"]
        return g

    a0, a1 = agg(prior), agg(current)
    q0 = sum(v["u"] for v in a0.values())
    q1 = sum(v["u"] for v in a1.values())
    r0 = sum(v["r"] for v in a0.values())
    lam = q1 / q0
    price = 0.0
    for k in set(a0) | set(a1):
        u0, u1 = a0.get(k, {}).get("u", 0.0), a1.get(k, {}).get("u", 0.0)
        rv0, rv1 = a0.get(k, {}).get("r", 0.0), a1.get(k, {}).get("r", 0.0)
        p0 = (rv0 / u0) if u0 else 0.0
        p1 = (rv1 / u1) if u1 else 0.0
        price += (p1 - p0) * u1
    volume = r0 * (lam - 1.0)
    return round(price, 2), round(volume, 2)


def test_bridge_available_on_real_data(real_rows):
    b = pvm.revenue_bridge(real_rows)
    assert b["available"] is True
    assert b["dimension"] == "product_category"
    assert b["by_category"], "expected at least one category row"


def test_effects_sum_to_total_exactly(real_rows):
    """The strong invariant: price + volume + mix == total revenue change, to the cent."""
    b = pvm.revenue_bridge(real_rows)
    parts = b["price_effect_eur"] + b["volume_effect_eur"] + b["mix_effect_eur"]
    assert round(parts, 2) == b["total_change_eur"]
    # and the total change is exactly current − prior revenue
    assert round(b["current_revenue_eur"] - b["prior_revenue_eur"], 2) == b["total_change_eur"]


def test_price_and_volume_match_stated_formulas(real_rows):
    b = pvm.revenue_bridge(real_rows)
    price, volume = _formula_price_volume(real_rows)
    assert abs(b["price_effect_eur"] - price) < 0.01
    assert abs(b["volume_effect_eur"] - volume) < 0.01
    # mix is therefore the residual, to the cent
    assert abs(b["mix_effect_eur"] - (b["total_change_eur"] - price - volume)) < 0.02


def test_by_category_sums_to_headline(real_rows):
    b = pvm.revenue_bridge(real_rows)
    for field in ("price_effect_eur", "volume_effect_eur", "mix_effect_eur",
                  "prior_revenue_eur", "current_revenue_eur"):
        got = round(sum(c[field] for c in b["by_category"]), 2)
        assert abs(got - b[field]) < 0.05, f"{field}: rows sum {got} vs headline {b[field]}"
    # per-category rows individually reconcile: price+volume+mix == Δrevenue
    for c in b["by_category"]:
        delta = c["current_revenue_eur"] - c["prior_revenue_eur"]
        parts = c["price_effect_eur"] + c["volume_effect_eur"] + c["mix_effect_eur"]
        assert abs(parts - delta) < 0.02, f"{c['product_category']} does not reconcile"


def test_bridge_deterministic(real_rows):
    assert pvm.revenue_bridge(real_rows) == pvm.revenue_bridge(real_rows)


def test_waterfall_steps_walk_ties_out(real_rows):
    b = pvm.revenue_bridge(real_rows)
    steps = pvm.bridge_waterfall_steps(b)
    assert [s["label"] for s in steps] == [
        "Prior revenue", "Price", "Volume", "Mix", "Current revenue"]
    # walking prior + price + volume + mix lands on current, to the cent
    run = steps[0]["value"]
    for s in steps[1:-1]:
        run += s["value"]
    assert round(run, 2) == b["current_revenue_eur"]


def test_plain_language_reports_measured_numbers(real_rows):
    b = pvm.revenue_bridge(real_rows)
    text = pvm.plain_language(b)
    assert "Revenue" in text
    # the rounded total appears in the sentence
    assert f"{abs(b['total_change_eur']):,.0f}" in text


def test_unavailable_without_two_years(tiny_rows):
    b = pvm.revenue_bridge(tiny_rows)
    assert b["available"] is False


# --------------------------------------------------------------------------- #
# The rendered SVG must equal the source numbers (screen == source)
# --------------------------------------------------------------------------- #
def test_svg_screen_equals_source(real_rows):
    from saleskpi.report import render_pvm_svg
    b = pvm.revenue_bridge(real_rows)
    shown = _screen_numbers(render_pvm_svg(b))
    for name in ("prior_revenue_eur", "current_revenue_eur", "total_change_eur",
                 "price_effect_eur", "volume_effect_eur", "mix_effect_eur"):
        val = round(abs(b[name]), 2)
        assert val in shown, f"{name} ({val:,.2f}) not shown on the waterfall"


def test_svg_self_contained_and_deterministic(real_rows):
    from saleskpi.report import render_pvm_svg
    b = pvm.revenue_bridge(real_rows)
    svg = render_pvm_svg(b)
    assert svg.strip() and svg.lstrip().startswith("<svg")
    assert "href" not in svg and "src=" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")  # only the xmlns
    assert render_pvm_svg(b) == render_pvm_svg(b)


def test_csv_and_svg_written(real_rows, tmp_path):
    from saleskpi.report import analyze, write_deliverables
    made = write_deliverables(analyze(real_rows), outdir=tmp_path)
    assert "pvm_bridge.csv" in made
    assert "pvm_waterfall.svg" in made
    csv_text = (tmp_path / "pvm_bridge.csv").read_text(encoding="utf-8")
    assert "TOTAL" in csv_text and "price_effect_eur" in csv_text
    if find_spec("matplotlib"):
        assert "pvm_waterfall.png" in made
