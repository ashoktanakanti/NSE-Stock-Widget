import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
from flask import Flask, jsonify, render_template_string, request, send_from_directory

from stock_extractor import (
    init_db, seed_historical_prices, fetch_all_quotes, store_quotes,
    TICKERS, DB_PATH, COMPANY_NAMES, SECTORS, FETCH_INTERVAL_SECONDS,
    is_nse_ticker, purge_non_nse_stocks, distinct_price_count, symbol_of,
)
from predictor import predict_ticker, FORECAST_STEPS

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
    return sqlite3.connect(DB_PATH)


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


@app.route("/api/quotes")
def api_quotes():
    df = query(LATEST_SQL + " ORDER BY ticker")
    cols = ["ticker", "exchange", "price", "open_price", "high_price", "low_price",
            "volume", "change_pct", "fetched_at"]
    return jsonify(records(df[cols]))


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


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NSE Stock Widget</title>
<style>
  :root {
    --bg: #0d0f14; --surface: #141720; --panel: #1a1e2a;
    --border: rgba(255,255,255,0.07); --border2: rgba(255,255,255,0.12);
    --text: #e4e8f0; --muted: #6b7291;
    --accent: #5b8dee; --green: #3dd68c; --red: #f26c6c; --amber: #f5a623;
    --font: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: var(--font); font-size: 12px;
    min-height: 100vh;
    display: flex; align-items: flex-start; justify-content: center;
    padding: 32px 16px;
  }

  #widget {
    width: 460px;
    background: var(--bg);
    border: 1px solid var(--border2);
    border-radius: 14px;
    overflow: hidden;
  }

  /* ── Titlebar ── */
  #titlebar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .dots { display: flex; gap: 6px; }
  .dot  { width: 11px; height: 11px; border-radius: 50%; }
  .dot-r { background: #ff5f57; } .dot-y { background: #febc2e; } .dot-g { background: #28c840; }
  .tb-title { font-size: 11px; color: var(--muted); letter-spacing: .08em; }
  .pulse-wrap { display: flex; align-items: center; gap: 5px; font-size: 10px; color: var(--muted); }
  .pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--green);
           animation: blink 2s ease-in-out infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* ── Ticker list ── */
  #ticker-list { max-height: 220px; overflow-y: auto; }
  #ticker-list::-webkit-scrollbar { width: 3px; }
  #ticker-list::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
  .ticker-row {
    display: grid; grid-template-columns: 90px 1fr 72px 68px;
    align-items: center; gap: 4px;
    padding: 8px 14px;
    border-bottom: 1px solid var(--border);
    cursor: pointer; transition: background .1s;
  }
  .ticker-row:hover { background: rgba(91,141,238,.06); }
  .ticker-row.selected { background: rgba(91,141,238,.1); }
  .tr-sym   { font-size: 11px; font-weight: 700; color: var(--accent); }
  .tr-price { font-size: 12px; text-align: right; }
  .tr-chg   { font-size: 11px; text-align: right; }
  .tr-vol   { font-size: 10px; color: var(--muted); text-align: right; }
  .up   { color: var(--green); }
  .down { color: var(--red); }
  .neu  { color: var(--muted); }

  /* ── Detail section ── */
  #detail-section { border-top: 1px solid var(--border); background: var(--surface); }
  #detail-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    padding: 10px 14px 8px; border-bottom: 1px solid var(--border);
  }
  .dh-sym   { font-size: 15px; font-weight: 700; }
  .dh-exch  { font-size: 9px; color: var(--green); background: rgba(61,214,140,.12);
              padding: 1px 5px; border-radius: 3px; margin-left: 6px; }
  .dh-price { font-size: 18px; font-weight: 700; text-align: right; }
  .dh-chg   { font-size: 11px; text-align: right; }

  #ohlc-grid { display: grid; grid-template-columns: repeat(4,1fr);
               gap: 1px; background: var(--border); }
  .og-cell  { background: var(--surface); padding: 6px 10px; }
  .og-label { font-size: 9px; color: var(--muted); text-transform: uppercase;
              letter-spacing: .07em; margin-bottom: 2px; }
  .og-val   { font-size: 11px; font-weight: 600; }

  #spark-section { padding: 8px 14px 6px; border-top: 1px solid var(--border); }
  .sec-label { font-size: 9px; color: var(--muted); text-transform: uppercase;
               letter-spacing: .07em; margin-bottom: 5px; }
  canvas { width: 100%; display: block; }

  /* ── Forecast section ── */
  #forecast-section { border-top: 1px solid var(--border); }
  #fc-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 14px; border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  .fc-title  { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
  .fc-ticker { font-size: 10px; color: var(--accent); }
  #fc-rows   { padding: 6px 10px; display: flex; flex-direction: column; gap: 4px; }
  .fc-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 8px; background: rgba(255,255,255,.03); border-radius: 5px;
  }
  .fc-step  { font-size: 10px; color: var(--muted); }
  .fc-price { font-size: 12px; font-weight: 600; }
  .fc-delta { font-size: 10px; }
  #fc-metrics {
    display: flex; gap: 14px;
    padding: 6px 14px 10px; border-top: 1px solid var(--border);
    font-size: 10px; color: var(--muted);
  }
  #fc-metrics b { color: var(--text); }

  /* ── Footer ── */
  #footer {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 14px; border-top: 1px solid var(--border);
    background: var(--panel);
  }
  #refresh-btn {
    background: rgba(91,141,238,.12); border: 1px solid rgba(91,141,238,.25);
    color: var(--accent); padding: 4px 10px; border-radius: 5px;
    cursor: pointer; font-family: var(--font); font-size: 10px;
    transition: background .15s;
  }
  #refresh-btn:hover   { background: rgba(91,141,238,.22); }
  #refresh-btn:active  { transform: scale(.97); }
  #refresh-btn:disabled { opacity: .5; cursor: default; }

  .loading { padding: 20px 14px; text-align: center; color: var(--muted); }
  .err-msg { padding: 14px; text-align: center; color: var(--amber); font-size: 11px; }

  @media (max-width: 500px) {
    #widget { width: 100%; border-radius: 0; }
  }
</style>
</head>
<body>

<div id="widget">
  <div id="titlebar">
    <div class="dots">
      <div class="dot dot-r"></div>
      <div class="dot dot-y"></div>
      <div class="dot dot-g"></div>
    </div>
    <span class="tb-title">NSE MARKET</span>
    <div class="pulse-wrap">
      <div class="pulse"></div>
      <span id="last-updated">connecting…</span>
    </div>
  </div>

  <div id="ticker-list">
    <div class="loading">Loading tickers…</div>
  </div>

  <div id="detail-section" style="display:none">
    <div id="detail-header">
      <div>
        <span class="dh-sym" id="d-sym">—</span>
        <span class="dh-exch">NSE</span>
      </div>
      <div>
        <div class="dh-price" id="d-price">—</div>
        <div class="dh-chg" id="d-chg"></div>
      </div>
    </div>
    <div id="ohlc-grid">
      <div class="og-cell"><div class="og-label">Open</div><div class="og-val" id="d-open">—</div></div>
      <div class="og-cell"><div class="og-label">High</div><div class="og-val up" id="d-high">—</div></div>
      <div class="og-cell"><div class="og-label">Low</div><div class="og-val down" id="d-low">—</div></div>
      <div class="og-cell"><div class="og-label">Volume</div><div class="og-val" id="d-vol">—</div></div>
    </div>
    <div id="spark-section">
      <div class="sec-label">30-day history</div>
      <canvas id="sparkline"></canvas>
    </div>
  </div>

  <div id="forecast-section">
    <div id="fc-header">
      <span class="fc-title">ML Forecast</span>
      <span class="fc-ticker" id="fc-ticker-label"></span>
    </div>
    <div id="fc-placeholder" class="loading">Select a ticker to view forecast</div>
    <div id="fc-body" style="display:none">
      <div id="fc-rows"></div>
      <div id="fc-metrics"></div>
    </div>
  </div>

  <div id="footer">
    <span id="ts-label" style="font-size:10px;color:var(--muted)">—</span>
    <button id="refresh-btn" onclick="triggerRefresh()">⟳ Refresh</button>
  </div>
</div>

<script>
const fmt  = n => '₹' + parseFloat(n).toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2});
const fmtV = n => { const v = parseInt(n); if(v>=1e7) return (v/1e7).toFixed(2)+'Cr'; if(v>=1e5) return (v/1e5).toFixed(1)+'L'; return v.toLocaleString('en-IN'); };
const pct  = n => (n >= 0 ? '+' : '') + parseFloat(n).toFixed(2) + '%';
const cls  = n => n > 0 ? 'up' : n < 0 ? 'down' : 'neu';
const sym  = t => (t || '').replace('.NS', '');

let quotes = [];
let selectedTicker = null;

async function loadQuotes() {
  try {
    const r = await fetch('/api/quotes');
    quotes = await r.json();
    renderTickers(quotes);
    document.getElementById('last-updated').textContent =
      new Date().toLocaleTimeString('en-IN', {hour:'2-digit', minute:'2-digit'});
    if (selectedTicker) loadForecast(selectedTicker);
  } catch(e) {
    document.getElementById('ticker-list').innerHTML =
      '<div class="err-msg">⚠ Failed to load data</div>';
  }
}

function renderTickers(data) {
  if (!data.length) {
    document.getElementById('ticker-list').innerHTML =
      '<div class="loading">No NSE data. Click Refresh.</div>';
    return;
  }
  const ts = data[0]?.fetched_at || '';
  document.getElementById('ts-label').textContent = ts ? ts.slice(0, 16) : '';
  let html = '';
  for (const q of data) {
    const cc = cls(q.change_pct);
    const sel = q.ticker === selectedTicker ? ' selected' : '';
    html += `<div class="ticker-row${sel}" onclick="selectTicker('${q.ticker}')">
      <span class="tr-sym">${sym(q.ticker)}</span>
      <span class="tr-price">${fmt(q.price)}</span>
      <span class="tr-chg ${cc}">${pct(q.change_pct)}</span>
      <span class="tr-vol">${fmtV(q.volume)}</span>
    </div>`;
  }
  document.getElementById('ticker-list').innerHTML = html;
}

async function selectTicker(ticker) {
  selectedTicker = ticker;
  renderTickers(quotes);
  const q = quotes.find(x => x.ticker === ticker);
  if (!q) return;

  document.getElementById('detail-section').style.display = 'block';
  document.getElementById('d-sym').textContent = sym(ticker);
  document.getElementById('d-price').textContent = fmt(q.price);
  const cc = cls(q.change_pct);
  document.getElementById('d-chg').innerHTML = `<span class="${cc}">${pct(q.change_pct)}</span>`;
  document.getElementById('d-open').textContent = fmt(q.open_price);
  document.getElementById('d-high').textContent = fmt(q.high_price);
  document.getElementById('d-low').textContent = fmt(q.low_price);
  document.getElementById('d-vol').textContent = fmtV(q.volume);

  try {
    const hr = await fetch(`/api/history/${ticker}?limit=30`);
    const hist = await hr.json();
    if (Array.isArray(hist)) drawSparkline(hist.map(h => h.price));
  } catch(_) {}

  loadForecast(ticker);
}

function drawSparkline(prices) {
  const canvas = document.getElementById('sparkline');
  const W = canvas.offsetWidth || 430, H = 60;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);
  if (!prices || prices.length < 2) return;

  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const pad = 4;
  const x = i => pad + (i / (prices.length - 1)) * (W - 2 * pad);
  const y = v => H - pad - ((v - min) / range) * (H - 2 * pad);

  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, 'rgba(91,141,238,0.22)');
  g.addColorStop(1, 'rgba(91,141,238,0)');
  ctx.beginPath();
  ctx.moveTo(x(0), y(prices[0]));
  for (let i = 1; i < prices.length; i++) ctx.lineTo(x(i), y(prices[i]));
  ctx.lineTo(x(prices.length - 1), H);
  ctx.lineTo(x(0), H);
  ctx.closePath();
  ctx.fillStyle = g;
  ctx.fill();

  ctx.beginPath();
  ctx.moveTo(x(0), y(prices[0]));
  for (let i = 1; i < prices.length; i++) ctx.lineTo(x(i), y(prices[i]));
  ctx.strokeStyle = '#5b8dee';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const last = prices[prices.length - 1];
  ctx.beginPath();
  ctx.arc(x(prices.length - 1), y(last), 3, 0, 2 * Math.PI);
  ctx.fillStyle = '#5b8dee';
  ctx.fill();
}

async function loadForecast(ticker) {
  document.getElementById('fc-ticker-label').textContent = sym(ticker);
  document.getElementById('fc-placeholder').textContent = 'Computing forecast…';
  document.getElementById('fc-placeholder').style.display = 'block';
  document.getElementById('fc-placeholder').style.color = 'var(--muted)';
  document.getElementById('fc-body').style.display = 'none';

  try {
    const r = await fetch(`/api/predict/${encodeURIComponent(ticker)}`);
    const d = await r.json();

    if (d.error) {
      document.getElementById('fc-placeholder').textContent = '⚠ ' + d.error;
      document.getElementById('fc-placeholder').style.color = 'var(--amber)';
      return;
    }

    if (!d.forecasts || !d.forecasts.length) {
      document.getElementById('fc-placeholder').textContent =
        'No forecast available. Click Refresh.';
      return;
    }

    document.getElementById('fc-placeholder').style.display = 'none';
    document.getElementById('fc-body').style.display = 'block';

    const base = d.current_price;
    let html = '';
    d.forecasts.forEach((p, i) => {
      const delta = p - base;
      const cc = cls(delta);
      html += `<div class="fc-row">
        <span class="fc-step">Day +${i + 1}</span>
        <span class="fc-price">${fmt(p)}</span>
        <span class="fc-delta ${cc}">${delta >= 0 ? '+' : ''}${fmt(delta)}</span>
      </div>`;
    });
    document.getElementById('fc-rows').innerHTML = html;

    const m = d.metrics || {};
    const dec = v => v != null ? parseFloat(v).toFixed(4) : '—';
    document.getElementById('fc-metrics').innerHTML =
      `<span>CV-MAE <b>${dec(m.cv_mae)}</b></span>
       <span>RMSE <b>${dec(m.train_rmse)}</b></span>
       <span>n <b>${m.n_samples ?? '—'}</b></span>`;
  } catch(e) {
    document.getElementById('fc-placeholder').textContent =
      '⚠ Forecast unavailable';
    document.getElementById('fc-placeholder').style.color = 'var(--amber)';
  }
}

async function triggerRefresh() {
  const btn = document.getElementById('refresh-btn');
  btn.textContent = '⏳ Wait…';
  btn.disabled = true;
  await fetch('/api/refresh', { method: 'POST' });
  await new Promise(res => setTimeout(res, 8000));
  await loadQuotes();
  if (selectedTicker) selectTicker(selectedTicker);
  btn.textContent = '⟳ Refresh';
  btn.disabled = false;
}

loadQuotes();
setInterval(loadQuotes, 90000);
</script>
</body>
</html>
"""


@app.route("/legacy")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


# Built React app (nse-terminal/dist). Unknown non-API paths fall back to
# index.html so client-side state survives a reload.
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path):
    if path.startswith("api/"):
        return jsonify({"error": "not found"}), 404
    if not os.path.isdir(DIST_DIR):
        return render_template_string(DASHBOARD_HTML)
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
