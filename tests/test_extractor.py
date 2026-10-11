import pytest

import stock_extractor as se


def test_change_pct_is_vs_previous_close_not_open():
    df = se.clean_quotes([{
        "ticker": "X.NS", "price": 110.0, "open_price": 120.0, "high_price": 121.0,
        "low_price": 109.0, "volume": 5, "prev_close": 100.0, "fetched_at": "2026-01-02 04:00:00+00:00",
    }])
    assert df.loc[0, "change_pct"] == pytest.approx(10.0)


def test_history_change_pct_uses_previous_bar():
    rows = [{"ticker": "X.NS", "price": p, "fetched_at": f"2026-01-0{i + 1} 03:45:00+00:00"}
            for i, p in enumerate([100.0, 105.0, 99.75])]
    df = se.clean_quotes(rows)
    assert df["change_pct"].round(2).tolist()[1:] == [5.0, -5.0]


def test_missing_ohlc_filled_from_same_ticker_not_cross_ticker_median():
    rows = [
        {"ticker": "CHEAP.NS", "price": 10.0, "open_price": None, "high_price": None,
         "low_price": None, "fetched_at": "2026-01-01 03:45:00+00:00"},
        {"ticker": "PRICEY.NS", "price": 12000.0, "open_price": 11900.0, "high_price": 12100.0,
         "low_price": 11800.0, "fetched_at": "2026-01-01 03:45:00+00:00"},
    ]
    cheap = se.clean_quotes(rows).set_index("ticker").loc["CHEAP.NS"]
    assert cheap["low_price"] == cheap["high_price"] == 10.0


def test_load_universe_skips_placeholders_and_cleans_names(tmp_path):
    csv = tmp_path / "n.csv"
    csv.write_text(
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        "Mahindra & Mahindra Ltd.,Automobile and Auto Components,M&M,EQ,X\n"
        "Dummy Holdings Limited,Financial Services,DUMMYHEG,EQ,Y\n",
        encoding="utf-8",
    )
    assert se.load_universe(str(csv)) == {"M&M": ("Mahindra & Mahindra", "Auto")}


def test_unlisted_symbol_is_skipped_not_simulated(monkeypatch):
    monkeypatch.setattr(se, "_yahoo_chart", lambda *a: se.NOT_LISTED)
    assert se.fetch_price_history("GONE.NS") == []


def test_network_failure_falls_back_to_flagged_simulation(monkeypatch):
    monkeypatch.setattr(se, "_yahoo_chart", lambda *a: None)
    rows = se.fetch_price_history("DOWN.NS")
    assert rows and all(r["source"] == "simulated" for r in rows)


def test_symbol_helpers():
    assert se.symbol_of("M&M.NS") == "M&M"
    assert se.is_nse_ticker("tcs.ns") and not se.is_nse_ticker("TCS.BO")
