# NSE Stock Widget

A dense, terminal-style dashboard for 42 large-cap NSE stocks: live quotes, 6 months of daily history, market breadth, sector filters, a watchlist, and a 5-session Ridge-regression forecast per stock.

- **Backend:** Python, Flask, SQLite, scikit-learn. Data from Yahoo Finance (delayed).
- **Frontend:** React 18, Vite 5, Tailwind CSS 3 (`nse-terminal/`).

## Run locally

```bash
pip install -r requirements.txt
python stock_extractor.py      # seed ~6 months of daily bars + latest quotes (a few seconds)
python app.py                  # API on http://127.0.0.1:5001
```

In a second terminal:

```bash
cd nse-terminal
npm install
npm run dev                    # http://localhost:5173 (proxies /api to :5001)
```

While NSE is open (Mon–Fri 09:15–15:30 IST), the API pulls fresh quotes every 60 s. Exchange holidays are not modelled.

## API

| Route | Returns |
|---|---|
| `GET /api/universe` | Latest quote per stock with name, sector, market cap, P/E, 52W range, 30-day sparkline, 1M/3M returns |
| `GET /api/history/<ticker>?limit=` | One row per trading day |
| `GET /api/predict/<ticker>` | 5-step forecast, CV MAE, feature weights |
| `GET /api/status` | Market open/closed, last fetch, simulated-data count |
| `POST /api/refresh` | Fetch live quotes now (409 if already running) |
| `GET /api/log` | Last 10 pipeline runs |

Tickers use the `.NS` suffix; `M&M.NS` must be URL-encoded as `M%26M.NS`.

## Keyboard

`/` search · `Esc` clear/close · `↑ ↓` or `j k` move · `s` star · `r` refresh · `w` watchlist

## Caveat

The forecast is a linear model on ~120 daily closes. It is a statistics demo, not investment advice.
