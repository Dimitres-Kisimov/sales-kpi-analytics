"""Tests for the forecasting library, error metrics, CV and model selection."""
from __future__ import annotations

from saleskpi import forecast as F


def test_every_model_returns_horizon_length():
    y = [float(v) for v in range(1, 25)]  # 24 points
    h = 3
    models = {
        "naive": F.naive,
        "seasonal_naive": F.seasonal_naive(12),
        "moving_avg": F.moving_average(3),
        "ses": F.ses(0.3),
        "holt_winters": F.holt_winters(12),
        "croston": F.croston(0.1),
        "sba": F.croston(0.1, sba=True),
    }
    for name, m in models.items():
        out = m(y, h)
        assert len(out) == h, f"{name} returned wrong length"
        assert all(isinstance(v, float) for v in out)


def test_seasonal_naive_repeats_the_season():
    m = 4
    y = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]  # two seasons of length 4
    f = F.seasonal_naive(m)
    # one season ahead == the last observed season
    assert f(y, 4) == [5.0, 6.0, 7.0, 8.0]
    # two seasons ahead repeats it
    assert f(y, 8) == [5.0, 6.0, 7.0, 8.0, 5.0, 6.0, 7.0, 8.0]


def test_mase_is_one_when_pred_equals_naive_baseline():
    # linear series, step 1 -> in-sample naive MAE == 1
    train = [1.0, 2.0, 3.0, 4.0, 5.0]
    actual = [6.0]
    pred = F.naive(train, 1)  # -> [5.0]; error = |6-5| = 1
    assert F.mase(actual, pred, train, m=1) == 1.0


def test_error_metrics_zero_on_perfect_forecast():
    actual = [10.0, 20.0, 30.0]
    pred = [10.0, 20.0, 30.0]
    assert F.mae(actual, pred) == 0.0
    assert F.rmse(actual, pred) == 0.0
    assert F.smape(actual, pred) == 0.0


def test_rolling_origin_cv_returns_folds():
    y = [float(v) for v in [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17,
                            16, 18, 17, 19, 18, 20, 19, 21, 20, 22, 21, 23]]
    res = F.rolling_origin_cv(y, F.naive, horizon=1, min_train=12, m=12)
    assert res is not None
    assert res.folds > 0
    assert res.mase >= 0


def test_rolling_origin_cv_none_when_too_short():
    assert F.rolling_origin_cv([1.0, 2.0, 3.0], F.naive, min_train=12) is None


def test_rolling_origin_errors_are_signed_and_counted():
    # perfectly linear series, step 1: naive predicts y[t-1], actual is y[t-1]+1,
    # so every out-of-sample error is exactly +1, and there are len-min_train folds.
    y = [float(v) for v in range(1, 25)]           # 24 points
    errs = F.rolling_origin_errors(y, F.naive, horizon=1, min_train=12)
    assert len(errs) == 12                          # origins t = 12..23
    assert all(abs(e - 1.0) < 1e-9 for e in errs)   # signed (actual − pred), not |·|
    # too short for even one fold -> empty
    assert F.rolling_origin_errors([1.0, 2.0, 3.0], F.naive, min_train=12) == []


def test_select_and_forecast_winner_and_sorted_leaderboard():
    y = [float(v) for v in [100, 120, 90, 140, 110, 130, 95, 150, 115, 135,
                            100, 160, 105, 125, 92, 145, 112, 132, 97, 152,
                            118, 138, 101, 162]]
    sel = F.select_and_forecast(y, horizon=3, min_train=12, m=12)
    assert sel.winner in F.CANDIDATES
    assert len(sel.values) == 3
    assert len(sel.leaderboard) > 0
    mases = [r.mase for r in sel.leaderboard]
    assert mases == sorted(mases), "leaderboard must be sorted by MASE ascending"
    # winner is the top of the leaderboard
    assert sel.leaderboard[0].model == sel.winner


def test_demand_class_smooth():
    steady = [10.0, 11.0, 10.0, 12.0, 10.0, 11.0, 10.0, 12.0, 11.0, 10.0, 11.0, 10.0]
    assert F.demand_class(steady)["pattern"] == "smooth"


def test_demand_class_sparse_is_intermittent_or_lumpy():
    sparse = [0.0, 0.0, 5.0, 0.0, 0.0, 8.0, 0.0, 0.0, 3.0, 0.0, 0.0, 40.0]
    assert F.demand_class(sparse)["pattern"] in {"intermittent", "lumpy"}
