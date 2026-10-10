"""
Refresh data/fundamentals.csv (shares outstanding + trailing EPS per stock).

Yahoo's v7 quote endpoint rate-limits (HTTP 429) many cloud hosts, so the
deployed app computes market cap = price x shares and P/E = price / EPS from
this file instead. These change roughly quarterly; re-run from a home
connection and commit the CSV:

    python update_fundamentals.py
"""
import csv
import os
import urllib.parse

from stock_extractor import (
    TICKERS, QUOTE_BATCH, BASE_DIR, _yahoo_session, _get_json, symbol_of, log,
)

OUT = os.path.join(BASE_DIR, "data", "fundamentals.csv")


def main():
    opener, crumb = _yahoo_session()
    rows = []
    for i in range(0, len(TICKERS), QUOTE_BATCH):
        chunk = TICKERS[i:i + QUOTE_BATCH]
        syms = ",".join(urllib.parse.quote(t) for t in chunk)
        url = (f"https://query1.finance.yahoo.com/v7/finance/quote"
               f"?symbols={syms}&crumb={urllib.parse.quote(crumb)}")
        for q in _get_json(url, opener).get("quoteResponse", {}).get("result", []):
            rows.append({
                "symbol": symbol_of(q["symbol"]),
                "shares_outstanding": q.get("sharesOutstanding") or "",
                "eps_ttm": q.get("epsTrailingTwelveMonths") or "",
            })
    rows.sort(key=lambda r: r["symbol"])
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "shares_outstanding", "eps_ttm"])
        w.writeheader()
        w.writerows(rows)
    have = sum(1 for r in rows if r["shares_outstanding"])
    log.info("Wrote %s: %d stocks (%d with shares outstanding)", OUT, len(rows), have)


if __name__ == "__main__":
    main()
