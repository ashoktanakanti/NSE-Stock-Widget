"""
Next-day close forecaster, evaluated against the naive baseline
"tomorrow's close = today's close".

The model is a Ridge regression that predicts tomorrow's *return* from
scale-free features of the last few days, then turns it back into a price.
An earlier version regressed the price level on lagged prices; it lost to
the naive baseline on ~94% of stocks because it could not extrapolate
outside the price range it was trained on.

Run `python predictor.py` to score the model against the baseline across
the whole universe.
"""
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from stock_extractor import DB_PATH, TICKERS, is_nse_ticker

MIN_ROWS = 8
MIN_PRICE_VARIANCE = 0.01
FORECAST_STEPS = 5
MAX_CV_SPLITS = 5
# Chosen by walk-forward CV over the Nifty 500 (alpha 1 / 10 / 100 / 1000)
RIDGE_ALPHA = 100.0

FEATURE_COLS = ["ret_1", "ret_2", "dev_mean_5", "volatility_5", "rel_volume"]
VOLUME_WINDOW = 20


def relative_features(lag_1, lag_2, lag_3, mean_5, std_5, rel_volume):
    """Scale-free inputs, so one model shape works for a ₹13 and a ₹13,000 stock."""
    return {
        "ret_1": lag_1 / lag_2 - 1,        # yesterday's return
        "ret_2": lag_2 / lag_3 - 1,        # the day before's return
        "dev_mean_5": lag_1 / mean_5 - 1,  # distance from the 5-day mean
        "volatility_5": std_5 / lag_1,     # 5-day price volatility
        "rel_volume": rel_volume,          # yesterday's volume / its 20-day average
    }


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per day. Every feature uses only data from *before* that day;
    the target is that day's return (`target_return`).

    Same-day values must not leak in: `change_pct` and `volume` describe the
    very close being predicted (price = prev_close * (1 + change_pct/100)).
    """
    df = df.copy().sort_values("fetched_at").reset_index(drop=True)
    price = df["price"]

    df["lag_1"] = price.shift(1)
    df["lag_2"] = price.shift(2)
    df["lag_3"] = price.shift(3)
    df["rolling_mean_5"] = price.shift(1).rolling(5, min_periods=2).mean()
    df["rolling_std_5"] = price.shift(1).rolling(5, min_periods=2).std().fillna(0)

    # Trailing average only: min-max scaling over the whole series would leak
    # future volumes into past rows (caught by test_features_use_only_past_data)
    vol = df["volume"].astype(float)
    df["rel_volume"] = (vol / vol.rolling(VOLUME_WINDOW, min_periods=5).mean()).shift(1)

    feats = relative_features(df["lag_1"], df["lag_2"], df["lag_3"],
                              df["rolling_mean_5"], df["rolling_std_5"], df["rel_volume"])
    for name, col in feats.items():
        df[name] = col
    df["target_return"] = price / df["lag_1"] - 1

    return df.dropna(subset=FEATURE_COLS + ["target_return"]).reset_index(drop=True)


def make_model() -> Pipeline:
    return Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=RIDGE_ALPHA))])


def cross_validate(df_feat: pd.DataFrame) -> dict:
    """Walk-forward CV. Each fold trains on the past and scores the next
    block, for both the model and the naive baseline (prediction = lag_1).
    Errors are in rupees on the same days, so they compare directly."""
    X = df_feat[FEATURE_COLS].values
    y = df_feat["target_return"].values
    price = df_feat["price"].values
    naive = df_feat["lag_1"].values  # "tomorrow = today"

    n_splits = max(2, min(MAX_CV_SPLITS, len(df_feat) // 10))
    model_err, naive_err = [], []
    for train_idx, test_idx in TimeSeriesSplit(n_splits=n_splits).split(X):
        model = make_model().fit(X[train_idx], y[train_idx])
        predicted = naive[test_idx] * (1 + model.predict(X[test_idx]))
        model_err.append(mean_absolute_error(price[test_idx], predicted))
        naive_err.append(mean_absolute_error(price[test_idx], naive[test_idx]))

    cv_mae, naive_mae = float(np.mean(model_err)), float(np.mean(naive_err))
    return {
        "cv_mae": round(cv_mae, 4),
        "naive_mae": round(naive_mae, 4),
        # > 0: the model beats "tomorrow = today"; < 0: the baseline wins
        "skill": round(1 - cv_mae / naive_mae, 4) if naive_mae else None,
        "beats_naive": bool(cv_mae < naive_mae),
    }


def train_model(df_feat: pd.DataFrame):
    if len(df_feat) < MIN_ROWS:
        return None, {"error": f"Need at least {MIN_ROWS} days of history, got {len(df_feat)}."}
    if np.std(df_feat["price"].values) < MIN_PRICE_VARIANCE:
        return None, {"error": "Not enough price variation to forecast."}

    metrics = cross_validate(df_feat)

    X = df_feat[FEATURE_COLS].values
    model = make_model().fit(X, df_feat["target_return"].values)
    price = df_feat["price"].values
    fitted = df_feat["lag_1"].values * (1 + model.predict(X))
    metrics.update(
        train_mae=round(float(mean_absolute_error(price, fitted)), 4),
        train_rmse=round(float(np.sqrt(mean_squared_error(price, fitted))), 4),
        n_samples=len(price),
    )
    return model, metrics


def forecast(model, df_feat: pd.DataFrame, steps: int = FORECAST_STEPS) -> list[float]:
    """Recursive multi-step forecast: each predicted close becomes the next lag."""
    if model is None or df_feat.empty:
        return []

    prices = [float(p) for p in df_feat["price"].tail(5)]
    # Volume isn't forecast; hold the last observed day's relative level
    vol = df_feat["volume"].astype(float)
    recent = vol.tail(VOLUME_WINDOW).mean()
    rel_volume = float(vol.iloc[-1] / recent) if recent > 0 else 1.0

    out = []
    for _ in range(steps):
        window = prices[-5:]
        feats = relative_features(prices[-1], prices[-2], prices[-3],
                                  float(np.mean(window)),
                                  float(np.std(window, ddof=1)),  # matches pandas .std()
                                  rel_volume)
        x = np.array([[feats[c] for c in FEATURE_COLS]])
        nxt = prices[-1] * (1 + float(model.predict(x)[0]))
        out.append(round(nxt, 2))
        prices.append(nxt)
    return out


def load_daily(ticker: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Daily rows for one ticker (repeated intraday quotes collapse to the last)."""
    conn = sqlite3.connect(db_path, timeout=30)
    df = pd.read_sql_query(
        "SELECT price, volume, change_pct, source, fetched_at "
        "FROM stocks WHERE ticker = ? ORDER BY fetched_at, id",
        conn, params=(ticker,),
    )
    conn.close()
    if df.empty:
        return df
    df["day"] = df["fetched_at"].astype(str).str[:10]
    return df.groupby("day", as_index=False).last().drop(columns=["day"])


def predict_ticker(ticker: str, db_path: str = DB_PATH,
                   steps: int = FORECAST_STEPS) -> dict:
    ticker = ticker.upper()
    if not is_nse_ticker(ticker):
        return {"ticker": ticker, "error": "Only NSE tickers (.NS suffix) are supported."}

    df = load_daily(ticker, db_path)
    if df.empty:
        return {"ticker": ticker, "error": "No data yet for this stock."}
    if (df["source"] == "simulated").any():
        # Never train on, or show a forecast from, made-up prices
        return {"ticker": ticker,
                "error": "Price history is simulated (Yahoo was unreachable), so no forecast is shown."}

    df_feat = build_features(df)
    model, metrics = train_model(df_feat)
    if model is None:
        return {"ticker": ticker, "error": metrics.get("error"), "metrics": metrics}

    coef = model.named_steps["ridge"].coef_
    importance = dict(sorted(
        ((col, round(float(abs(v)), 6)) for col, v in zip(FEATURE_COLS, coef)),
        key=lambda kv: kv[1], reverse=True,
    ))
    return {
        "ticker": ticker,
        "exchange": "NSE",
        "current_price": round(float(df_feat["price"].iloc[-1]), 2),
        "forecasts": forecast(model, df_feat, steps),
        "metrics": metrics,
        "feature_importance": importance,
        "history": df_feat["price"].round(2).tolist()[-30:],
    }


def evaluate(tickers: list[str] = TICKERS, db_path: str = DB_PATH) -> dict:
    """Model vs naive baseline across the universe. MAE is scaled by each
    stock's average price so cheap and expensive stocks compare."""
    rows = []
    for t in tickers:
        df = load_daily(t, db_path)
        if df.empty or (df["source"] == "simulated").any():
            continue
        df_feat = build_features(df)
        if len(df_feat) < MIN_ROWS * 4:
            continue
        m = cross_validate(df_feat)
        px = float(df_feat["price"].mean())
        rows.append({"model_pct": m["cv_mae"] / px * 100,
                     "naive_pct": m["naive_mae"] / px * 100,
                     "skill": m["skill"], "beats": m["beats_naive"]})
    res = pd.DataFrame(rows)
    return {
        "stocks": len(res),
        "model_wins_pct": round(float(res["beats"].mean() * 100), 1),
        "median_model_mae_pct": round(float(res["model_pct"].median()), 3),
        "median_naive_mae_pct": round(float(res["naive_pct"].median()), 3),
        "median_skill_pct": round(float(res["skill"].median() * 100), 2),
    }


if __name__ == "__main__":
    r = evaluate()
    print(f"Stocks evaluated:      {r['stocks']}")
    print(f"Model beats naive on:  {r['model_wins_pct']}% of stocks")
    print(f"Median MAE, model:     {r['median_model_mae_pct']}% of price")
    print(f"Median MAE, naive:     {r['median_naive_mae_pct']}% of price")
    print(f"Median skill:          {r['median_skill_pct']}%  (>0 = model better)")
