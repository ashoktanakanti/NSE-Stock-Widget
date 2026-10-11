import sqlite3
from datetime import datetime, timezone

import pandas as pd
import pytest

import app as A


def ist(y, mo, d, h, mi):
    """IST wall-clock time as an aware UTC datetime."""
    return datetime(y, mo, d, h, mi, tzinfo=A.IST).astimezone(timezone.utc)


@pytest.mark.parametrize("when, is_open", [
    (ist(2026, 10, 9, 10, 0), True),     # Friday mid-session
    (ist(2026, 10, 9, 9, 14), False),    # one minute before the open
    (ist(2026, 10, 9, 9, 15), True),     # at the open
    (ist(2026, 10, 9, 15, 30), True),    # at the close
    (ist(2026, 10, 9, 15, 31), False),   # after the close
    (ist(2026, 10, 10, 11, 0), False),   # Saturday
])
def test_market_status(when, is_open):
    assert A.market_status(when)["open"] is is_open


def test_daily_bars_keeps_last_write_per_day():
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "ticker": ["X.NS"] * 3,
        "price": [100.0, 101.0, 102.0],
        "fetched_at": ["2026-01-01 03:45:00", "2026-01-01 09:00:00", "2026-01-02 03:45:00"],
    })
    out = A.daily_bars(df)
    assert out["price"].tolist() == [101.0, 102.0]


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(A, "DB_PATH", db)
    A._universe_cache.update(key=None, data=None)
    conn = sqlite3.connect(db)
    for i, p in enumerate([2700.0, 2750.0, 2796.2]):
        conn.execute(
            "INSERT INTO stocks (ticker, exchange, price, volume, change_pct, prev_close, source, kind, fetched_at)"
            " VALUES ('M&M.NS', 'NSE', ?, 1000, 0, NULL, 'live', 'bar', ?)",
            (p, f"2026-10-0{7 + i} 03:45:00+00:00"),
        )
    conn.commit()
    conn.close()
    return A.app.test_client()


def test_universe_returns_latest_row_with_metadata(client):
    [row] = client.get("/api/universe").get_json()
    assert row["symbol"] == "M&M" and row["price"] == 2796.2
    assert row["name"] == "Mahindra & Mahindra" and row["spark"][-1] == 2796.2


def test_history_accepts_url_encoded_ampersand(client):
    rows = client.get("/api/history/M%26M.NS").get_json()
    assert [r["date"] for r in rows] == ["2026-10-07", "2026-10-08", "2026-10-09"]


def test_non_nse_ticker_is_rejected(client):
    assert client.get("/api/predict/AAPL").status_code == 400


def test_unknown_api_path_is_json_404(client):
    assert client.get("/api/nope").status_code == 404
