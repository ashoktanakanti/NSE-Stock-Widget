import csv
import os
import re
import sqlite3
import socket
import urllib.error
import urllib.request
import urllib.parse
import http.cookiejar
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd


# Fallback universe (Nifty 50 core) if data/nifty500.csv is missing.
# symbol -> (company name, sector)
CORE_COMPANIES = {
    "RELIANCE":   ("Reliance Industries",        "Energy"),
    "TCS":        ("Tata Consultancy Services",  "IT"),
    "INFY":       ("Infosys",                    "IT"),
    "HDFCBANK":   ("HDFC Bank",                  "Banks"),
    "ICICIBANK":  ("ICICI Bank",                 "Banks"),
    "WIPRO":      ("Wipro",                      "IT"),
    "HINDUNILVR": ("Hindustan Unilever",         "FMCG"),
    "BAJFINANCE": ("Bajaj Finance",              "Financials"),
    "SBIN":       ("State Bank of India",        "Banks"),
    "BHARTIARTL": ("Bharti Airtel",              "Telecom"),
    "ITC":        ("ITC",                        "FMCG"),
    "LT":         ("Larsen & Toubro",            "Infra"),
    "AXISBANK":   ("Axis Bank",                  "Banks"),
    "KOTAKBANK":  ("Kotak Mahindra Bank",        "Banks"),
    "SUNPHARMA":  ("Sun Pharma",                 "Pharma"),
    "MARUTI":     ("Maruti Suzuki",              "Auto"),
    "TITAN":      ("Titan Company",              "Consumer"),
    "ASIANPAINT": ("Asian Paints",               "Consumer"),
    "NESTLEIND":  ("Nestle India",               "FMCG"),
    "ULTRACEMCO": ("UltraTech Cement",           "Materials"),
    "HCLTECH":    ("HCL Technologies",           "IT"),
    "TECHM":      ("Tech Mahindra",              "IT"),
    "M&M":        ("Mahindra & Mahindra",        "Auto"),
    "NTPC":       ("NTPC",                       "Power"),
    "POWERGRID":  ("Power Grid Corp",            "Power"),
    "ONGC":       ("ONGC",                       "Energy"),
    "COALINDIA":  ("Coal India",                 "Energy"),
    "TATASTEEL":  ("Tata Steel",                 "Metals"),
    "JSWSTEEL":   ("JSW Steel",                  "Metals"),
    "ADANIENT":   ("Adani Enterprises",          "Infra"),
    "ADANIPORTS": ("Adani Ports",                "Infra"),
    "BAJAJFINSV": ("Bajaj Finserv",              "Financials"),
    "DRREDDY":    ("Dr. Reddy's Labs",           "Pharma"),
    "CIPLA":      ("Cipla",                      "Pharma"),
    "DIVISLAB":   ("Divi's Labs",                "Pharma"),
    "EICHERMOT":  ("Eicher Motors",              "Auto"),
    "HEROMOTOCO": ("Hero MotoCorp",              "Auto"),
    "GRASIM":     ("Grasim Industries",          "Materials"),
    "BRITANNIA":  ("Britannia Industries",       "FMCG"),
    "INDUSINDBK": ("IndusInd Bank",              "Banks"),
    # Post-demerger Tata Motors listings (verified on Yahoo: TATAMOTORS.NS now 404s)
    "TMPV":       ("Tata Motors Passenger Veh.", "Auto"),
    "TMCV":       ("Tata Motors Commercial Veh.", "Auto"),
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSE_CSV = os.path.join(BASE_DIR, "data", "nifty500.csv")

# Short labels for niftyindices.com "Industry" values (keeps sector chips compact)
SECTOR_SHORT = {
    "Financial Services": "Financials",
    "Capital Goods": "Capital Goods",
    "Healthcare": "Healthcare",
    "Automobile and Auto Components": "Auto",
    "Fast Moving Consumer Goods": "FMCG",
    "Chemicals": "Chemicals",
    "Information Technology": "IT",
    "Consumer Services": "Consumer Svcs",
    "Metals & Mining": "Metals",
    "Power": "Power",
    "Oil Gas & Consumable Fuels": "Energy",
    "Consumer Durables": "Durables",
    "Services": "Services",
    "Realty": "Realty",
    "Construction": "Construction",
    "Construction Materials": "Materials",
    "Telecommunication": "Telecom",
    "Textiles": "Textiles",
    "Media Entertainment & Publication": "Media",
    "Diversified": "Diversified",
}


def _clean_name(name: str) -> str:
    return re.sub(r"\s+(Ltd\.?|Limited)$", "", name.strip())


def load_universe(path: str = UNIVERSE_CSV) -> dict[str, tuple[str, str]]:
    """Nifty 500 constituents from the niftyindices.com CSV
    (columns: Company Name, Industry, Symbol, Series, ISIN Code)."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return dict(CORE_COMPANIES)
    out = {}
    for r in rows:
        sym = (r.get("Symbol") or "").strip()
        # The index file carries placeholder rows like DUMMYHEG
        if not sym or sym.startswith("DUMMY"):
            continue
        industry = (r.get("Industry") or "").strip()
        out[sym] = (_clean_name(r.get("Company Name") or sym),
                    SECTOR_SHORT.get(industry, industry or "Other"))
    return out or dict(CORE_COMPANIES)


COMPANIES = load_universe()


def load_fundamentals(path: str = os.path.join(BASE_DIR, "data", "fundamentals.csv")):
    """symbol -> (shares_outstanding, eps_ttm) from update_fundamentals.py."""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return {r["symbol"]: (num(r["shares_outstanding"]), num(r["eps_ttm"]))
                    for r in csv.DictReader(fh)}
    except OSError:
        return {}


FUNDAMENTALS = load_fundamentals()
COMPANY_NAMES = {s: v[0] for s, v in COMPANIES.items()}
SECTORS = {s: v[1] for s, v in COMPANIES.items()}

NSE_TICKERS = [s + ".NS" for s in COMPANIES]

TICKERS = NSE_TICKERS
NSE_SUFFIX = ".NS"

DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "stock_market.db"))
FETCH_INTERVAL_SECONDS = 60
HISTORY_RANGE = "6mo"
MIN_HISTORY_ROWS = 20
FETCH_WORKERS = 8
QUOTE_BATCH = 100   # symbols per v7 quote request
LOG_FORMAT = "%(asctime)s  %(levelname)-8s %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger("stock_pipeline")

YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


# Python's resolver tries IPv6 first; on many networks Yahoo's IPv6 route
# stalls ~25s per request. Force IPv4 for Yahoo hosts only.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_for_yahoo(host, *args, **kwargs):
    if isinstance(host, str) and host.endswith("yahoo.com"):
        args = list(args)
        if len(args) >= 2:
            args[1] = socket.AF_INET
        else:
            kwargs["family"] = socket.AF_INET
    return _orig_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _ipv4_for_yahoo


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


def ts_to_iso(epoch_sec: int) -> str:
    return datetime.fromtimestamp(epoch_sec, tz=timezone.utc).isoformat(
        sep=" ", timespec="seconds"
    )


def is_nse_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(NSE_SUFFIX)


def symbol_of(ticker: str) -> str:
    return ticker[: -len(NSE_SUFFIX)] if is_nse_ticker(ticker) else ticker


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()
    # WAL: API reads keep working while the seeder bulk-inserts
    cursor.execute("PRAGMA journal_mode=WAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker        TEXT    NOT NULL,
            exchange      TEXT    NOT NULL DEFAULT 'NSE',
            price         REAL    NOT NULL,
            open_price    REAL,
            high_price    REAL,
            low_price     REAL,
            volume        INTEGER,
            market_cap    REAL,
            pe_ratio      REAL,
            change_pct    REAL,
            fetched_at    TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at      TEXT NOT NULL,
            tickers_ok  INTEGER,
            tickers_err INTEGER,
            status      TEXT
        )
    """)

    cols = {row[1] for row in cursor.execute("PRAGMA table_info(stocks)")}
    migrations = {
        "exchange":   "TEXT NOT NULL DEFAULT 'NSE'",
        "prev_close": "REAL",
        "week52_high": "REAL",
        "week52_low":  "REAL",
        # 'live' = Yahoo, 'simulated' = random-walk fallback
        "source":     "TEXT NOT NULL DEFAULT 'live'",
        # 'bar' = daily history bar, 'quote' = intraday live quote
        "kind":       "TEXT NOT NULL DEFAULT 'bar'",
    }
    for col, ddl in migrations.items():
        if col not in cols:
            cursor.execute(f"ALTER TABLE stocks ADD COLUMN {col} {ddl}")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stocks_ticker_time ON stocks (ticker, fetched_at)"
    )

    conn.commit()
    purge_non_nse_stocks(conn)
    log.info("Database initialised: %s", db_path)
    return conn


def purge_non_nse_stocks(conn: sqlite3.Connection) -> int:
    """Remove BSE (.BO), US, and any non-NSE ticker rows."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stocks WHERE ticker NOT LIKE '%.NS'")
    deleted = cursor.rowcount
    conn.commit()
    if deleted:
        log.info("Purged %d non-NSE record(s) (BSE/US/other).", deleted)
    return deleted


def _get_json(url: str, opener=None, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    open_ = opener.open if opener else urllib.request.urlopen
    with open_(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


NOT_LISTED = {}  # sentinel: Yahoo answered 404 for the symbol


def _yahoo_chart(ticker: str, interval: str, range_period: str) -> dict | None:
    # Symbols like M&M must be percent-encoded (M%26M.NS)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
        f"?interval={interval}&range={range_period}"
    )
    try:
        return _get_json(url)["chart"]["result"][0]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Symbol unknown to Yahoo (new listing / renamed): skip, don't simulate
            log.warning("Yahoo has no symbol %s", ticker)
            return NOT_LISTED
        log.warning("Yahoo chart failed for %s: %s", ticker, exc)
        return None
    except Exception as exc:
        log.warning("Yahoo chart failed for %s: %s", ticker, exc)
        return None


_crumb_session: dict = {}
# Last v7 batch outcome, surfaced via /api/status (helps debug hosted deploys)
quote_diag: dict = {"ok": None, "error": None, "at": None}


def _yahoo_session(refresh: bool = False):
    """Cookie + crumb pair required by the v7 quote endpoint."""
    if _crumb_session and not refresh:
        return _crumb_session["opener"], _crumb_session["crumb"]
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        opener.open(urllib.request.Request("https://fc.yahoo.com", headers=YAHOO_HEADERS), timeout=10)
    except Exception:
        pass  # 404 is expected; it still sets the cookie
    req = urllib.request.Request("https://query1.finance.yahoo.com/v1/test/getcrumb", headers=YAHOO_HEADERS)
    with opener.open(req, timeout=10) as resp:
        crumb = resp.read().decode().strip()
    if not crumb or "<" in crumb:
        raise RuntimeError(f"no crumb (got {crumb[:40]!r})")
    _crumb_session.update(opener=opener, crumb=crumb)
    return opener, crumb


def fetch_quotes_batch(tickers: list[str]) -> dict[str, dict]:
    """v7 quotes in chunks of QUOTE_BATCH: price, OHLC, prev close, market cap, P/E, 52w."""
    out: dict[str, dict] = {}
    chunks = [tickers[i:i + QUOTE_BATCH] for i in range(0, len(tickers), QUOTE_BATCH)]
    for chunk in chunks:
        out.update(_fetch_quotes_chunk(chunk))
    return out


def _fetch_quotes_chunk(tickers: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for attempt in range(2):
        try:
            opener, crumb = _yahoo_session(refresh=attempt > 0)
            syms = ",".join(urllib.parse.quote(t) for t in tickers)
            url = (f"https://query1.finance.yahoo.com/v7/finance/quote"
                   f"?symbols={syms}&crumb={urllib.parse.quote(crumb)}")
            data = _get_json(url, opener)
            break
        except Exception as exc:
            log.warning("Yahoo batch quote failed (attempt %d): %s", attempt + 1, exc)
            quote_diag.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:200], at=utc_now())
            data = None
    if not data:
        return out
    quote_diag.update(ok=True, error=None, at=utc_now())

    now = utc_now()
    for q in data.get("quoteResponse", {}).get("result", []):
        mt = q.get("regularMarketTime")
        t = q.get("symbol")
        price = q.get("regularMarketPrice")
        if t not in tickers or price is None:
            continue
        out[t] = {
            "ticker":      t,
            "exchange":    "NSE",
            "price":       price,
            "open_price":  q.get("regularMarketOpen"),
            "high_price":  q.get("regularMarketDayHigh"),
            "low_price":   q.get("regularMarketDayLow"),
            "volume":      q.get("regularMarketVolume"),
            "prev_close":  q.get("regularMarketPreviousClose"),
            "market_cap":  q.get("marketCap"),
            "pe_ratio":    q.get("trailingPE"),
            "week52_high": q.get("fiftyTwoWeekHigh"),
            "week52_low":  q.get("fiftyTwoWeekLow"),
            "source":      "live",
            "kind":        "quote",
            # Stamp with the exchange's last trade time, not wall-clock time,
            # so a weekend/after-hours fetch doesn't create a phantom daily bar.
            "fetched_at":  ts_to_iso(mt) if isinstance(mt, (int, float)) else now,
        }
    return out


def fetch_quote(ticker: str) -> dict | None:
    """Per-ticker fallback via the chart endpoint (no market cap / P/E)."""
    if not is_nse_ticker(ticker):
        return None

    result = _yahoo_chart(ticker, "1d", "5d")
    if not result:  # also NOT_LISTED
        return None

    meta = result["meta"]
    quote = (result.get("indicators") or {}).get("quote", [{}])[0]
    closes = [c for c in (quote.get("close") or []) if c is not None]
    opens = [o for o in (quote.get("open") or []) if o is not None]
    # chartPreviousClose is the close *before the range*, not yesterday's close
    prev_close = closes[-2] if len(closes) >= 2 else meta.get("chartPreviousClose")
    return {
        "ticker":      ticker,
        "exchange":    "NSE",
        "price":       meta.get("regularMarketPrice"),
        "open_price":  opens[-1] if opens else None,
        "high_price":  meta.get("regularMarketDayHigh"),
        "low_price":   meta.get("regularMarketDayLow"),
        "volume":      meta.get("regularMarketVolume"),
        "prev_close":  prev_close,
        "market_cap":  None,
        "pe_ratio":    None,
        "week52_high": meta.get("fiftyTwoWeekHigh"),
        "week52_low":  meta.get("fiftyTwoWeekLow"),
        "source":      "live",
        "kind":        "quote",
        "fetched_at":  ts_to_iso(meta["regularMarketTime"])
                       if meta.get("regularMarketTime") else utc_now(),
    }


def fetch_price_history(ticker: str,
                        range_period: str = HISTORY_RANGE) -> list[dict]:
    """
    Fetch daily OHLC history for ML training (multiple distinct prices per ticker).
    """
    if not is_nse_ticker(ticker):
        return []

    result = _yahoo_chart(ticker, "1d", range_period)
    if result is NOT_LISTED:
        return []
    if not result:
        return _simulated_history(ticker)

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators") or {}).get("quote", [{}])[0]
    opens  = quote.get("open") or []
    highs  = quote.get("high") or []
    lows   = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    rows = []
    for i, ts in enumerate(timestamps):
        close = closes[i] if i < len(closes) else None
        if close is None:
            continue
        open_ = opens[i] if i < len(opens) and opens[i] is not None else close
        high  = highs[i] if i < len(highs) and highs[i] is not None else close
        low   = lows[i] if i < len(lows) and lows[i] is not None else close
        vol   = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
        rows.append({
            "ticker":     ticker,
            "exchange":   "NSE",
            "price":      close,
            "open_price": open_,
            "high_price": high,
            "low_price":  low,
            "volume":     vol,
            "market_cap": None,
            "source":     "live",
            "kind":       "bar",
            "fetched_at": ts_to_iso(ts),
        })

    if rows:
        log.info("  history %s: %d daily bars [live]", ticker, len(rows))
        return rows
    return _simulated_history(ticker)


def _simulated_history(ticker: str, days: int = 60) -> list[dict]:
    """Random-walk daily prices when the API is unavailable."""
    rng = np.random.default_rng(seed=sum(map(ord, ticker)))
    price = 500.0
    rows = []
    now = datetime.now(timezone.utc)
    for d in range(days, 0, -1):
        open_ = round(price * (1 + rng.uniform(-0.01, 0.01)), 2)
        price = round(open_ * (1 + rng.uniform(-0.02, 0.02)), 2)
        rows.append({
            "ticker":     ticker,
            "exchange":   "NSE",
            "price":      price,
            "open_price": open_,
            "high_price": round(max(open_, price) * 1.005, 2),
            "low_price":  round(min(open_, price) * 0.995, 2),
            "volume":     int(rng.integers(1_000_000, 50_000_000)),
            "market_cap": None,
            "source":     "simulated",
            "kind":       "bar",
            "fetched_at": (now - timedelta(days=d)).isoformat(sep=" ", timespec="seconds"),
        })
    log.info("  history %s: %d daily bars [simulated]", ticker, len(rows))
    return rows


def fetch_all_quotes(tickers: list[str]) -> list[dict]:
    nse = [t for t in tickers if is_nse_ticker(t)]
    quotes = fetch_quotes_batch(nse)

    missing = [t for t in nse if t not in quotes]
    if missing:
        log.info("  batch missed %d ticker(s); falling back to chart endpoint", len(missing))
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            for t, q in zip(missing, pool.map(fetch_quote, missing)):
                if q and q.get("price") is not None:
                    quotes[t] = q

    failed = [t for t in nse if t not in quotes]
    if failed:
        # Never invent a live price; the UI keeps showing the last stored row.
        log.warning("  Skipped (live): %s", failed)
    log.info("  live quotes: %d/%d", len(quotes), len(nse))
    return [quotes[t] for t in nse if t in quotes]


def clean_quotes(raw: list[dict]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    df["exchange"] = "NSE"
    for col, default in [("source", "live"), ("kind", "bar")]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default)

    num_cols = ["price", "open_price", "high_price", "low_price", "volume",
                "market_cap", "pe_ratio", "prev_close", "week52_high", "week52_low"]
    for col in num_cols:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["price"])
    df = df.sort_values(["ticker", "fetched_at"]).reset_index(drop=True)

    cleaned = []
    for ticker, grp in df.groupby("ticker", sort=False):
        grp = grp.copy()
        prices = grp["price"].values
        if len(prices) >= 4:
            q1, q3 = np.percentile(prices, 25), np.percentile(prices, 75)
            iqr = q3 - q1
            if iqr > 0:
                lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
                grp["price"] = grp["price"].clip(lower=lower, upper=upper)

        # 1D change is vs. the previous session's close, not today's open.
        # History bars: previous bar's close. Live quotes: Yahoo's prev close.
        grp["prev_close"] = grp["prev_close"].fillna(grp["price"].shift(1))

        # Fill gaps from *this* ticker only (a cross-ticker median would put
        # a ₹200 stock's low on a ₹12,000 stock).
        for col in ["open_price", "high_price", "low_price"]:
            grp[col] = grp[col].fillna(grp["price"])
        cleaned.append(grp)
    df = pd.concat(cleaned, ignore_index=True) if cleaned else df

    df["change_pct"] = np.where(
        df["prev_close"].notna() & (df["prev_close"] != 0),
        (df["price"] - df["prev_close"]) / df["prev_close"] * 100,
        np.nan,
    ).round(4)

    for col in ["price", "open_price", "high_price", "low_price", "prev_close"]:
        df[col] = df[col].round(4)
    df["volume"] = df["volume"].fillna(0).astype(int)

    log.info("Cleaned DataFrame: %d rows", len(df))
    return df


INSERT_COLS = ["ticker", "exchange", "price", "open_price", "high_price", "low_price",
               "volume", "market_cap", "pe_ratio", "change_pct", "prev_close",
               "week52_high", "week52_low", "source", "kind", "fetched_at"]


def insert_quotes(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    df = df.copy()
    for col in INSERT_COLS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[INSERT_COLS].astype(object).where(df[INSERT_COLS].notna(), None)

    records = df.to_dict(orient="records")
    placeholders = ", ".join(f":{c}" for c in INSERT_COLS)
    conn.cursor().executemany(
        f"INSERT INTO stocks ({', '.join(INSERT_COLS)}) VALUES ({placeholders})",
        records,
    )
    conn.commit()
    log.info("Inserted %d record(s).", len(records))
    return len(records)


def distinct_price_count(conn: sqlite3.Connection, ticker: str) -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT price) FROM stocks WHERE ticker = ?", (ticker,)
    ).fetchone()
    return row[0] if row else 0


def seed_historical_prices(conn: sqlite3.Connection,
                           tickers: list[str] | None = None,
                           force: bool = False) -> int:
    """
    Load ~6 months of daily OHLC per NSE ticker for ML forecasts and charts.
    Skips tickers that already have enough varied history unless force=True.
    """
    tickers = [t for t in (tickers or TICKERS) if is_nse_ticker(t)]
    if not force:
        tickers = [t for t in tickers
                   if distinct_price_count(conn, t) < MIN_HISTORY_ROWS]
    if not tickers:
        log.info("  history already loaded for all tickers")
        return 0

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        histories = list(pool.map(fetch_price_history, tickers))

    for ticker in tickers:
        conn.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
    conn.commit()

    all_rows = [row for rows in histories for row in rows]
    if not all_rows:
        return 0
    return insert_quotes(conn, clean_quotes(all_rows))


def log_pipeline_run(conn: sqlite3.Connection, ok: int, err: int, status: str) -> None:
    conn.execute("""
        INSERT INTO pipeline_log (run_at, tickers_ok, tickers_err, status)
        VALUES (?, ?, ?, ?)
    """, (utc_now(), ok, err, status))
    conn.commit()


def print_latest_snapshot(conn: sqlite3.Connection) -> None:
    df = pd.read_sql_query("""
        SELECT ticker, price, change_pct, source, fetched_at FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY ticker ORDER BY fetched_at DESC, id DESC) AS rn
            FROM stocks)
        WHERE rn = 1 ORDER BY ticker
    """, conn)
    if df.empty:
        return

    print("\n" + "-" * 66)
    print(f"  {'TICKER':<16} {'PRICE':>12}  {'CHANGE':>8}  {'SRC':<5} FETCHED AT")
    print("-" * 66)
    for _, row in df.iterrows():
        chg = row["change_pct"]
        chg_s = "n/a" if pd.isna(chg) else f"{chg:+.2f}%"
        print(f"  {row.ticker:<16} Rs{row.price:>10.2f}  {chg_s:>8}  {row.source[:4]:<5} {row.fetched_at}")
    print("-" * 66 + "\n")


def run_once(conn: sqlite3.Connection, tickers: list[str]) -> None:
    log.info("--- Pipeline run (NSE only) ---")
    t0 = time.time()
    raw = fetch_all_quotes(tickers)
    store_quotes(conn, tickers, raw)
    log.info("--- Done in %.2fs ---", round(time.time() - t0, 2))
    print_latest_snapshot(conn)


def store_quotes(conn: sqlite3.Connection, tickers: list[str], raw: list[dict]) -> int:
    """Insert fetched quotes and log the run (split from fetching so callers
    can do the slow network part without holding a DB lock)."""
    ok = len(raw)
    err = len([t for t in tickers if is_nse_ticker(t)]) - ok
    inserted = insert_quotes(conn, clean_quotes(raw))
    log_pipeline_run(conn, ok, err, "OK" if err == 0 else f"PARTIAL ({err})")
    return inserted


if __name__ == "__main__":
    conn = init_db(DB_PATH)
    t0 = time.time()
    seed_historical_prices(conn, force=True)
    log.info("Seeded history in %.1fs", time.time() - t0)
    run_once(conn, TICKERS)
    conn.close()
