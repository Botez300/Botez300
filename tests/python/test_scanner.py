from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from conftest import FROZEN_NOW
from legion_data import DemoProvider, ProviderError, SymbolInfo, calendar
from legion_data.base import MarketDataProvider, daily_frame
from legion_data.models import Adjustment, DataStatus
from legion_indicators import compute
from legion_scanner import PRESETS, ScanDefinition, ScanError, run_scan, validate


class FixtureProvider(MarketDataProvider):
    """Serves hand-built closes so expected scan results can be worked out by hand."""

    name, status, adjustment = "fixture", DataStatus.HISTORICAL, Adjustment.ALL

    def __init__(self, closes: dict[str, list[float]], end=date(2025, 6, 13)):
        self.closes, self.end = closes, end

    def search(self, query, limit=20):
        return []

    def get_symbol(self, symbol):
        if symbol not in self.closes:
            raise ProviderError(f"no {symbol}")
        return SymbolInfo(symbol, symbol, "TEST", "stock", provider=self.name)

    def universe(self):
        return [self.get_symbol(s) for s in self.closes]

    def fetch_daily(self, symbol, start, end):
        closes = self.closes[symbol]
        days = calendar.sessions(self.end - timedelta(days=len(closes) * 2), self.end)[-len(closes):]
        return daily_frame([(d, c, c + 1, c - 1, c, 1000 + i) for i, (d, c) in enumerate(zip(days, closes))])


def scan(provider, rules, now=FROZEN_NOW, **kw):
    defn = ScanDefinition.model_validate({"filter": {"logic": kw.pop("logic", "and"), "rules": rules}, **kw})
    return run_scan(provider, defn, provider.universe(), now=now)


CLOSE = {"field": "close"}


def sma(n, **kw):
    return {"indicator": "sma", "params": {"length": n}, **kw}


def test_comparison_offsets_and_crosses():
    p = FixtureProvider({
        "UP": [10, 10, 10, 10, 12],  # SMA(3) = 10.67 on the last bar; close crosses above it
        "DOWN": [10, 10, 10, 10, 8],
        "FLAT": [10, 10, 10, 10, 10],
        "WASUP": [10, 10, 10, 12, 12],  # crossed one bar earlier, so no cross on the last bar
    })
    assert [r["symbol"] for r in scan(p, [{"left": CLOSE, "op": ">", "right": sma(3)}])["rows"]] == ["UP", "WASUP"]
    assert [r["symbol"] for r in scan(p, [{"left": CLOSE, "op": "crosses_above", "right": sma(3)}])["rows"]] == ["UP"]
    assert [r["symbol"] for r in scan(p, [{"left": CLOSE, "op": "crosses_below", "right": sma(3)}])["rows"]] == ["DOWN"]
    assert [r["symbol"] for r in scan(p, [{"left": {"field": "close", "offset": 1}, "op": ">", "right": {"value": 11}}])["rows"]] == ["WASUP"]
    out = scan(p, [{"left": CLOSE, "op": ">=", "right": {"field": "close", "offset": 1, "multiplier": 1.2}}])
    assert [r["symbol"] for r in out["rows"]] == ["UP"]
    row = scan(p, [{"left": CLOSE, "op": ">", "right": sma(3)}])["rows"][0]
    assert row["values"] == {"close 1D": 12.0, "sma(3) 1D": pytest.approx(10.666667)}
    assert row["price"] == 12.0 and row["bar_date"] == "2025-06-13" and row["verification"] == "VERIFIED"


def test_and_or_groups_and_sorting():
    p = FixtureProvider({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1], "C": [3, 3, 3, 3, 9]})
    above = {"left": CLOSE, "op": ">", "right": {"value": 4}}
    falling = {"left": CLOSE, "op": "<", "right": {"field": "close", "offset": 1}}
    assert [r["symbol"] for r in scan(p, [above, falling])["rows"]] == []
    assert [r["symbol"] for r in scan(p, [above, falling], logic="or")["rows"]] == ["A", "B", "C"]
    nested = [{"logic": "or", "rules": [above, falling]}, {"left": CLOSE, "op": "<", "right": {"value": 6}}]
    assert [r["symbol"] for r in scan(p, nested)["rows"]] == ["A", "B"]
    ranked = scan(p, [above, falling], logic="or", sort_by=CLOSE, limit=2)
    assert [r["symbol"] for r in ranked["rows"]] == ["C", "A"] and ranked["matched"] == 3
    assert [r["symbol"] for r in scan(p, [above, falling], logic="or", sort_by=CLOSE, sort_desc=False)["rows"]] == ["B", "A", "C"]


def test_insufficient_history_is_reported_not_matched_or_failed():
    p = FixtureProvider({"SHORT": [10, 11, 12], "LONG": list(range(1, 60))})
    out = scan(p, [{"left": CLOSE, "op": ">", "right": sma(50)}])
    assert [r["symbol"] for r in out["rows"]] == ["LONG"] and out["insufficient"] == ["SHORT"]
    # In an OR group a decidable branch still decides.
    out = scan(p, [{"left": CLOSE, "op": ">", "right": sma(50)}, {"left": CLOSE, "op": ">", "right": {"value": 11}}], logic="or")
    assert [r["symbol"] for r in out["rows"]] == ["LONG", "SHORT"] and out["insufficient"] == []


def test_provider_errors_are_isolated_per_symbol():
    p = FixtureProvider({"A": [1, 2, 3]})
    defn = ScanDefinition.model_validate({"filter": {"rules": [{"left": CLOSE, "op": ">", "right": {"value": 0}}]}})
    out = run_scan(p, defn, [SymbolInfo("A", "A", "", "stock"), SymbolInfo("GONE", "GONE", "", "stock")], now=FROZEN_NOW)
    assert out["matched"] == 1 and out["errors"] == [{"symbol": "GONE", "error": "no GONE"}]


def test_forming_bars_are_never_used():
    """At 14:00 New York on a Wednesday the daily, weekly and monthly bars are all still forming."""
    closes = list(np.linspace(50, 60, 79)) + [1000.0]  # today's (forming) print is a wild outlier
    p = FixtureProvider({"X": closes}, end=date(2025, 6, 11))
    now = datetime(2025, 6, 11, 18, 0, tzinfo=UTC)
    out = scan(p, [{"left": CLOSE, "op": "<", "right": {"value": 100}},
                   {"left": {"field": "high", "timeframe": "1W"}, "op": "<", "right": {"value": 100}},
                   {"left": {"field": "high", "timeframe": "1M"}, "op": "<", "right": {"value": 100}}], now=now)
    assert out["matched"] == 1
    row = out["rows"][0]
    assert row["bar_date"] == "2025-06-10" and row["price"] == pytest.approx(closes[-2])
    # After the close the same bar counts.
    assert scan(p, [{"left": CLOSE, "op": "<", "right": {"value": 100}}],
                now=datetime(2025, 6, 11, 21, 0, tzinfo=UTC))["matched"] == 0


def test_historical_replay_matches_what_was_knowable_then(demo):
    """A scan run 'as of' an earlier date equals one run on that date: later data cannot leak in."""
    defn = ScanDefinition.model_validate(PRESETS[0]["definition"])
    then = FROZEN_NOW - timedelta(days=90)
    at_the_time = run_scan(DemoProvider(clock=lambda: then), defn, demo.universe())
    values = {r["symbol"]: r["values"] for r in at_the_time["rows"]}
    assert len(values) > 0
    for symbol, got in values.items():
        frame = demo.get_bars(symbol).frame.loc[: pd.Timestamp(calendar.last_completed_session(then), tz="UTC")]
        assert got["close 1D"] == pytest.approx(frame["close"].iloc[-1])
        assert got["sma(50) 1D"] == pytest.approx(compute("sma", frame, {"length": 50})["sma"][-1])
        assert got["rsi(14) 1D"] == pytest.approx(compute("rsi", frame)["rsi"][-1], abs=1e-6)


def test_presets_are_valid_and_run_on_demo_data(demo):
    assert len({p["id"] for p in PRESETS}) == len(PRESETS) >= 5
    total = 0
    for preset in PRESETS:
        out = run_scan(demo, ScanDefinition.model_validate(preset["definition"]), demo.universe())
        assert out["scanned"] == len(demo.universe()) and not out["errors"] and not out["insufficient"]
        assert out["data_status"] == "SIMULATED" and all(r["verification"] == "SIMULATED" for r in out["rows"])
        assert out["conditions"] and all(set(r["values"]) == set(out["columns"]) for r in out["rows"])
        total += out["matched"]
    assert total > 0


def test_multi_timeframe_preset_agrees_with_direct_calculation(demo):
    preset = next(p for p in PRESETS if p["id"] == "mtf-momentum")
    matched = {r["symbol"] for r in run_scan(demo, ScanDefinition.model_validate(preset["definition"]), demo.universe())["rows"]}
    expected = set()
    for info in demo.universe():
        d, w, m = (demo.get_bars(info.symbol, tf).completed() for tf in ("1D", "1W", "1M"))
        if all(compute("rsi", f)["rsi"][-1] > 50 for f in (d, w, m)) and compute("adx", d)["adx"][-1] > 20:
            expected.add(info.symbol)
    assert matched == expected and expected


@pytest.mark.parametrize("definition,message", [
    ({"filter": {"rules": [{"left": {"indicator": "nope"}, "op": ">", "right": {"value": 1}}]}}, "unknown indicator"),
    ({"filter": {"rules": [{"left": sma(0), "op": ">", "right": {"value": 1}}]}}, "between"),
    ({"filter": {"rules": [{"left": {"indicator": "macd", "output": "nope"}, "op": ">", "right": {"value": 1}}]}}, "unknown output"),
])
def test_semantic_validation(definition, message):
    with pytest.raises(ScanError, match=message):
        validate(ScanDefinition.model_validate(definition))


@pytest.mark.parametrize("definition", [
    {"filter": {"rules": []}},
    {"filter": {"rules": [{"left": {"field": "close", "value": 1}, "op": ">", "right": {"value": 1}}]}},
    {"filter": {"rules": [{"left": {}, "op": ">", "right": {"value": 1}}]}},
    {"filter": {"rules": [{"left": CLOSE, "op": "~", "right": {"value": 1}}]}},
    {"filter": {"rules": [{"left": {"field": "close", "eval": "__import__('os')"}, "op": ">", "right": {"value": 1}}]}},
    {"filter": {"rules": [{"logic": "and", "rules": [{"logic": "and", "rules": [{"logic": "and", "rules": [
        {"logic": "and", "rules": [{"left": CLOSE, "op": ">", "right": {"value": 1}}]}]}]}]}]}},
])
def test_schema_rejects_malformed_definitions(definition):
    with pytest.raises(ValidationError):
        ScanDefinition.model_validate(definition)
