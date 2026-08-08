"""pacing.py — sales pacing & target attainment (run-rate to plan, with an interval).

The one question a sales leader asks between the QBRs: *"are we on track to hit the
number?"* This module answers it for the current fiscal year:

  * **year-to-date (YTD)** revenue vs where the plan says we should be by now — paced
    on the prior year's *seasonal* shape, not a naïve straight line (a distributor's
    revenue is heavily seasonal, so a flat 1/12-per-month plan is misleading);
  * a **run-rate projection** of the full-year landing, made two ways: the simple
    "annualise the YTD" run-rate every exec knows, and a **model projection** that
    forecasts the remaining months with the same rolling-origin-CV-selected model the
    rest of the toolkit uses (`saleskpi.forecast`);
  * an **honest prediction interval** on that projection, built from the empirical
    out-of-sample errors of the chosen model (not a textbook σ pulled from thin air);
  * **attainment %** and the **euro gap to plan**, with the interval carried through
    to an attainment *range* — so the read is "≈96% of plan, 80% interval 94–97%",
    never a single false-precision number.

Because the shipped synthetic dataset is a *complete* two-year history, a pacing
snapshot taken mid-year can be scored against what actually happened: the module
reports the **realised** full-year figure and whether it fell inside the projected
interval — an out-of-sample back-check you can only do on closed periods.

Honest scope, stated up front:
  * The **plan** is a stated assumption, not a measured budget — the dataset carries
    no plan, so by default the target is `prior-FY revenue × (1 + PLAN_GROWTH_PCT)`.
    The growth rate is a parameter; every attainment number moves with it and the
    output labels it as assumed (the same discipline the discount-policy ceiling uses).
  * The projection is **modelled, not a promise.** The interval is a normal
    approximation over the model's empirical backtest errors, aggregated across the
    remaining months under an independence assumption — a reasonable, clearly-flagged
    simplification, and on only ~24 monthly points the backtest has few folds, so the
    band is indicative rather than exact. An 80% interval is expected to miss ~1 year
    in 5; when the realised value lands outside it, the module says so plainly.

Pure stdlib (`statistics.NormalDist` for the interval quantile, as the inventory
engine already uses it). Deterministic — the "as of" month is derived from the data,
never the wall clock, and nothing here draws on an RNG.

    from saleskpi.pacing import target_attainment
    att = target_attainment(rows)                 # completed-year attainment
    att = target_attainment(rows, as_of="2025-09")  # Q3 pacing + projection

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from statistics import NormalDist
from typing import Any

from .forecast import CANDIDATES, rolling_origin_errors, select_and_forecast

Rows = list[dict[str, Any]]

# Default planning assumption: the fiscal-year target is the prior FY's revenue grown
# by this rate. The dataset has no budget, so this is a *stated* assumption (a
# mildly-stretch plan against the ~+7% underlying trend), not a measured fact — it is
# a parameter everywhere and the output flags the target as assumed when it is derived.
PLAN_GROWTH_PCT = 0.08

# Central mass of the default prediction interval (80% is the common pacing band).
DEFAULT_INTERVAL = 0.80

# Attainment bands for the plain-language status (share of plan the projection lands).
_ON_TRACK = 100.0     # projected ≥ plan
_SLIGHTLY_BEHIND = 97.0   # within 3 pts of plan


# --------------------------------------------------------------------------- #
# Fiscal-calendar helpers (fiscal_start_month = 1 -> calendar year)
# --------------------------------------------------------------------------- #
def _add_month(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    idx = (y * 12 + (m - 1)) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def fiscal_months(as_of: str, fiscal_start_month: int = 1) -> tuple[str, list[str]]:
    """(fiscal-year label, the 12 ordered "YYYY-MM" months of the fiscal year that
    contains `as_of`). For `fiscal_start_month=1` this is the plain calendar year."""
    y, m = int(as_of[:4]), int(as_of[5:7])
    start_year = y if m >= fiscal_start_month else y - 1
    start = f"{start_year:04d}-{fiscal_start_month:02d}"
    months = [_add_month(start, i) for i in range(12)]
    label = f"FY{start_year}" if fiscal_start_month == 1 else f"FY{start_year}/{start_year + 1}"
    return label, months


def _monthly_revenue(rows: Rows) -> dict[str, float]:
    rev: dict[str, float] = defaultdict(float)
    for r in rows:
        rev[r["date"][:7]] += r["revenue_eur"]
    return dict(rev)


# --------------------------------------------------------------------------- #
# Target attainment & run-rate projection
# --------------------------------------------------------------------------- #
def target_attainment(rows: Rows, *, annual_target_eur: float | None = None,
                      as_of: str | None = None, fiscal_start_month: int = 1,
                      interval: float = DEFAULT_INTERVAL,
                      plan_growth_pct: float = PLAN_GROWTH_PCT) -> dict[str, Any]:
    """Pace the current fiscal year to plan and project the full-year landing.

    `as_of` (default: the latest month in the data) is the cut-off we stand at —
    everything up to and including it is actual, everything after is projected. The
    target defaults to `prior-FY revenue × (1 + plan_growth_pct)` (flagged as an
    assumption); pass `annual_target_eur` to use a real budget. Returns a rounded,
    JSON-ready dict; `available` is False when there isn't enough history to form a
    target and no explicit one was given.
    """
    if not rows:
        return {"available": False, "reason": "no rows"}
    rev = _monthly_revenue(rows)
    data_months = sorted(rev)
    as_of = as_of or data_months[-1]

    fy_label, fy_months = fiscal_months(as_of, fiscal_start_month)
    if as_of not in fy_months:            # as_of outside a clean FY position — clamp
        as_of = max(m for m in fy_months if m <= as_of)
    elapsed = fy_months.index(as_of) + 1
    remaining = 12 - elapsed
    elapsed_months = fy_months[:elapsed]
    remaining_months = fy_months[elapsed:]

    ytd_actual = round(sum(rev.get(m, 0.0) for m in elapsed_months), 2)

    # prior fiscal year (same 12 positions, one year earlier) — the target basis and
    # the seasonal-pace shape.
    prior_months = [_add_month(m, -12) for m in fy_months]
    prior_present = [m for m in prior_months if m in rev]
    prior_complete = len(prior_present) == 12
    prior_fy_actual = round(sum(rev.get(m, 0.0) for m in prior_months), 2)

    target_is_assumed = annual_target_eur is None
    if annual_target_eur is None:
        if not prior_complete:
            return {"available": False, "fiscal_year": fy_label, "as_of": as_of,
                    "reason": "no prior fiscal year to derive a target from; "
                              "pass annual_target_eur"}
        annual_target_eur = prior_fy_actual * (1.0 + plan_growth_pct)
    target = round(float(annual_target_eur), 2)

    # ---- pace: YTD vs where the plan says we should be by now --------------- #
    straight_line_expected = round(target * elapsed / 12, 2)
    seasonalized_expected = None
    if prior_complete and prior_fy_actual:
        prior_elapsed = sum(rev.get(_add_month(m, -12), 0.0) for m in elapsed_months)
        seasonal_share = prior_elapsed / prior_fy_actual
        seasonalized_expected = round(target * seasonal_share, 2)
    expected_to_date = (seasonalized_expected if seasonalized_expected is not None
                        else straight_line_expected)
    pace_gap = round(ytd_actual - expected_to_date, 2)
    pace_index = round(ytd_actual / expected_to_date, 4) if expected_to_date else None

    # ---- projection of the full-year landing ------------------------------- #
    history = [rev[m] for m in data_months if m <= as_of]
    simple_run_rate = round(ytd_actual / elapsed * 12, 2) if elapsed else None

    winner: str | None = None
    cv_mase: float | None = None
    method = "actual"
    proj_remaining = 0.0
    errors: list[float] = []
    if remaining > 0:
        if len(history) >= 13:            # enough for the CV-selected model + a backtest
            sel = select_and_forecast(history, horizon=remaining)
            winner, cv_mase = sel.winner, sel.cv_mase
            proj_remaining = sum(sel.values)
            errors = rolling_origin_errors(history, CANDIDATES[winner], horizon=1)
            method = "model"
        else:                             # too little history — fall back to the run-rate
            winner, method = "run_rate", "run_rate"
            proj_remaining = ytd_actual / elapsed * remaining if elapsed else 0.0

    projected_fy = round(ytd_actual + proj_remaining, 2)

    # ---- prediction interval from the model's empirical backtest errors ----- #
    backtest_sigma = round(statistics.stdev(errors), 2) if len(errors) >= 2 else 0.0
    backtest_bias = round(statistics.mean(errors), 2) if errors else 0.0
    z = NormalDist().inv_cdf(0.5 + interval / 2)
    half_width = round(z * backtest_sigma * math.sqrt(remaining), 2) if remaining > 0 else 0.0
    proj_low = round(projected_fy - half_width, 2)
    proj_high = round(projected_fy + half_width, 2)

    # ---- attainment -------------------------------------------------------- #
    def att(v: float) -> float:
        return round(100 * v / target, 2) if target else 0.0

    projected_attainment = att(projected_fy)
    gap_to_target = round(projected_fy - target, 2)
    status = _status(projected_attainment)

    # ---- back-check: realised landing, when the FY has already closed -------- #
    realized_complete = all(m in rev for m in remaining_months) if remaining else True
    realized_fy = realized_attainment = None
    realized_in_interval: bool | None = None
    if realized_complete:
        realized_fy = round(sum(rev.get(m, 0.0) for m in fy_months), 2)
        realized_attainment = att(realized_fy)
        realized_in_interval = proj_low <= realized_fy <= proj_high

    return {
        "available": True,
        "fiscal_year": fy_label,
        "as_of": as_of,
        "fiscal_start_month": fiscal_start_month,
        "months_elapsed": elapsed,
        "months_remaining": remaining,
        "period_elapsed": f"{elapsed_months[0]}..{elapsed_months[-1]}",
        "period_remaining": (f"{remaining_months[0]}..{remaining_months[-1]}"
                             if remaining_months else ""),
        # target / plan
        "annual_target_eur": target,
        "target_is_assumed": target_is_assumed,
        "plan_growth_pct": round(100 * plan_growth_pct, 2) if target_is_assumed else None,
        "prior_fy_revenue_eur": prior_fy_actual if prior_complete else None,
        "target_note": (
            f"assumed plan = prior-FY revenue x (1 + {100 * plan_growth_pct:.1f}%); "
            "the dataset carries no budget, so every attainment figure moves with this "
            "rate (a stated assumption, not a measured target)"
            if target_is_assumed else "explicit target supplied by caller"),
        # pace
        "ytd_actual_eur": ytd_actual,
        "straight_line_expected_eur": straight_line_expected,
        "seasonalized_expected_eur": seasonalized_expected,
        "expected_to_date_eur": expected_to_date,
        "pace_basis": "seasonalized" if seasonalized_expected is not None else "straight_line",
        "pace_gap_eur": pace_gap,
        "pace_index": pace_index,
        # projection
        "projection_method": method,
        "forecast_model": winner,
        "forecast_cv_mase": cv_mase,
        "simple_run_rate_projection_eur": simple_run_rate,
        "projected_remaining_eur": round(proj_remaining, 2),
        "projected_full_year_eur": projected_fy,
        # interval
        "interval": interval,
        "interval_low_eur": proj_low,
        "interval_high_eur": proj_high,
        "interval_half_width_eur": half_width,
        "backtest_folds": len(errors),
        "backtest_error_sigma_eur": backtest_sigma,
        "backtest_bias_eur": backtest_bias,
        # attainment
        "projected_attainment_pct": projected_attainment,
        "attainment_low_pct": att(proj_low),
        "attainment_high_pct": att(proj_high),
        "gap_to_target_eur": gap_to_target,
        "status": status,
        # back-check (available only on a closed fiscal year)
        "realized_full_year_eur": realized_fy,
        "realized_attainment_pct": realized_attainment,
        "realized_within_interval": realized_in_interval,
    }


def _status(attainment_pct: float) -> str:
    """Plain-language pacing verdict from the projected attainment percentage."""
    if attainment_pct >= _ON_TRACK:
        return "on track to meet or beat plan"
    if attainment_pct >= _SLIGHTLY_BEHIND:
        return "slightly behind plan"
    return "behind plan — at risk"


def plain_language(att: dict[str, Any]) -> str:
    """A one-line read of the pacing, e.g. 'As of 2025-09 (Q3, 9/12 months), FY2025
    is projected to land at €10,911,670 — 95.7% of the €11,400,851 plan (€489,181
    short); status: behind plan — at risk.'"""
    if not att.get("available"):
        return "Target attainment unavailable (no plan basis; supply a target)."
    q = (att["months_elapsed"] + 2) // 3
    gap = att["gap_to_target_eur"]
    return (f"As of {att['as_of']} (Q{q}, {att['months_elapsed']}/12 months), "
            f"{att['fiscal_year']} is projected to land at "
            f"€{att['projected_full_year_eur']:,.0f} — "
            f"{att['projected_attainment_pct']:.1f}% of the "
            f"€{att['annual_target_eur']:,.0f} plan "
            f"({'+' if gap >= 0 else '−'}€{abs(gap):,.0f}); "
            f"status: {att['status']}.")


# --------------------------------------------------------------------------- #
# The single source of truth a pacing bullet chart draws (SVG + tests consume it)
# --------------------------------------------------------------------------- #
def pacing_steps(att: dict[str, Any]) -> dict[str, Any]:
    """The exact values a pacing "bullet" chart renders — the YTD-actual and
    projected-remaining segments, the projection interval whisker, the target
    marker and (when the year has closed) the realised marker. Consumed by the SVG
    renderer and asserted against in the tests, so the picture cannot drift from the
    numbers. Every euro figure here is one already computed in `target_attainment`.
    """
    return {
        "fiscal_year": att["fiscal_year"],
        "as_of": att["as_of"],
        "ytd_actual_eur": att["ytd_actual_eur"],
        "projected_remaining_eur": att["projected_remaining_eur"],
        "projected_full_year_eur": att["projected_full_year_eur"],
        "interval_low_eur": att["interval_low_eur"],
        "interval_high_eur": att["interval_high_eur"],
        "target_eur": att["annual_target_eur"],
        "expected_to_date_eur": att["expected_to_date_eur"],
        "realized_full_year_eur": att["realized_full_year_eur"],
        "projected_attainment_pct": att["projected_attainment_pct"],
        "status": att["status"],
    }
