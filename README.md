# NSE Stock Widget

A dense, terminal-style dashboard for the **Nifty 500** (499 tradable NSE stocks): live quotes, 6 months of daily history, market breadth, sector filters, a watchlist, and a 5-session Ridge-regression forecast per stock.

- **Backend:** Python, Flask, SQLite, scikit-learn. Data from Yahoo Finance (delayed).
- **Frontend:** React 18, Vite 5, Tailwind CSS 3 (`nse-terminal/`).
- **Stock list:** `data/nifty500.csv`, the official constituent file from niftyindices.com. Replace it with a newer download to update the universe.

## Host it for free (Render)

1. Sign in at [render.com](https://render.com) with GitHub.
2. **New → Blueprint**, pick this repo. Render reads `render.yaml` and builds the `Dockerfile`.
3. Open the `*.onrender.com` URL it gives you.

On first start the app seeds ~6 months of history for all stocks (about 20 s); the page shows a loading state and fills in by itself. Free instances sleep after ~15 minutes idle, so the first visit after a sleep takes ~30–60 s and re-seeds.

## Run locally

Requires Python 3.10+ and Node 18+.

```bash
pip install -r requirements.txt
python app.py                  # seeds the DB on first run, API on http://127.0.0.1:5001
```

In a second terminal (dev server with hot reload):

```bash
cd nse-terminal
npm install
npm run dev                    # http://localhost:5173 (proxies /api to :5001)
```

Or build once and let Flask serve everything from one port:

```bash
npm --prefix nse-terminal install
npm --prefix nse-terminal run build
python app.py                  # http://localhost:5001
```

While NSE is open (Mon–Fri 09:15–15:30 IST), the API pulls fresh quotes every 60 s. Exchange holidays are not modelled.

## Sorting

One-tap presets above the table: market cap, **biggest movers** (largest 1D move either way), top gainers, top losers, **price high → low / low → high**, volume, 1M %, A–Z. Column headers are also clickable on desktop.

## API

| Route | Returns |
|---|---|
| `GET /api/universe` | Latest quote per stock with name, sector, market cap, P/E, 52W range, 30-day sparkline, 1M/3M returns |
| `GET /api/history/<ticker>?limit=` | One row per trading day |
| `GET /api/predict/<ticker>` | 5-step forecast, CV MAE, feature weights |
| `GET /api/status` | Market open/closed, seeding flag, last fetch, simulated-data count |
| `POST /api/refresh` | Fetch live quotes now (409 if already running) |
| `GET /api/log` | Last 10 pipeline runs |

Tickers use the `.NS` suffix; `M&M.NS` must be URL-encoded as `M%26M.NS`.

## Keyboard

`/` search · `Esc` clear/close · `↑ ↓` or `j k` move · `s` star · `r` refresh · `w` watchlist

## Caveat

The forecast is a linear model on ~120 daily closes. It is a statistics demo, not investment advice.
