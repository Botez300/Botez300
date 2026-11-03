import json
import subprocess
import sys
import unittest
from pathlib import Path

from robinhood_turtle_bot import signals


def make_bars(closes, spread=1.0):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        out.append({"begins_at": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}T00:00:00Z",
                    "open_price": str(prev), "close_price": str(c),
                    "high_price": str(max(prev, c) + spread), "low_price": str(min(prev, c) - spread)})
        prev = c
    return out


class TestIndicators(unittest.TestCase):
    def test_rsi_all_up_is_100(self):
        self.assertEqual(signals.wilder_rsi([float(i) for i in range(30)])[-1], 100.0)

    def test_n_constant_range(self):
        bars = signals.parse_bars(make_bars([100.0] * 40, spread=1.0))
        self.assertAlmostEqual(signals.turtle_n(bars)[-1], 2.0)

    def test_interpolated_bars_ignored(self):
        raw = make_bars([1.0, 2.0])
        raw[1]["interpolated"] = True
        self.assertEqual(len(signals.parse_bars(raw)), 1)


class TestEntry(unittest.TestCase):
    def uptrend(self):
        return make_bars([100 + i * 0.5 for i in range(120)])

    def test_forming_bar_dropped_by_default(self):
        raw = self.uptrend()
        e = signals.evaluate_entry("x", raw, live_price=1000)
        self.assertEqual(e.as_of_completed_bar, raw[-2]["begins_at"][:10])

    def test_too_few_bars_raises(self):
        with self.assertRaises(ValueError):
            signals.evaluate_entry("X", make_bars([100.0] * 30))

    def test_open_theoretical_trade_blocks_20_but_55_allowed(self):
        e = signals.evaluate_entry("X", self.uptrend(), live_price=1000)
        self.assertTrue(e.skip_20_day_due_to_prior_winner)
        self.assertEqual(e.signal, "ENTER_55_FAILSAFE")
        self.assertIsNotNone(e.initial_stop)
        self.assertEqual(len(e.pyramid_add_levels), 3)

    def test_low_rsi_blocks_entries(self):
        closes = [200 - i * 0.5 for i in range(120)]
        e = signals.evaluate_entry("X", make_bars(closes), live_price=1000)
        self.assertFalse(e.rsi_ok)
        self.assertEqual(e.signal, "NONE")

    def test_prior_loser_allows_20_day(self):
        # Breakout, then a sharp drop -> stopped out at a loss, then flat (no new breakout).
        closes = [100.0] * 60 + [103.0, 104.0] + [90.0] * 60
        cfg = signals.load_config()
        cfg["daily_rsi"]["minimum"] = 0  # isolate the winner filter from RSI
        e = signals.evaluate_entry("X", make_bars(closes, spread=0.5), live_price=500,
                                   last_bar_complete=True, cfg=cfg)
        last = e.last_theoretical_20_breakout
        self.assertIs(last["winner"], False)
        self.assertFalse(e.skip_20_day_due_to_prior_winner)
        self.assertEqual(e.signal, "ENTER_20")

    def test_prior_winner_skips_20_but_not_55(self):
        # Breakout, rally, then a slow drift down exits via the 10-day low above entry.
        closes = [100.0] * 60 + [101 + i for i in range(30)] + [129 - i * 0.3 for i in range(40)]
        cfg = signals.load_config()
        cfg["daily_rsi"]["minimum"] = 0
        e = signals.evaluate_entry("X", make_bars(closes, spread=0.5), live_price=500,
                                   last_bar_complete=True, cfg=cfg)
        self.assertIs(e.last_theoretical_20_breakout["winner"], True)
        self.assertTrue(e.skip_20_day_due_to_prior_winner)
        self.assertEqual(e.signal, "ENTER_55_FAILSAFE")


class TestPosition(unittest.TestCase):
    def test_stop_exit_ignores_rsi(self):
        r = signals.evaluate_position("X", make_bars([100.0] * 20), 95.0, [100.0], 2.0)
        self.assertIn("EXIT_ALL_2N_STOP", r["actions"])

    def test_add_signal(self):
        r = signals.evaluate_position("X", make_bars([100.0] * 20), 101.5, [100.0], 2.0)
        self.assertEqual(r["actions"], ["ADD_UNIT_SUBJECT_TO_RISK_GATE"])

    def test_no_add_past_four_units(self):
        r = signals.evaluate_position("X", make_bars([100.0] * 20), 110.0, [100, 101, 102, 103], 2.0)
        self.assertIsNone(r["next_add_level"])


class TestServer(unittest.TestCase):
    def test_stdio_roundtrip(self):
        server = Path(signals.__file__).with_name("mcp_server.py")
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "turtle_size_buy", "arguments": {
                "net_liquidation_value": 10000, "cash": 6000, "positions": [], "pending_buys": [],
                "symbol": "A", "expected_fill_price": 50, "N": 5}}},
        ]
        out = subprocess.run([sys.executable, str(server)], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                             capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
        self.assertEqual(len(out), 3)
        tools = json.loads(out[1])["result"]["tools"]
        self.assertEqual(len(tools), 4)
        sized = json.loads(json.loads(out[2])["result"]["content"][0]["text"])
        self.assertEqual(sized["permitted_shares"], 4)


if __name__ == "__main__":
    unittest.main()
