# NSE Stock Widget

A terminal-style market dashboard for the **Nifty 500**: live prices, 6 months of history, market breadth, and a short-term price forecast for every stock.

**Live demo: [nse-stock-widget.onrender.com](https://nse-stock-widget.onrender.com/)**

> Hosted on a free plan. If nobody has visited for a while, the first load takes about a minute while the server wakes up.

## Features

- **499 NSE stocks** with price, 1D / 1M change, volume, market cap, P/E and 52-week range
- **Sorting:** biggest movers, top gainers and losers, price high → low and low → high, market cap, volume
- **Sector filters** with each sector's average move, plus an advancing vs declining bar
- **Interactive chart** for each stock (1M / 3M / 6M) with a 5-day forecast and error band
- **Watchlist** saved in your browser
- **Keyboard shortcuts:** `/` search · `↑ ↓` move · `s` star · `r` refresh · `w` watchlist
- Works on desktop and mobile

## Tech stack

**Frontend:** React, Vite, Tailwind CSS
**Backend:** Python, Flask, SQLite, scikit-learn
**Data:** Yahoo Finance (delayed quotes), Nifty 500 list from niftyindices.com

## Run locally

```bash
pip install -r requirements.txt
npm --prefix nse-terminal install
npm --prefix nse-terminal run build
python app.py
```

Then open http://localhost:5001.

## Disclaimer

The forecast is a simple statistical model built for learning. It is not investment advice.
