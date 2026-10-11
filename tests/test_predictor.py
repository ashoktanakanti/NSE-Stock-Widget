import numpy as np
import pytest

import predictor as P
from conftest import make_daily


def test_features_use_only_past_data(random_walk):
    """Changing day t's close, volume or change_pct must not change day t's
    features (the leak that once made CV error look near-perfect)."""
    base = P.build_features(random_walk)
    t = 100
    tampered = random_walk.copy()
    tampered.loc[t, ["price", "volume", "change_pct"]] = [99999.0, 10**12, 55.0]
    after = P.build_features(tampered)

    row = base.index[base["fetched_at"] == random_walk.loc[t, "fetched_at"]][0]
    for col in P.FEATURE_COLS:
        assert after.loc[row, col] == pytest.approx(base.loc[row, col]), col
    # ...while the target for that day does change
    assert after.loc[row, "target_return"] != pytest.approx(base.loc[row, "target_return"])


def test_target_is_next_day_return(random_walk):
    f = P.build_features(random_walk)
    np.testing.assert_allclose(f["target_return"], f["price"] / f["lag_1"] - 1)


def test_naive_baseline_is_tomorrow_equals_today(random_walk):
    f = P.build_features(random_walk)
    m = P.cross_validate(f)
    # Naive MAE over the CV test folds can never exceed the overall mean |Δprice|
    # by much, and must be positive on a random walk
    assert m["naive_mae"] > 0
    assert m["skill"] == pytest.approx(1 - m["cv_mae"] / m["naive_mae"], abs=1e-3)


def test_model_beats_naive_on_a_predictable_series():
    # Steady 1%/day growth: the model can learn it, "tomorrow = today" can't
    f = P.build_features(make_daily(100 * 1.01 ** np.arange(120)))
    m = P.cross_validate(f)
    assert m["beats_naive"] and m["skill"] > 0.5


def test_forecast_continues_a_trend():
    df = make_daily(100 * 1.01 ** np.arange(120))
    model, _ = P.train_model(P.build_features(df))
    fc = P.forecast(model, P.build_features(df), steps=5)
    assert len(fc) == 5
    assert all(b > a for a, b in zip(fc, fc[1:]))


def test_train_model_rejects_short_history():
    model, metrics = P.train_model(P.build_features(make_daily([100, 101, 102, 103, 104])))
    assert model is None and "Need at least" in metrics["error"]


def _insert(db, ticker, df):
    import sqlite3
    conn = sqlite3.connect(db)
    for r in df.itertuples():
        conn.execute(
            "INSERT INTO stocks (ticker, exchange, price, volume, change_pct, source, fetched_at)"
            " VALUES (?, 'NSE', ?, ?, ?, ?, ?)",
            (ticker, r.price, r.volume, r.change_pct, r.source, r.fetched_at),
        )
    conn.commit()
    conn.close()


def test_no_forecast_from_simulated_prices(db, random_walk):
    _insert(db, "FAKE.NS", random_walk.assign(source="simulated"))
    result = P.predict_ticker("FAKE.NS", db)
    assert "simulated" in result["error"] and "forecasts" not in result


def test_predict_ticker_reports_baseline(db, random_walk):
    _insert(db, "REAL.NS", random_walk)
    result = P.predict_ticker("REAL.NS", db)
    assert len(result["forecasts"]) == P.FORECAST_STEPS
    assert {"cv_mae", "naive_mae", "skill", "beats_naive"} <= result["metrics"].keys()


def test_rejects_non_nse_ticker(db):
    assert "NSE" in P.predict_ticker("AAPL", db)["error"]
