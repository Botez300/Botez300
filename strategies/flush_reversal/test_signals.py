"""Replay a synthetic flush-and-reversal session through the signal engine.

Run: python -m unittest strategies/flush_reversal/test_signals.py
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import signals  # noqa: E402  (run from this folder or via sys.path below)

BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "JPM", "LLY"]
OPEN = datetime(2026, 10, 8, 13, 30, tzinfo=timezone.utc)  # 9:30 ET


def path_spy(m):
    """Drift down, flush at minute 48 (10:18 ET), then rally."""
    if m < 40:
        return 600 - m * 0.05
    if m < 48:
        return 598 - (m - 40) * 0.4      # selloff into the flush
    return 594.8 + (m - 48) * 0.25       # recovery


def bar(t, o, c, v, kind="price"):
    h, l = max(o, c) + 0.05, min(o, c) - 0.05
    d = {"begins_at": t.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if kind == "price":
        d.update(open_price=o, close_price=c, high_price=h, low_price=l, volume=v)
    else:
        d.update(open_value=o, close_value=c, high_value=h, low_value=l)
    return d


def make_session(tmp: Path, minutes=90):
    spy, vix, eq = [], [], {s: [] for s in BASKET}
    for m in range(minutes):
        t = OPEN + timedelta(minutes=m)
        p0, p1 = path_spy(m - 1) if m else path_spy(0), path_spy(m)
        spy.append(bar(t, p0, p1, 100000))
        v = 16 + (m - 40) * 0.06 if 40 <= m <= 48 else (16.46 - (m - 48) * 0.03 if m > 48 else 16)
        vix.append(bar(t, v, v, 0, kind="index"))
        for k, s in enumerate(BASKET):
            prev = eq[s][-1]["close_price"] if eq[s] else 100.0
            if m < 40:
                # quiet drift: names alternate up/down so the TICK proxy sits near 0
                c = prev + (0.03 if (m + k) % 2 else -0.04)
            elif m >= 50 and k < 2:
                c = prev - 0.01   # two laggers stay soft during the bounce
            else:
                c = prev * path_spy(m) / path_spy(m - 1)
            vol = 15000 if c < prev and 40 <= m <= 48 else 5000
            eq[s].append(bar(t, prev, c, vol))
    def dump(name, results):
        (tmp / name).write_text(json.dumps({"data": {"results": results}}))
    dump("01_spy.json", [{"symbol": "SPY", "interval": "minute", "bars": spy}])
    dump("02_vix.json", [{"symbol": "VIX", "interval": "minute", "bars": vix}])
    dump("03_basket.json", [{"symbol": s, "interval": "minute", "bars": b} for s, b in eq.items()])
    prev_day = (OPEN - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dump("04_daily.json", [{"symbol": s, "interval": "day", "bars": [
        {"begins_at": prev_day, "open_price": 99, "close_price": 99.5, "high_price": 100, "low_price": 98, "volume": 1}
    ]} for s in BASKET])


class FlushReversalTest(unittest.TestCase):
    def run_engine(self, blackout=""):
        with tempfile.TemporaryDirectory() as d:
            make_session(Path(d))
            minute, daily = signals.load_cache(Path(d))
            und, vix = minute.pop("SPY"), minute.pop("VIX")
            ints = signals.internals(minute, signals.prior_closes(daily, und[0].t.date()))
            bl = [signals.time.fromisoformat(x) for x in blackout.split(",") if x]
            return signals.run(und, vix, ints, bl)

    def test_full_sequence(self):
        st = self.run_engine()
        rules = [e["rule"] for e in st.events]
        for r in ("1 SETUP", "2 CONFIRM", "3 ENTRY", "5 EXIT"):
            self.assertIn(r, rules, st.events)
        self.assertLess(rules.index("1 SETUP"), rules.index("3 ENTRY"))
        entry = next(e for e in st.events if e["rule"] == "3 ENTRY")
        self.assertGreater(entry["time"], "10:18")

    def test_blackout_blocks_setup(self):
        st = self.run_engine(blackout="10:15")
        rules = [e["rule"] for e in st.events]
        self.assertNotIn("3 ENTRY", rules)
        self.assertIn("6 NO TRADE", rules)


if __name__ == "__main__":
    unittest.main()
