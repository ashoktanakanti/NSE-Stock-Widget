import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from stock_extractor import (
    init_db, seed_historical_prices, fetch_all_quotes, store_quotes,
    TICKERS, DB_PATH, quote_diag, FUNDAMENTALS, COMPANY_NAMES, SECTORS, FETCH_INTERVAL_SECONDS,
    is_nse_ticker, purge_non_nse_stocks, distinct_price_count, symbol_of,
)
from predictor import predict_ticker

NSE_TICKER_FILTER = "ticker LIKE '%.NS'"
PORT = int(os.environ.get("PORT", 5001))
DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nse-terminal", "dist")
IST = timezone(timedelta(hours=5, minutes=30))
SPARK_POINTS = 30

app = Flask(__name__, static_folder=None)
_db_lock = threading.Lock()
_refresh_lock = threading.Lock()
_refresh_state = {"running": False, "started_at": None, "finished_at": None,
                  "ok": None, "err": None, "trigger": None}
_boot_state = {"seeding": False, "started": False}
_universe_cache = {"key": None, "data": None}


def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)


def query(sql, params=()):
    with _db_lock:
        conn = get_conn()
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
    return df


def records(df):
    """DataFrame -> JSON-safe records (NaN -> null)."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def market_status(now=None):
    """NSE cash session: Mon-Fri 09:15-15:30 IST (exchange holidays not modelled)."""
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = now.weekday() < 5 and open_t <= now <= close_t
    return {"open": is_open, "ist": now.isoformat(timespec="seconds")}


# "Latest" by time, not MAX(id): seeded bars and live quotes share the table
LATEST_SQL = f"""
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY ticker ORDER BY fetched_at DESC, id DESC) AS rn
        FROM stocks WHERE ({NSE_TICKER_FILTER}))
    WHERE rn = 1
"""


def daily_bars(df):
    """Collapse to one row per ticker per calendar day (last write wins), so
    repeated intraday refreshes don't distort charts or ranges."""
    df = df.copy()
    df["day"] = df["fetched_at"].astype(str).str[:10]
    return (df.sort_values(["ticker", "fetched_at", "id"])
              .groupby(["ticker", "day"], as_index=False).last())


@app.route("/api/universe")
def api_universe():
    # ~500 tickers x ~125 bars: recompute only when new rows land
    key = query("SELECT MAX(id) AS m, COUNT(*) AS n FROM stocks").iloc[0].tolist()
    if _universe_cache["key"] == key:
        return jsonify(_universe_cache["data"])
    data = _build_universe()
    _universe_cache.update(key=key, data=data)
    return jsonify(data)


def _build_universe():
    latest = query(LATEST_SQL + " ORDER BY ticker")
    if latest.empty:
        return []

    hist = daily_bars(query(
        f"SELECT id, ticker, price, market_cap, pe_ratio, source, fetched_at "
        f"FROM stocks WHERE {NSE_TICKER_FILTER}"
    ))
    extra = {}
    for t, g in hist.groupby("ticker"):
        closes = g["price"].tolist()
        last63 = closes[-63:]
        # Bars carry no fundamentals; take the newest row that has them
        mc = g["market_cap"].dropna()
        pe = g["pe_ratio"].dropna()
        extra[t] = {
            "spark": [round(p, 2) for p in closes[-SPARK_POINTS:]],
            "range3m_low": min(last63),
            "range3m_high": max(last63),
            "ret_1m": (closes[-1] / closes[-22] - 1) * 100 if len(closes) > 22 else None,
            "ret_3m": (closes[-1] / closes[-64] - 1) * 100 if len(closes) > 64 else None,
            "market_cap_fallback": float(mc.iloc[-1]) if len(mc) else None,
            "pe_fallback": float(pe.iloc[-1]) if len(pe) else None,
            "simulated_bars": int((g["source"] == "simulated").sum()),
        }

    out = []
    for row in records(latest.drop(columns=["rn", "id"])):
        t = row["ticker"]
        e = extra.get(t, {})
        sym = symbol_of(t)
        row["symbol"] = sym
        row["name"] = COMPANY_NAMES.get(sym, sym)
        row["sector"] = SECTORS.get(sym, "Other")
        row["market_cap"] = row["market_cap"] or e.get("market_cap_fallback")
        row["pe_ratio"] = row["pe_ratio"] or e.get("pe_fallback")
        # Live v7 fundamentals are often rate-limited on cloud hosts: derive
        # from bundled shares outstanding / trailing EPS instead
        shares, eps = FUNDAMENTALS.get(sym, (None, None))
        if not row["market_cap"] and shares and row["price"]:
            row["market_cap"] = row["price"] * shares
        if not row["pe_ratio"] and eps and eps > 0 and row["price"]:
            row["pe_ratio"] = row["price"] / eps
        if e.get("simulated_bars"):
            row["source"] = "simulated"
        for k in ("spark", "range3m_low", "range3m_high", "ret_1m", "ret_3m"):
            row[k] = e.get(k)
        out.append(row)
    return out


@app.route("/api/history/<path:ticker>")
def api_history(ticker):
    ticker = ticker.upper()
    if not is_nse_ticker(ticker):
        return jsonify({"error": "Only NSE tickers (.NS suffix) are supported."}), 400
    limit = request.args.get("limit", 90, type=int)
    df = query(
        "SELECT id, ticker, price, open_price, high_price, low_price, volume, "
        "change_pct, source, fetched_at FROM stocks WHERE ticker = ?",
        (ticker,),
    )
    if df.empty:
        return jsonify([])
    df = daily_bars(df).tail(limit)
    df["date"] = df["day"]
    return jsonify(records(df.drop(columns=["id", "ticker", "day"])))


@app.route("/api/predict/<path:ticker>")
def api_predict(ticker):
    ticker = ticker.upper()
    if not is_nse_ticker(ticker):
        return jsonify({"error": "Only NSE tickers (.NS suffix) are supported."}), 400
    result = predict_ticker(ticker, DB_PATH)
    return jsonify(result)


def _run_refresh(trigger):
    if not _refresh_lock.acquire(blocking=False):
        return False
    _refresh_state.update(running=True, trigger=trigger,
                          started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    try:
        raw = fetch_all_quotes(TICKERS)          # network: no DB lock held
        with _db_lock:
            conn = get_conn()
            store_quotes(conn, TICKERS, raw)
            conn.close()
        _refresh_state.update(ok=len(raw), err=len(TICKERS) - len(raw))
    except Exception as exc:
        app.logger.exception("refresh failed: %s", exc)
        _refresh_state.update(ok=0, err=len(TICKERS))
    finally:
        _refresh_state.update(running=False,
                              finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        _refresh_lock.release()
    return True


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Run one pipeline cycle in a background thread."""
    if _refresh_state["running"]:
        return jsonify({"status": "already running", **_refresh_state}), 409
    threading.Thread(target=_run_refresh, args=("manual",), daemon=True).start()
    return jsonify({"status": "refresh started",
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})


@app.route("/api/status")
def api_status():
    latest = query(LATEST_SQL)
    sim = query(f"SELECT COUNT(DISTINCT ticker) AS n FROM stocks "
                f"WHERE {NSE_TICKER_FILTER} AND source = 'simulated'")
    quotes = latest[latest["kind"] == "quote"] if not latest.empty else latest
    return jsonify({
        "market": market_status(),
        "refresh": _refresh_state,
        "auto_refresh_seconds": FETCH_INTERVAL_SECONDS,
        "tickers_tracked": len(TICKERS),
        "seeding": _boot_state["seeding"],
        "quote_batch": quote_diag,
        "tickers_with_data": int(len(latest)),
        "tickers_simulated": int(sim["n"].iloc[0]),
        "last_quote_at": quotes["fetched_at"].max() if len(quotes) else None,
    })


@app.route("/api/log")
def api_log():
    df = query("SELECT * FROM pipeline_log ORDER BY id DESC LIMIT 10")
    return jsonify(records(df))


def _auto_refresh_loop():
    """Pull live quotes every FETCH_INTERVAL_SECONDS while NSE is open."""
    while True:
        time.sleep(FETCH_INTERVAL_SECONDS)
        if market_status()["open"]:
            _run_refresh("auto")


# Built React app (nse-terminal/dist). Unknown non-API paths fall back to
# index.html so client-side state survives a reload.
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path):
    if path.startswith("api/"):
        return jsonify({"error": "not found"}), 404
    if not os.path.isdir(DIST_DIR):
        return ("Frontend not built. Run: npm --prefix nse-terminal install && "
                "npm --prefix nse-terminal run build", 503)
    full = os.path.join(DIST_DIR, path)
    if path and os.path.isfile(full):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")


def _seed_db():
    """Load ~6 months of daily NSE price history so charts and forecasts work."""
    _boot_state["seeding"] = True
    try:
        conn = get_conn()
        needs_history = [t for t in TICKERS if distinct_price_count(conn, t) < 15]
        if needs_history:
            print(f"  Loading price history for {len(needs_history)} ticker(s)…")
            # No _db_lock here: the fetch is ~30s of network I/O and SQLite's
            # own locking covers the short insert; /api/status stays responsive.
            seed_historical_prices(conn, needs_history, force=False)
            print("  History loaded.")
        conn.close()
    finally:
        _boot_state["seeding"] = False


def bootstrap():
    """Init DB, then seed + start the quote loop in the background so the
    HTTP server is up immediately (hosts health-check the port on boot)."""
    if _boot_state["started"]:
        return
    _boot_state["started"] = True
    conn = init_db(DB_PATH)
    purge_non_nse_stocks(conn)
    conn.close()

    def _boot():
        _seed_db()
        _run_refresh("startup")
        _auto_refresh_loop()

    threading.Thread(target=_boot, daemon=True).start()
    print(f"  Tracking {len(TICKERS)} NSE tickers")


# gunicorn imports this module; `python app.py` runs it directly.
if os.environ.get("NSE_AUTOBOOT", "1") == "1":
    bootstrap()


if __name__ == "__main__":
    print(f"  NSE Terminal  ->  http://localhost:{PORT}/")
    print(f"  API           ->  http://localhost:{PORT}/api/universe")
    # Reloader would spawn a second process and double the background threads
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=PORT, debug=False, threaded=True)
