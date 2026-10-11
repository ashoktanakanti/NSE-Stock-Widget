# NSE Stock Widget

[![CI](https://github.com/ashoktanakanti/NSE-Stock-Widget/actions/workflows/ci.yml/badge.svg)](https://github.com/ashoktanakanti/NSE-Stock-Widget/actions/workflows/ci.yml)

A terminal-style market dashboard for the **Nifty 500**: live prices, 6 months of history, market breadth, and a next-day forecast for every stock that is honestly scored against a naive baseline.

**Live demo: [nse-stock-widget.onrender.com](https://nse-stock-widget.onrender.com/)**

> Hosted on a free plan. If nobody has visited for a while, the first load takes about a minute while the server wakes up.

## Features

- **499 NSE stocks** with price, 1D / 1M change, volume, market cap, P/E and 52-week range
- **Sorting:** biggest movers, top gainers and losers, price high → low and low → high, market cap, volume
- **Sector filters** with each sector's average move, plus an advancing vs declining bar
- **Interactive chart** for each stock (1M / 3M / 6M) with a 5-day forecast and error band
- **Model vs baseline** shown for every stock, with a plain verdict on which one wins
- **Watchlist** saved in your browser, **keyboard shortcuts** (`/` `↑↓` `s` `r` `w`), mobile layout

## Model vs baseline

Each stock gets a Ridge regression that predicts tomorrow's **return** from the last few days (recent returns, distance from the 5-day mean, volatility, relative volume). It is scored with walk-forward cross-validation against the naive forecast **"tomorrow's close = today's close"**.

Across all 499 stocks (`python predictor.py`):

| | Median error (% of price) |
|---|---|
| Naive: tomorrow = today | **1.42%** |
| Ridge model | 1.46% |

**The naive baseline wins on 82% of stocks.** That is the expected result: daily returns are close to unpredictable from past prices alone, so the app shows both errors instead of presenting the forecast as a signal.

How the model got here:

- **Same-day leakage.** The first version used the day's `change_pct` as a feature, which encodes the target price. Cross-validation error looked near-perfect. Every feature now uses only data from before the predicted day, and a test enforces it.
- **Price level → returns.** Regressing the price level lost to the baseline on 94% of stocks because it could not extrapolate outside its training range. Predicting returns closed most of that gap.
- **Lookahead in normalization.** Volume was min-max scaled over the whole series, leaking future volumes into past rows. The leakage test caught it; volume is now relative to its trailing 20-day average.

Simulated prices (used only if Yahoo is unreachable) are labelled `SIM` in the UI and never get a forecast.

## Tech stack

**Frontend:** React, Vite, Tailwind CSS, Vitest
**Backend:** Python, Flask, SQLite, scikit-learn, pytest
**Data:** Yahoo Finance (delayed quotes), Nifty 500 list from niftyindices.com

## Run locally

```bash
pip install -r requirements.txt
npm --prefix nse-terminal install
npm --prefix nse-terminal run build
python app.py
```

Then open http://localhost:5001.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                         # backend: leakage, baseline, data cleaning, API
npm --prefix nse-terminal test # frontend: sorting, filtering, formatting
```

## Disclaimer

The forecast is a statistics exercise, not investment advice.
