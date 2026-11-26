"""Builds independent market snapshots from the Robinhood adapter."""
from datetime import timedelta
from .rh import RobinhoodClient
from .strategies import Snapshot

class RobinhoodMarket:
    def __init__(self, client: RobinhoodClient, history_days=800): self.c, self.days = client, history_days
    def snapshot(self, ticker, now) -> Snapshot:
        start = (now - timedelta(days=self.days)).date().isoformat()
        try: e = self.c.earnings_dates(ticker, now.date().isoformat())
        except Exception: e = None
        return Snapshot(ticker, self.c.quote(ticker), self.c.bars(ticker, start), self.c.bars("SPY", start),
                        self.c.fundamentals(ticker), e, now)
