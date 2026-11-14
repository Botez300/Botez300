from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data.models import OptionQuote


@pytest.fixture(scope="session")
def cfg():
    return load_config()


def make_bars(closes, start="2020-01-01") -> pd.DataFrame:
    d = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"date": d.date, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1000})


@pytest.fixture
def quote_factory():
    def _q(symbol="SQQQ", strike=35.0, bid=0.80, ask=0.86, delta=-0.15, oi=1000, exp=date(2026, 12, 18),
           updated=datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc), iv=0.8, bid_size=50, ask_size=50,
           hfs=None, hfb=None, iid="iid-1"):
        return OptionQuote(iid, symbol, exp, strike, "put", 100, bid, ask, bid_size, ask_size, (bid + ask) / 2,
                           iv, delta, 0.01, -0.03, 0.02, oi, 10, updated, hfs, hfb)
    return _q
