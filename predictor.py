
import sqlite3
import warnings
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")

DB_PATH = "stock_market.db"
MIN_ROWS = 8
MIN_PRICE_VARIANCE = 0.01
FORECAST_STEPS = 5


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values("fetched_at").reset_index(drop=True)

    df["lag_1"]          = df["price"].shift(1)
    df["lag_2"]          = df["price"].shift(2)
    df["lag_3"]          = df["price"].shift(3)
    df["rolling_mean_5"] = df["price"].shift(1).rolling(5, min_periods=2).mean()
    df["rolling_std_5"]  = df["price"].shift(1).rolling(5, min_periods=2).std().fillna(0)
    # Both must describe *yesterday*: same-day values encode the target price
    # (price = prev_close * (1 + change_pct/100)) and leak it into training.
    df["change_pct"]     = df["change_pct"].shift(1).fillna(0)
    df["return_1d"]      = df["price"].pct_change().shift(1).fillna(0) * 100

    vol_min, vol_max = df["volume"].min(), df["volume"].max()
    df["volume_norm"] = (
        (df["volume"] - vol_min) / (vol_max - vol_min)
        if vol_max > vol_min else 0.0
    )

    df.dropna(subset=["lag_1", "lag_2", "lag_3"], inplace=True)
    return df


FEATURE_COLS = [
    "lag_1", "lag_2", "lag_3",
    "rolling_mean_5", "rolling_std_5",
    "change_pct", "return_1d", "volume_norm",
]


def train_model(df_feat: pd.DataFrame):
    if len(df_feat) < MIN_ROWS:
        return None, {"error": f"Need at least {MIN_ROWS} history rows, got {len(df_feat)}. Click Refresh data."}

    prices = df_feat["price"].values
    if np.std(prices) < MIN_PRICE_VARIANCE:
        return None, {
            "error": (
                "Not enough price variation to forecast. "
                "Wait for more daily history or click Refresh data."
            )
        }

    X = df_feat[FEATURE_COLS].values
    y = df_feat["price"].values

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  Ridge(alpha=0.5)),
    ])

    n_splits = max(2, min(3, len(df_feat) // 4))
    try:
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = cross_val_score(
            model, X, y, cv=tscv, scoring="neg_mean_absolute_error"
        )
        cv_mae = float(-cv_scores.mean())
    except Exception:
        cv_mae = float("nan")

    model.fit(X, y)
    y_pred = model.predict(X)

    return model, {
        "cv_mae":      round(cv_mae, 4) if cv_mae == cv_mae else None,
        "train_mae":   round(float(mean_absolute_error(y, y_pred)), 4),
        "train_rmse":  round(float(np.sqrt(mean_squared_error(y, y_pred))), 4),
        "n_samples":   len(y),
    }


def forecast(model, df_feat: pd.DataFrame, steps: int = FORECAST_STEPS) -> list[float]:
    if model is None or df_feat.empty:
        return []

    last = df_feat.iloc[-1]
    lag1 = float(last["price"])
    lag2 = float(last["lag_1"])
    lag3 = float(last["lag_2"])
    rolling_vals = list(df_feat["price"].tail(5).values)
    # For step 1 the "previous day" is the last observed day itself
    return_1d = (lag1 / lag2 - 1) * 100 if lag2 else 0.0
    change_pct = return_1d
    volume_norm = float(last["volume_norm"])

    forecasts = []
    for _ in range(steps):
        r_mean = float(np.mean(rolling_vals[-5:]))
        r_std  = float(np.std(rolling_vals[-5:])) if len(rolling_vals) > 1 else 0.0

        x = np.array([[lag1, lag2, lag3, r_mean, r_std, change_pct, return_1d, volume_norm]])
        pred = float(model.predict(x)[0])
        forecasts.append(round(pred, 2))

        lag3, lag2, lag1 = lag2, lag1, pred
        rolling_vals.append(pred)
        return_1d = ((pred - lag2) / lag2 * 100) if lag2 else 0.0
        change_pct = return_1d

    return forecasts


def predict_ticker(ticker: str, db_path: str = DB_PATH,
                   steps: int = FORECAST_STEPS) -> dict:
    from stock_extractor import is_nse_ticker

    ticker = ticker.upper()
    if not is_nse_ticker(ticker):
        return {"ticker": ticker, "error": "Only NSE tickers (.NS suffix) are supported."}

    conn = sqlite3.connect(db_path, timeout=30)
    df = pd.read_sql_query(
        "SELECT price, open_price, high_price, low_price, volume, "
        "       change_pct, fetched_at "
        "FROM stocks WHERE ticker = ? ORDER BY fetched_at",
        conn, params=(ticker,),
    )
    conn.close()

    if df.empty:
        return {"ticker": ticker, "error": "No data yet. Click Refresh data first."}

    
    df["day"] = df["fetched_at"].astype(str).str[:10]
    df = df.groupby("day", as_index=False).last().drop(columns=["day"])

    df_feat = build_features(df)
    model, metrics = train_model(df_feat)

    if model is None:
        return {"ticker": ticker, "error": metrics.get("error"), "metrics": metrics}

    future_prices = forecast(model, df_feat, steps)
    coef = model.named_steps["ridge"].coef_
    importance = dict(sorted(
        {col: round(float(abs(v)), 4) for col, v in zip(FEATURE_COLS, coef)}.items(),
        key=lambda x: x[1], reverse=True,
    ))

    return {
        "ticker":        ticker,
        "exchange":      "NSE",
        "current_price": round(float(df_feat["price"].iloc[-1]), 2),
        "forecasts":     future_prices,
        "metrics":       metrics,
        "feature_importance": importance,
        "history":       df_feat["price"].round(2).tolist()[-30:],
    }


def predict_all(tickers: list[str], db_path: str = DB_PATH) -> list[dict]:
    return [predict_ticker(t, db_path) for t in tickers]


if __name__ == "__main__":
    from stock_extractor import TICKERS, DB_PATH as _DB

    for ticker in TICKERS:
        result = predict_ticker(ticker, _DB)
        if result.get("error"):
            print(f"{ticker}: {result['error']}")
            continue
        fc = result["forecasts"]
        print(f"{ticker}: Rs{result['current_price']:.2f} -> "
              f"{', '.join(f'Rs{p:.2f}' for p in fc)}")
