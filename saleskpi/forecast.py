"""forecast.py — demand forecasting with honest, out-of-sample model selection.

A distributor's SKUs range from steady fast-movers to lumpy long-tail MRO items,
so no single model wins. This module implements a small library of classical
forecasters and picks the best one PER SERIES by rolling-origin (walk-forward)
cross-validation scored with MASE — the industry-correct way, not a leaderboard
of one global model.

Models:
  naive · seasonal_naive · moving_average · ses (simple exp. smoothing) ·
  holt_winters (additive triple exp. smoothing) · croston · sba (Syntetos-Boylan)

Evaluation:
  rolling-origin CV (expanding window) + MAE / RMSE / MAPE / sMAPE / MASE.
  MASE < 1 means the model beats the seasonal-naive baseline. It is scale-free
  (comparable across SKUs) and defined at zero demand (works for intermittent).

References: Hyndman & Koehler 2006 (MASE); Croston 1972; Syntetos-Boylan 2005;
Hyndman FPP3 §5.10 (rolling-origin). See docs/METHODOLOGY.md.

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass

Series = list[float]
Model = Callable[[Series, int], Series]        # (history, horizon) -> forecast


# --------------------------------------------------------------------------- #
# Models — each maps (history, horizon) -> list[forecast] of length `horizon`
# --------------------------------------------------------------------------- #
def naive(y: Series, h: int) -> Series:
    return [y[-1]] * h if y else [0.0] * h


def seasonal_naive(m: int = 12) -> Model:
    def f(y: Series, h: int) -> Series:
        if len(y) < m:
            return naive(y, h)
        return [y[-m + (i % m)] for i in range(h)]
    return f


def moving_average(k: int = 3) -> Model:
    def f(y: Series, h: int) -> Series:
        if not y:
            return [0.0] * h
        return [sum(y[-k:]) / min(k, len(y))] * h
    return f


def ses(alpha: float = 0.3) -> Model:
    def f(y: Series, h: int) -> Series:
        if not y:
            return [0.0] * h
        level = y[0]
        for v in y[1:]:
            level = alpha * v + (1 - alpha) * level
        return [level] * h
    return f


def holt_winters(m: int = 12, alpha: float = 0.3, beta: float = 0.1,
                 gamma: float = 0.2) -> Model:
    """Additive Holt-Winters (level + trend + seasonality). Needs >= 2 seasons."""
    def f(y: Series, h: int) -> Series:
        if len(y) < 2 * m:
            return ses(alpha)(y, h)
        # init: level = mean of first season, trend = avg season-over-season slope,
        # seasonals = first-season deviations from that level.
        s1, s2 = y[:m], y[m:2 * m]
        level = sum(s1) / m
        trend = (sum(s2) / m - sum(s1) / m) / m
        season = [s1[i] - level for i in range(m)]
        for t in range(len(y)):
            val = y[t]
            si = t % m
            last_level = level
            level = alpha * (val - season[si]) + (1 - alpha) * (level + trend)
            trend = beta * (level - last_level) + (1 - beta) * trend
            season[si] = gamma * (val - level) + (1 - gamma) * season[si]
        out = []
        for i in range(1, h + 1):
            out.append(level + i * trend + season[(len(y) + i - 1) % m])
        return [max(0.0, v) for v in out]
    return f


def croston(alpha: float = 0.1, sba: bool = False) -> Model:
    """Croston's method for intermittent demand (SES on demand size and interval).
    sba=True applies the Syntetos-Boylan bias correction (1 - alpha/2)."""
    def f(y: Series, h: int) -> Series:
        nz = [(i, v) for i, v in enumerate(y) if v > 0]
        if not nz:
            return [0.0] * h
        z = nz[0][1]                     # smoothed demand size
        x = 1.0                          # smoothed interval
        last = nz[0][0]
        for i, v in nz[1:]:
            gap = i - last
            z = alpha * v + (1 - alpha) * z
            x = alpha * gap + (1 - alpha) * x
            last = i
        rate = z / x if x else z
        if sba:
            rate *= (1 - alpha / 2)
        return [max(0.0, rate)] * h
    return f


CANDIDATES: dict[str, Model] = {
    "naive": naive,
    "seasonal_naive": seasonal_naive(12),
    "moving_avg_3": moving_average(3),
    "ses": ses(0.3),
    "holt_winters": holt_winters(12),
    "croston": croston(0.1),
    "sba": croston(0.1, sba=True),
}


# --------------------------------------------------------------------------- #
# Error metrics
# --------------------------------------------------------------------------- #
def mae(actual: Series, pred: Series) -> float:
    return statistics.mean(abs(a - p) for a, p in zip(actual, pred, strict=False))


def rmse(actual: Series, pred: Series) -> float:
    return math.sqrt(statistics.mean((a - p) ** 2 for a, p in zip(actual, pred, strict=False)))


def mape(actual: Series, pred: Series) -> float:
    pairs = [(a, p) for a, p in zip(actual, pred, strict=False) if a != 0]
    if not pairs:
        return float("nan")
    return 100 * statistics.mean(abs(a - p) / abs(a) for a, p in pairs)


def smape(actual: Series, pred: Series) -> float:
    vals = []
    for a, p in zip(actual, pred, strict=False):
        denom = (abs(a) + abs(p)) / 2
        if denom:
            vals.append(abs(a - p) / denom)
    return 100 * statistics.mean(vals) if vals else float("nan")


def mase(actual: Series, pred: Series, train: Series, m: int = 1) -> float:
    """Scaled by the in-sample MAE of the (seasonal-)naive forecast on `train`."""
    if len(train) <= m:
        m = 1
    denom = statistics.mean(abs(train[i] - train[i - m]) for i in range(m, len(train)))
    if denom == 0:
        return float("nan")
    return mae(actual, pred) / denom


# --------------------------------------------------------------------------- #
# Rolling-origin (walk-forward) cross-validation
# --------------------------------------------------------------------------- #
@dataclass
class CVResult:
    model: str
    folds: int
    mase: float
    mae: float
    rmse: float
    smape: float


def rolling_origin_cv(y: Series, model: Model, horizon: int = 1,
                      min_train: int = 12, step: int = 1, m: int = 12) -> CVResult | None:
    """Expanding-window backtest: train on y[:t], test on the next `horizon`,
    roll t forward by `step`. Averages the errors across folds. Returns None if
    the series is too short for even one fold."""
    origins = list(range(min_train, len(y) - horizon + 1, step))
    if not origins:
        return None
    ma_s, ma_e, rm_e, sm_e, n = 0.0, 0.0, 0.0, 0.0, 0
    for t in origins:
        train, test = y[:t], y[t:t + horizon]
        pred = model(train, horizon)
        sc = mase(test, pred, train, m if t > m else 1)
        if sc != sc:  # NaN (flat train) — skip fold
            continue
        ma_s += sc
        ma_e += mae(test, pred)
        rm_e += rmse(test, pred)
        s = smape(test, pred)
        sm_e += 0.0 if s != s else s
        n += 1
    if n == 0:
        return None
    return CVResult(model="", folds=n, mase=round(ma_s / n, 4), mae=round(ma_e / n, 2),
                    rmse=round(rm_e / n, 2), smape=round(sm_e / n, 2))


def rolling_origin_errors(y: Series, model: Model, horizon: int = 1,
                          min_train: int = 12, step: int = 1) -> Series:
    """Signed out-of-sample forecast errors (actual − predicted) from the same
    expanding-window backtest `rolling_origin_cv` scores, but returned raw rather
    than aggregated. This is the empirical residual sample a prediction interval is
    built from — the honest, model-specific spread of how far the chosen forecaster
    has missed out-of-sample, in the series' own units. Deterministic; returns a
    flat list across folds (and horizon steps when horizon > 1), empty when the
    series is too short for even one fold."""
    errs: Series = []
    for t in range(min_train, len(y) - horizon + 1, step):
        train, test = y[:t], y[t:t + horizon]
        pred = model(train, horizon)
        errs.extend(a - p for a, p in zip(test, pred, strict=False))
    return errs


# --------------------------------------------------------------------------- #
# Demand classification (routes each series to a sensible method family)
# --------------------------------------------------------------------------- #
def demand_class(y: Series) -> dict:
    """ADI (avg inter-demand interval) + CV^2 of non-zero sizes -> Syntetos
    demand pattern: smooth / intermittent / erratic / lumpy."""
    nz = [v for v in y if v > 0]
    if len(nz) < 2:
        return {"adi": float("inf"), "cv2": 0.0, "pattern": "no-demand"}
    idx = [i for i, v in enumerate(y) if v > 0]
    intervals = [idx[i] - idx[i - 1] for i in range(1, len(idx))]
    adi = statistics.mean(intervals) if intervals else 1.0
    mean = statistics.mean(nz)
    cv2 = (statistics.pstdev(nz) / mean) ** 2 if mean else 0.0
    if adi < 1.32 and cv2 < 0.49:
        pattern = "smooth"
    elif adi >= 1.32 and cv2 < 0.49:
        pattern = "intermittent"
    elif adi < 1.32 and cv2 >= 0.49:
        pattern = "erratic"
    else:
        pattern = "lumpy"
    return {"adi": round(adi, 2), "cv2": round(cv2, 3), "pattern": pattern}


# --------------------------------------------------------------------------- #
# Model selection + forecast
# --------------------------------------------------------------------------- #
@dataclass
class Forecast:
    winner: str
    cv_mase: float
    horizon: int
    values: Series
    leaderboard: list[CVResult]
    demand: dict


def select_and_forecast(y: Series, horizon: int = 3, min_train: int = 12,
                        m: int = 12, models: dict[str, Model] | None = None) -> Forecast:
    """Backtest every candidate on `y`, pick the lowest-MASE model, and forecast
    the next `horizon` periods with it fitted on the full history."""
    models = models or CANDIDATES
    board: list[CVResult] = []
    for name, model in models.items():
        res = rolling_origin_cv(y, model, horizon=1, min_train=min_train, m=m)
        if res:
            res.model = name
            board.append(res)
    board.sort(key=lambda r: r.mase)
    winner = board[0].model if board else "seasonal_naive"
    fc = models[winner](y, horizon)
    return Forecast(winner=winner, cv_mase=board[0].mase if board else float("nan"),
                    horizon=horizon, values=[round(v, 2) for v in fc],
                    leaderboard=board, demand=demand_class(y))
