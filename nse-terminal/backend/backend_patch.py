# ---- 1) stock_extractor.py: replace NSE_TICKERS with this (and keep TICKERS = NSE_TICKERS) ----
COMPANY_NAMES = {
 "RELIANCE":"Reliance Industries","TCS":"Tata Consultancy Services","INFY":"Infosys","HDFCBANK":"HDFC Bank",
 "ICICIBANK":"ICICI Bank","WIPRO":"Wipro","HINDUNILVR":"Hindustan Unilever","BAJFINANCE":"Bajaj Finance",
 "SBIN":"State Bank of India","BHARTIARTL":"Bharti Airtel","ITC":"ITC","LT":"Larsen & Toubro",
 "AXISBANK":"Axis Bank","KOTAKBANK":"Kotak Mahindra Bank","SUNPHARMA":"Sun Pharma","MARUTI":"Maruti Suzuki",
 "TITAN":"Titan Company","ASIANPAINT":"Asian Paints","NESTLEIND":"Nestle India","ULTRACEMCO":"UltraTech Cement",
 "HCLTECH":"HCL Technologies","TECHM":"Tech Mahindra","M&M":"Mahindra & Mahindra","NTPC":"NTPC",
 "POWERGRID":"Power Grid Corp","ONGC":"ONGC","COALINDIA":"Coal India","TATASTEEL":"Tata Steel",
 "JSWSTEEL":"JSW Steel","ADANIENT":"Adani Enterprises","ADANIPORTS":"Adani Ports","BAJAJFINSV":"Bajaj Finserv",
 "DRREDDY":"Dr. Reddy's Labs","CIPLA":"Cipla","DIVISLAB":"Divi's Labs","EICHERMOT":"Eicher Motors",
 "HEROMOTOCO":"Hero MotoCorp","GRASIM":"Grasim Industries","BRITANNIA":"Britannia Industries","INDUSINDBK":"IndusInd Bank",
}
NSE_TICKERS = [s + ".NS" for s in COMPANY_NAMES]
# NOTE: TATAMOTORS omitted: Tata Motors demerged, so Yahoo's symbol may be unreliable. Add the new listed symbol(s) once verified.
# Also in seed_historical_prices use time.sleep(0.3) as-is; 40 tickers ~ 15s on first seed.

# ---- 2) app.py: add near the other routes ----
# from flask_cors import CORS; CORS(app)   # optional; Vite proxy already avoids CORS
# from stock_extractor import COMPANY_NAMES
@app.route("/api/universe")
def api_universe():
    df = query(f"""
        SELECT ticker, exchange, price, open_price, high_price, low_price,
               volume, market_cap, change_pct, fetched_at
        FROM stocks
        WHERE ({NSE_TICKER_FILTER}) AND id IN (SELECT MAX(id) FROM stocks GROUP BY ticker)
        ORDER BY ticker""")
    df["name"] = df["ticker"].map(lambda t: COMPANY_NAMES.get(t.replace(".NS", ""), t))
    return jsonify(df.where(df.notna(), None).to_dict(orient="records"))
