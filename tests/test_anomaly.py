"""Tests for the KPI exception monitor (robust statistical process control).

The load-bearing properties: the robust statistics match their textbook formulas;
the control chart reconciles to itself (a flagged month is exactly a month outside
its limits, and the alert list has one entry per flagged month); the shipped OTIF
finding is the measured, deterministic one (six peak-season months out of control);
the seasonal-adjustment path removes a pure seasonal pattern without false alarms
yet still catches an injected spike; and the rendered control-chart SVG's numbers
equal the computed centre, limits and flagged values to the cent (screen == source).
"""
from __future__ import annotations

import re
import statistics
from importlib.util import find_spec

from saleskpi import anomaly

# any number printed on the chart, e.g. "86.46", "1,458.86", "79.04"
_NUM = re.compile(r"([0-9][0-9,]*\.[0-9]{2})")

_MONITORED = {"gross_margin_pct", "otif_pct", "returns_rate_pct",
              "discount_leakage_pct", "aov_eur"}
# peak-demand months the generator degrades delivery in (season > 1.12)
_PEAK = ("-05", "-09", "-10")


def _screen_numbers(svg: str) -> set[float]:
    return {round(float(m.replace(",", "")), 2) for m in _NUM.findall(svg)}


# --------------------------------------------------------------------------- #
# Robust statistics
# --------------------------------------------------------------------------- #
def test_mad_and_modified_z_hand_checked():
    vals = [2.0, 4.0, 6.0, 8.0, 10.0]          # median 6, |dev| = 4,2,0,2,4 -> MAD 2
    assert anomaly.median_abs_deviation(vals) == 2.0
    assert abs(anomaly.robust_scale(vals) - 2.0 / 0.6745) < 1e-9
    z = anomaly.modified_z(vals)
    # modified z = 0.6745*(x-6)/2  ->  0.6745*(-4)/2 = -1.349 at the ends
    assert abs(z[0] - (0.6745 * (2.0 - 6.0) / 2.0)) < 1e-9
    assert z[2] == 0.0                          # the median scores exactly zero


def test_flat_series_has_no_dispersion_and_no_flags():
    z = anomaly.modified_z([5.0] * 12)
    assert z == [0.0] * 12                       # constant series: no divide-by-zero
    assert anomaly.robust_scale([5.0] * 12) == 0.0


def test_mad_zero_but_not_constant_falls_back():
    # tie-heavy series: MAD collapses to 0 but the outlier must still be scored
    vals = [10.0, 10.0, 10.0, 10.0, 10.0, 25.0]
    assert anomaly.median_abs_deviation(vals) == 0.0
    assert anomaly.robust_scale(vals) > 0.0      # mean-absolute-deviation fallback
    assert anomaly.modified_z(vals)[-1] > 0.0


# --------------------------------------------------------------------------- #
# The monthly KPI table reconciles to the existing KPI engine
# --------------------------------------------------------------------------- #
def test_monthly_table_reconciles_to_kpi_summary(real_rows):
    from saleskpi import metrics
    table = anomaly.monthly_kpi_table(real_rows)
    k = metrics.kpi_summary(real_rows)
    assert len(table) == 24
    assert round(sum(row["revenue_eur"] for row in table), 2) == k["revenue_eur"]
    assert sum(row["orders"] for row in table) == k["orders"]


# --------------------------------------------------------------------------- #
# Exception detection — structure, reconciliation, the measured finding
# --------------------------------------------------------------------------- #
def test_exceptions_reconcile_to_limits(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    assert set(exc["series"]) == _MONITORED
    assert exc["months"] == 24
    for chart in exc["series"].values():
        outside = 0
        for p in chart["points"]:
            beyond = p["value"] < chart["lower_limit"] or p["value"] > chart["upper_limit"]
            # a month is flagged iff its value sits outside the control band
            assert p["flagged"] == beyond, f"{chart['kpi']} {p['month']} flag/limit mismatch"
            outside += beyond
        assert chart["n_flagged"] == outside
        # one alert per flagged month for this KPI
        kpi_alerts = [a for a in exc["alerts"] if a["kpi"] == chart["kpi"]]
        assert len(kpi_alerts) == chart["n_flagged"]
    assert exc["summary"]["total_alerts"] == len(exc["alerts"])


def test_otif_exceptions_are_the_measured_peak_season_six(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    otif = [a for a in exc["alerts"] if a["kpi"] == "otif_pct"]
    # deterministic data: exactly the six peak-demand months break the lower limit
    assert len(otif) == 6
    for a in otif:
        assert a["month"].endswith(_PEAK), f"{a['month']} not a peak-season month"
        assert a["direction"] == "below"
        assert a["favorable"] is False           # OTIF falling is unfavourable
        assert a["value"] < exc["series"]["otif_pct"]["lower_limit"]


def test_other_kpis_in_control_on_this_data(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    for kpi in ("gross_margin_pct", "returns_rate_pct", "discount_leakage_pct", "aov_eur"):
        assert exc["series"][kpi]["n_flagged"] == 0
    assert set(exc["summary"]["kpis_in_control"]) == {
        "Gross margin %", "Returns rate %", "Discount leakage %", "Average order value"}
    assert exc["summary"]["unfavorable"] == 6
    assert exc["summary"]["favorable"] == 0


def test_alerts_sorted_worst_first(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    rank = {"severe": 0, "elevated": 1}
    keys = [(rank[a["severity"]], -abs(a["modified_z"])) for a in exc["alerts"]]
    assert keys == sorted(keys)
    # the worst alert is the most extreme month
    assert exc["alerts"][0]["severity"] == "severe"
    assert abs(exc["alerts"][0]["modified_z"]) == max(
        abs(a["modified_z"]) for a in exc["alerts"])


def test_polarity_read_matches_direction(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    polarity = {s["kpi"]: s["polarity"] for s in anomaly.KPI_SPECS}
    for a in exc["alerts"]:
        pol = polarity[a["kpi"]]
        if pol == "neutral":
            assert a["favorable"] is None
        elif a["direction"] == "above":
            assert a["favorable"] is (pol == "higher_is_better")
        else:
            assert a["favorable"] is (pol == "lower_is_better")


def test_shipped_specs_are_non_seasonal(real_rows):
    # the shipped KPI set uses the raw robust chart (documented scope); volume
    # series are intentionally not among the monitored KPIs
    assert all(not s["seasonal"] for s in anomaly.KPI_SPECS)
    monitored = set(anomaly.kpi_exceptions(real_rows)["monitored_kpis"])
    assert "revenue_eur" not in monitored and "orders" not in monitored


def test_exceptions_deterministic(real_rows):
    assert anomaly.kpi_exceptions(real_rows) == anomaly.kpi_exceptions(real_rows)


def test_plain_language_reports_measured_counts(real_rows):
    exc = anomaly.kpi_exceptions(real_rows)
    text = anomaly.plain_language(exc)
    assert "6 exception" in text and "OTIF" in text


def test_tiny_single_month_is_safe(tiny_rows):
    exc = anomaly.kpi_exceptions(tiny_rows)   # all four orders share one month
    assert exc["months"] == 1
    assert exc["alerts"] == []                # no dispersion -> no false alarms


# --------------------------------------------------------------------------- #
# Seasonal-adjustment path (tested for completeness; off in the shipped set)
# --------------------------------------------------------------------------- #
def test_deseasonalize_removes_pure_seasonality():
    season = [0.82, 0.85, 1.02, 1.12, 1.18, 1.10, 0.95, 0.90, 1.15, 1.20, 1.05, 0.78]
    vals = [1000 * season[i % 12] for i in range(36)]     # flat level, pure season
    adj = anomaly.deseasonalize(vals, 12)
    # a purely seasonal series flattens out -> no month is an outlier (no false alarms)
    assert max(anomaly.modified_z(adj), key=abs) < 3.5
    assert statistics.pstdev(adj) < 1.0


def test_deseasonalize_still_catches_a_shock():
    season = [0.82, 0.85, 1.02, 1.12, 1.18, 1.10, 0.95, 0.90, 1.15, 1.20, 1.05, 0.78]
    vals = [1000 * season[i % 12] for i in range(36)]
    vals[18] *= 1.6                                        # a genuine spike
    adj = anomaly.deseasonalize(vals, 12)
    flagged = [i for i, z in enumerate(anomaly.modified_z(adj)) if abs(z) > 3.5]
    assert 18 in flagged                                  # the shock is detected


def test_deseasonalize_noop_when_too_short():
    vals = [1.0, 2.0, 3.0, 4.0]                            # < 2 full cycles
    assert anomaly.deseasonalize(vals, 12) == vals


# --------------------------------------------------------------------------- #
# The rendered control chart must equal the source numbers (screen == source)
# --------------------------------------------------------------------------- #
def test_control_chart_svg_screen_equals_source(real_rows):
    from saleskpi.report import _chart_to_render, render_control_chart_svg
    exc = anomaly.kpi_exceptions(real_rows)
    chart = _chart_to_render(exc)
    shown = _screen_numbers(render_control_chart_svg(chart, exc["k_sigma"]))
    # centre and both control limits are drawn, to the cent
    for key in ("center", "lower_limit", "upper_limit"):
        assert round(chart[key], 2) in shown, f"{key} not shown on the chart"
    # every out-of-control month's value is labelled on the chart
    for p in chart["points"]:
        if p["flagged"]:
            assert round(p["value"], 2) in shown, f"{p['month']} value not shown"


def test_control_chart_svg_self_contained_and_deterministic(real_rows):
    from saleskpi.report import _chart_to_render, render_control_chart_svg
    exc = anomaly.kpi_exceptions(real_rows)
    chart = _chart_to_render(exc)
    svg = render_control_chart_svg(chart, exc["k_sigma"])
    assert svg.strip() and svg.lstrip().startswith("<svg")
    assert "href" not in svg and "src=" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")  # only the xmlns
    assert render_control_chart_svg(chart, exc["k_sigma"]) == svg


def test_control_chart_written_as_deliverable(real_rows, tmp_path):
    from saleskpi.report import analyze, write_deliverables
    made = write_deliverables(analyze(real_rows), outdir=tmp_path)
    assert "kpi_control_chart.svg" in made
    svg = (tmp_path / "kpi_control_chart.svg").read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg")
    if find_spec("matplotlib"):
        assert "kpi_control_chart.png" in made
        assert (tmp_path / "kpi_control_chart.png").stat().st_size > 0
