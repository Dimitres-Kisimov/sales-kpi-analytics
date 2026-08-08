"""Tests for sales pacing & target attainment (run-rate projection with an interval).

The load-bearing properties, checked by independent recomputation rather than by
trusting the module:

  * the fiscal calendar is correct (calendar and non-January fiscal years);
  * YTD, the seasonally-paced plan-to-date and the pace index are the hand-computed
    figures from the raw monthly series;
  * the projection is exactly the CV-selected forecaster applied to the remaining
    months (on this data: seasonal-naive → last year's Q4), so projected full-year =
    YTD + last-year-Q4, to the cent;
  * the prediction interval equals z · σ(backtest errors) · √remaining, recomputed
    straight from `forecast.rolling_origin_errors`;
  * attainment %, the euro gap and the attainment range are internally consistent;
  * it collapses to the clean base case on a *closed* fiscal year (projection ==
    YTD == realised, zero-width interval);
  * the realised full-year is a genuine back-check the closed synthetic year enables;
  * it is deterministic, and the rendered bullet chart's euro labels equal the source
    numbers to the cent (screen == source).
"""
from __future__ import annotations

import math
import re
import statistics
from importlib.util import find_spec
from statistics import NormalDist

from saleskpi import pacing
from saleskpi.dataset import monthly_series
from saleskpi.forecast import CANDIDATES, rolling_origin_errors

# every euro amount shown on the bullet chart, e.g. "€10,911,669.85"
_EUR = re.compile(r"&#8364;([0-9,]+\.[0-9]{2})")
_AS_OF = "2025-09"          # end of Q3 FY2025 — a real in-year pacing checkpoint


def _screen_numbers(svg: str) -> set[float]:
    return {round(float(m.replace(",", "")), 2) for m in _EUR.findall(svg)}


def _monthly(rows) -> dict[str, float]:
    """Monthly revenue with the same rounding the module's series helper uses."""
    return dict(monthly_series(rows, "revenue_eur"))


# --------------------------------------------------------------------------- #
# Fiscal calendar
# --------------------------------------------------------------------------- #
def test_fiscal_months_calendar_year():
    label, months = pacing.fiscal_months("2025-09", fiscal_start_month=1)
    assert label == "FY2025"
    assert months[0] == "2025-01" and months[-1] == "2025-12"
    assert len(months) == 12
    assert months.index("2025-09") == 8          # 9th month -> elapsed 9


def test_fiscal_months_non_january_start():
    # a fiscal year starting in October: 2025-11 is the 2nd month of FY2025/2026
    label, months = pacing.fiscal_months("2025-11", fiscal_start_month=10)
    assert label == "FY2025/2026"
    assert months[0] == "2025-10" and months[-1] == "2026-09"
    assert months.index("2025-11") == 1


# --------------------------------------------------------------------------- #
# Pace, projection and attainment — hand-checked against the raw series
# --------------------------------------------------------------------------- #
def test_available_and_period_split(real_rows):
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["available"] is True
    assert a["fiscal_year"] == "FY2025"
    assert a["months_elapsed"] == 9 and a["months_remaining"] == 3
    assert a["period_elapsed"] == "2025-01..2025-09"
    assert a["period_remaining"] == "2025-10..2025-12"


def test_ytd_and_target_are_hand_computed(real_rows):
    ms = _monthly(real_rows)
    ytd = round(sum(ms[f"2025-{m:02d}"] for m in range(1, 10)), 2)
    prior_fy = round(sum(ms[f"2024-{m:02d}"] for m in range(1, 13)), 2)
    target = round(prior_fy * (1 + pacing.PLAN_GROWTH_PCT), 2)

    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["ytd_actual_eur"] == ytd
    assert a["prior_fy_revenue_eur"] == prior_fy
    assert a["annual_target_eur"] == target
    assert a["target_is_assumed"] is True
    assert a["plan_growth_pct"] == round(100 * pacing.PLAN_GROWTH_PCT, 2)


def test_seasonalized_pace_and_index(real_rows):
    ms = _monthly(real_rows)
    ytd = round(sum(ms[f"2025-{m:02d}"] for m in range(1, 10)), 2)
    prior_fy = round(sum(ms[f"2024-{m:02d}"] for m in range(1, 13)), 2)
    target = round(prior_fy * (1 + pacing.PLAN_GROWTH_PCT), 2)
    prior_elapsed = sum(ms[f"2024-{m:02d}"] for m in range(1, 10))   # Jan..Sep prior FY
    expected = round(target * (prior_elapsed / prior_fy), 2)

    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["pace_basis"] == "seasonalized"
    assert a["seasonalized_expected_eur"] == expected
    assert a["expected_to_date_eur"] == expected
    assert a["pace_gap_eur"] == round(ytd - expected, 2)
    assert a["pace_index"] == round(ytd / expected, 4)


def test_projection_is_the_seasonal_naive_last_year_quarter(real_rows):
    """On this data the CV winner is seasonal-naive, so the projected remaining
    months are exactly last year's Q4 — a meaning-level check of the projection."""
    ms = _monthly(real_rows)
    ytd = round(sum(ms[f"2025-{m:02d}"] for m in range(1, 10)), 2)
    last_year_q4 = ms["2024-10"] + ms["2024-11"] + ms["2024-12"]

    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["forecast_model"] == "seasonal_naive"
    assert a["projection_method"] == "model"
    assert a["projected_remaining_eur"] == round(last_year_q4, 2)
    assert a["projected_full_year_eur"] == round(ytd + last_year_q4, 2)
    # simple annualise-the-YTD run-rate is the other, cruder projection
    assert a["simple_run_rate_projection_eur"] == round(ytd / 9 * 12, 2)


def test_prediction_interval_matches_backtest_errors(real_rows):
    """Interval half-width = z · σ(rolling-origin errors) · √remaining, recomputed
    straight from the forecast engine — the interval is empirical, not invented."""
    ms = _monthly(real_rows)
    hist = [v for m, v in sorted(ms.items()) if m <= _AS_OF]
    errs = rolling_origin_errors(hist, CANDIDATES["seasonal_naive"], horizon=1)
    sigma = round(statistics.stdev(errs), 2)
    z = NormalDist().inv_cdf(0.5 + pacing.DEFAULT_INTERVAL / 2)
    hw = round(z * sigma * math.sqrt(3), 2)

    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["backtest_folds"] == len(errs)
    assert a["backtest_error_sigma_eur"] == sigma
    assert a["interval_half_width_eur"] == hw
    assert a["interval_low_eur"] == round(a["projected_full_year_eur"] - hw, 2)
    assert a["interval_high_eur"] == round(a["projected_full_year_eur"] + hw, 2)


def test_attainment_arithmetic_is_consistent(real_rows):
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    t = a["annual_target_eur"]
    assert a["projected_attainment_pct"] == round(100 * a["projected_full_year_eur"] / t, 2)
    assert a["gap_to_target_eur"] == round(a["projected_full_year_eur"] - t, 2)
    assert a["attainment_low_pct"] == round(100 * a["interval_low_eur"] / t, 2)
    assert a["attainment_high_pct"] == round(100 * a["interval_high_eur"] / t, 2)
    # projected below plan on this data -> "behind plan" status, negative gap
    assert a["gap_to_target_eur"] < 0
    assert a["status"] == "behind plan — at risk"


def test_realized_backcheck_on_closed_year(real_rows):
    ms = _monthly(real_rows)
    realized = round(sum(ms[f"2025-{m:02d}"] for m in range(1, 13)), 2)
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    assert a["realized_full_year_eur"] == realized
    assert a["realized_attainment_pct"] == round(100 * realized / a["annual_target_eur"], 2)
    # the flag is exactly "did the realised value land inside the projected band?"
    inside = a["interval_low_eur"] <= realized <= a["interval_high_eur"]
    assert a["realized_within_interval"] is inside


# --------------------------------------------------------------------------- #
# Base case: a *closed* fiscal year collapses to plain attainment
# --------------------------------------------------------------------------- #
def test_collapses_to_completed_year(real_rows):
    ms = _monthly(real_rows)
    realized = round(sum(ms[f"2025-{m:02d}"] for m in range(1, 13)), 2)
    a = pacing.target_attainment(real_rows, as_of="2025-12")
    assert a["months_elapsed"] == 12 and a["months_remaining"] == 0
    assert a["projection_method"] == "actual"
    assert a["forecast_model"] is None
    # nothing left to project: projection == YTD == realised, zero-width interval
    assert a["ytd_actual_eur"] == realized
    assert a["projected_full_year_eur"] == realized
    assert a["interval_half_width_eur"] == 0.0
    assert a["interval_low_eur"] == a["interval_high_eur"] == realized
    assert a["realized_within_interval"] is True
    # annualising a full year returns the full year unchanged
    assert a["simple_run_rate_projection_eur"] == realized


# --------------------------------------------------------------------------- #
# Targets, availability, determinism
# --------------------------------------------------------------------------- #
def test_explicit_target_overrides_the_assumption(real_rows):
    a = pacing.target_attainment(real_rows, as_of=_AS_OF, annual_target_eur=10_000_000.0)
    assert a["target_is_assumed"] is False
    assert a["annual_target_eur"] == 10_000_000.0
    assert a["plan_growth_pct"] is None
    assert a["projected_attainment_pct"] == round(
        100 * a["projected_full_year_eur"] / 10_000_000.0, 2)


def test_unavailable_without_prior_year(tiny_rows):
    # a single month, no prior fiscal year to derive a target from
    a = pacing.target_attainment(tiny_rows)
    assert a["available"] is False
    assert "target" in a["reason"]


def test_explicit_target_works_without_history(tiny_rows):
    # tiny data (1 month, <13 points) falls back to the run-rate projection
    a = pacing.target_attainment(tiny_rows, annual_target_eur=5_000.0)
    assert a["available"] is True
    assert a["target_is_assumed"] is False
    assert a["months_elapsed"] == 1 and a["months_remaining"] == 11
    assert a["projection_method"] == "run_rate"
    assert a["ytd_actual_eur"] == 1000.0            # 100+200+300+400 (see conftest)
    assert a["projected_full_year_eur"] == 12000.0  # 1000/1 * 12
    assert a["interval_half_width_eur"] == 0.0       # no backtest on 1 point
    assert a["realized_full_year_eur"] is None       # year not closed in the data


def test_deterministic(real_rows):
    assert pacing.target_attainment(real_rows, as_of=_AS_OF) == \
        pacing.target_attainment(real_rows, as_of=_AS_OF)


def test_plain_language_reports_measured_numbers(real_rows):
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    text = pacing.plain_language(a)
    assert "FY2025" in text
    assert f"{a['projected_full_year_eur']:,.0f}" in text
    assert f"{a['projected_attainment_pct']:.1f}%" in text


def test_pacing_steps_mirror_the_attainment(real_rows):
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    st = pacing.pacing_steps(a)
    assert st["ytd_actual_eur"] == a["ytd_actual_eur"]
    assert st["projected_full_year_eur"] == a["projected_full_year_eur"]
    assert st["target_eur"] == a["annual_target_eur"]
    assert st["interval_low_eur"] == a["interval_low_eur"]
    assert st["realized_full_year_eur"] == a["realized_full_year_eur"]


# --------------------------------------------------------------------------- #
# The rendered bullet chart must equal the source numbers (screen == source)
# --------------------------------------------------------------------------- #
def test_svg_screen_equals_source(real_rows):
    from saleskpi.report import render_pacing_svg
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    shown = _screen_numbers(render_pacing_svg(a))
    st = pacing.pacing_steps(a)
    for name in ("ytd_actual_eur", "projected_remaining_eur", "projected_full_year_eur",
                 "interval_low_eur", "interval_high_eur", "target_eur",
                 "realized_full_year_eur"):
        val = round(st[name], 2)
        assert val in shown, f"{name} ({val:,.2f}) not shown on the bullet chart"


def test_svg_self_contained_and_deterministic(real_rows):
    from saleskpi.report import render_pacing_svg
    a = pacing.target_attainment(real_rows, as_of=_AS_OF)
    svg = render_pacing_svg(a)
    assert svg.strip() and svg.lstrip().startswith("<svg")
    assert "href" not in svg and "src=" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")  # only the xmlns
    assert render_pacing_svg(a) == svg


def test_bullet_written_as_deliverable(real_rows, tmp_path):
    from saleskpi.report import analyze, write_deliverables
    made = write_deliverables(analyze(real_rows), outdir=tmp_path)
    assert "pacing_bullet.svg" in made
    svg = (tmp_path / "pacing_bullet.svg").read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg")
    if find_spec("matplotlib"):
        assert "pacing_bullet.png" in made
        assert (tmp_path / "pacing_bullet.png").stat().st_size > 0
