# NSE Stock Widget

[![CI](https://github.com/ashoktanakanti/NSE-Stock-Widget/actions/workflows/ci.yml/badge.svg)](https://github.com/ashoktanakanti/NSE-Stock-Widget/actions/workflows/ci.yml)

A dashboard for the Nifty 500. It shows prices, about six months of daily history, market breadth, and a next-day forecast for each stock. Every forecast is scored against a naive baseline, and the page shows both results.

**Live demo:** [nse-stock-widget.onrender.com](https://nse-stock-widget.onrender.com/). The free plan sleeps when idle, so the first load can be slow.

## What the page shows

- Price, 1-day and 1-month change, volume, market cap and P/E for each stock. The stock list covers the 500 tickers in the bundled Nifty 500 list.
- A 3-month range in the table. On a stock's detail view, the 52-week range appears when Yahoo returns it.
- Sorting by biggest movers, top gainers, top losers, price (high to low and low to high), market cap and volume.
- Sector filters, and a bar showing advancing, unchanged and declining stocks.
- A chart with 1M, 3M and 6M ranges, a five-day forecast, and an error band.
- A comparison of the model's error with the naive error for each stock, with a line saying which one did better on that stock.
- A watchlist saved in the browser's local storage.
- Keyboard shortcuts: `/` to search, `↑` and `↓` (or `j` and `k`) to move through the list, `s` to star, `r` to refresh, `w` to switch to the watchlist, and `Esc`.
- A layout for phones.

## How the forecast works

The model is a Ridge regression, trained separately for each stock. It predicts tomorrow's return from five inputs:

- yesterday's return
- the return the day before
- the distance from the 5-day average price
- the 5-day price volatility
- yesterday's volume relative to its 20-day average

The code is in `predictor.py`. The Ridge penalty (alpha = 100) was chosen with walk-forward cross-validation over 1, 10, 100 and 1000.

The model is compared with the naive forecast, "tomorrow's close equals today's close." The comparison uses walk-forward folds. Each fold trains on the past, predicts the next block of days, and measures the mean absolute error against the naive forecast on those same days.

The forecast is five steps ahead. Each predicted close becomes the input for the next step. The error band is the cross-validation error multiplied by the square root of the number of days ahead.

Three things shaped the current version:

- **Same-day values were leaking.** Early inputs included the day's `change_pct` and `volume`, which describe the close being predicted. Every input now uses only data from before the predicted day. `tests/test_predictor.py` checks this.
- **Price levels don't extrapolate.** A version that regressed on price levels did worse than the naive forecast on most stocks, because it can't predict prices outside the range it was trained on. Predicting returns avoids that problem.
- **Volume scaling used future data.** Volume was scaled over the whole series. It's now relative to a trailing 20-day average.

### Reproducing the comparison

`python predictor.py` scores the model against the naive baseline across every stock in the local database. It prints the number of stocks, the share where the model beats the baseline, the median error for each, and the median skill. Those results depend on the price history in your database when you run it. The script needs the database to be filled from Yahoo first, which happens when the app starts.

## Data sources

- **Prices and quotes:** Yahoo Finance's chart and quote endpoints. These are unofficial, and they can be rate-limited or blocked on cloud hosts.
- **Stock list:** `data/nifty500.csv`, from niftyindices.com.
- **Fundamentals:** `data/fundamentals.csv` holds shares outstanding and trailing EPS. Market cap and P/E are calculated from these when Yahoo doesn't supply them.
- **History:** On first start, the app loads about six months of daily prices for each ticker that has fewer than 15 stored prices.
- **Simulated data:** If Yahoo can't be reached for a ticker, the app generates a 60-day random-walk history and labels it `SIM`. Simulated tickers never get a forecast.

The market-hours check uses NSE's regular session, 09:15 to 15:30 IST, Monday to Friday. Exchange holidays are not modelled. While the market is open, quotes refresh every 60 seconds.

## Run locally

Requirements: Python 3.12 and Node.js 20. CI and the Docker build use the same versions.

```bash
pip install -r requirements.txt
npm --prefix nse-terminal install
npm --prefix nse-terminal run build
python app.py
```

Then open http://localhost:5001. The server listens on 127.0.0.1 unless `HOST` is set. The port comes from `PORT`.

The database is a SQLite file, `stock_market.db`, created in the project folder. Set `DB_PATH` to put it somewhere else.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                            # backend: API, extractor, predictor
npm --prefix nse-terminal test    # frontend: sorting, filtering, formatting
```

CI runs pyflakes, pytest, a Prettier check, the frontend tests, and the frontend build on every push and pull request.

## Deploy on Render

`render.yaml` defines one Docker web service on the free plan. The health check is `/api/status`.

The Docker image builds the React app, then serves it from a Flask API under gunicorn. gunicorn runs a single worker with eight threads, because the quote refresh and its state live inside the process.

The Docker image sets `DB_PATH=/tmp/stock_market.db`. The database is rebuilt when the container starts, so it doesn't persist across restarts.

## Tech stack

- **Backend:** Python, Flask, pandas, NumPy, scikit-learn, SQLite, gunicorn (in Docker)
- **Frontend:** React 18, Vite 5, Tailwind CSS 3, Vitest, Prettier

## Limitations

- Yahoo's endpoints are unofficial. When a ticker can't be fetched, the app shows simulated data and labels it `SIM`.
- The forecast is a statistics exercise. The page shows the baseline comparison for each stock, so you can see where the model doesn't beat the naive forecast.

## Disclaimer

The forecast is a statistics exercise, not investment advice.
