import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

# Import the app without seeding or starting background threads
os.environ["NSE_AUTOBOOT"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_daily(prices, start="2026-01-01", volume=1_000_000, source="live"):
    """Daily bars in the shape predictor.build_features expects."""
    day0 = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    prices = list(prices)
    return pd.DataFrame({
        "price": prices,
        "volume": [volume + 1000 * i for i in range(len(prices))],
        "change_pct": [0.0] + [(b / a - 1) * 100 for a, b in zip(prices, prices[1:])],
        "source": source,
        "fetched_at": [(day0 + timedelta(days=i)).isoformat(sep=" ") for i in range(len(prices))],
    })


@pytest.fixture
def random_walk():
    rng = np.random.default_rng(7)
    return make_daily(1000 * np.cumprod(1 + rng.normal(0, 0.015, 150)))


@pytest.fixture
def db(tmp_path):
    """Empty schema in a temp SQLite file."""
    from stock_extractor import init_db
    path = str(tmp_path / "test.db")
    init_db(path).close()
    return path
