"""Builds scanner Data bundles from the read-only Robinhood adapter. Every field that Robinhood cannot supply stays None
(=> UNVERIFIED downstream). Nothing is estimated."""
from datetime import timedelta
from .defs import Data
from . import series as S

def build(client, ticker, now, market_index=None, years=6):
    start = lambda y: (now - timedelta(days=365 * y)).date().isoformat()
    d = Data(ticker, now)
    try: d.daily = S.completed(client.bars(ticker, start(2), interval="day"), "day", now)
    except Exception: pass
    try: d.weekly = S.completed(client.bars(ticker, start(years), interval="week"), "week", now)
    except Exception: pass
    try: d.monthly = S.completed(client.bars(ticker, start(years), interval="month"), "month", now)
    except Exception: pass
    try:
        f = client.fundamentals(ticker); d.market_cap, d.fundamentals_as_of = f.get("market_cap"), f.get("market_date")
    except Exception: pass
    try:
        q = client.quote(ticker)
        if q.bid and q.ask and q.ask >= q.bid: d.spread_pct = (q.ask - q.bid) / ((q.ask + q.bid) / 2)
    except Exception: pass
    try: d.eps, d.eps_basis = client.earnings_history(ticker)
    except Exception: pass
    d.analyst_buy_dates = None            # Robinhood exposes aggregate counts + updated_at only, never dated individual ratings
    if market_index:
        try: d.market_daily = S.completed(client.index_bars(market_index, start(2)), "day", now)
        except Exception: pass
    return d
