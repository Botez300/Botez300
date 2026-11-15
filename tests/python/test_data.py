from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pandas as pd
import pytest

from conftest import FROZEN_NOW
from legion_data import (
    AlpacaProvider,
    DataStatus,
    DemoProvider,
    PolygonProvider,
    ProviderError,
    SymbolNotFound,
    Verification,
    build_provider,
    calendar,
    quality,
)
from legion_data.base import daily_frame, to_timeframe
from legion_data.resample import resample

# ------------------------------------------------------------------ calendar


def test_nyse_holidays_match_published_schedule():
    # https://www.nyse.com/markets/hours-calendars
    assert calendar.holidays(2024) == frozenset(map(date.fromisoformat, [
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04",
        "2024-09-02", "2024-11-28", "2024-12-25"]))
    assert calendar.holidays(2025) == frozenset(map(date.fromisoformat, [
        "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04",
        "2025-09-01", "2025-11-27", "2025-12-25"]))
    assert date(2021, 12, 31) not in calendar.holidays(2021)  # New Year's 2022 fell on Saturday: not observed
    assert date(2021, 6, 18) not in calendar.holidays(2021)  # Juneteenth observed from 2022
    assert len(calendar.sessions(date(2024, 1, 1), date(2024, 12, 31))) == 252


def test_last_completed_session_respects_close_time_and_dst():
    ny = calendar.NY
    assert calendar.last_completed_session(datetime(2025, 6, 13, 15, 59, tzinfo=ny)) == date(2025, 6, 12)
    assert calendar.last_completed_session(datetime(2025, 6, 13, 16, 0, tzinfo=ny)) == date(2025, 6, 13)
    assert calendar.last_completed_session(datetime(2025, 6, 15, 12, 0, tzinfo=ny)) == date(2025, 6, 13)  # Sunday
    assert calendar.last_completed_session(datetime(2025, 7, 4, 18, 0, tzinfo=ny)) == date(2025, 7, 3)  # holiday
    # 20:30 UTC is after the close in summer (EDT, 16:30) but before it in winter (EST, 15:30).
    assert calendar.last_completed_session(datetime(2025, 7, 1, 20, 30, tzinfo=UTC)) == date(2025, 7, 1)
    assert calendar.last_completed_session(datetime(2025, 1, 7, 20, 30, tzinfo=UTC)) == date(2025, 1, 6)


# ---------------------------------------------------------------------- demo


def test_demo_is_deterministic_and_labelled_simulated(demo):
    a, b = demo.get_bars("ALFA"), DemoProvider(clock=lambda: FROZEN_NOW).get_bars("ALFA")
    pd.testing.assert_frame_equal(a.frame, b.frame)
    assert a.status is DataStatus.SIMULATED and a.verification is Verification.SIMULATED
    assert a.provider == "demo" and a.exchange == "SIM" and not a.last_bar_forming
    assert a.frame.index[-1].date() == date(2025, 6, 13)
    assert a.warnings == []


def test_demo_history_does_not_change_when_time_advances(demo):
    """Yesterday's simulated bars must be identical tomorrow (prefix stability)."""
    later = DemoProvider(clock=lambda: FROZEN_NOW + timedelta(days=200))
    for symbol in ("SIMX", "SXTK", "PETR"):
        old, new = demo.get_bars(symbol).frame, later.get_bars(symbol, start=date(2015, 1, 1)).frame
        assert len(new.loc[old.index[-1]:]) > 100
        pd.testing.assert_frame_equal(old, new.loc[old.index[0]:old.index[-1]])


def test_demo_universe_bars_are_valid(demo):
    universe = demo.universe()
    assert len(universe) > 60 and len({s.symbol for s in universe}) == len(universe)
    for info in universe:
        f = demo.get_bars(info.symbol).frame
        assert (f["high"] >= f[["open", "close"]].max(axis=1)).all() and (f["low"] <= f[["open", "close"]].min(axis=1)).all()
        assert (f[["open", "high", "low", "close"]] > 0).all().all() and (f["volume"] > 0).all()
        assert "simulated" in info.name.lower()


def test_demo_search_and_unknown_symbol(demo):
    assert [s.symbol for s in demo.search("alf")] == ["ALFA"]
    assert "QBIT" in [s.symbol for s in demo.search("foundry")]
    assert len(demo.search("", 5)) == 5
    with pytest.raises(SymbolNotFound):
        demo.get_bars("AAPL")  # real tickers do not exist in the simulated universe


# ------------------------------------------------------------- resample / forming


def test_weekly_and_monthly_resample(demo):
    daily = demo.get_bars("ALFA").frame
    weekly = resample(daily, "1W")
    week = daily.loc["2025-06-09":"2025-06-13"]
    last = weekly.iloc[-1]
    assert weekly.index[-1] == week.index[0]
    assert (last["open"], last["close"]) == (week["open"].iloc[0], week["close"].iloc[-1])
    assert (last["high"], last["low"], last["volume"]) == (week["high"].max(), week["low"].min(), week["volume"].sum())
    monthly = resample(daily, "1M")
    assert monthly.index[-1].date() == date(2025, 6, 2)  # first session of June 2025
    assert monthly["volume"].sum() == pytest.approx(daily["volume"].sum())


def test_incomplete_periods_are_flagged_forming(demo):
    assert not demo.get_bars("ALFA", "1W").last_bar_forming  # Friday close completes the week
    assert demo.get_bars("ALFA", "1M").last_bar_forming  # June has sessions left
    midweek = DemoProvider(clock=lambda: datetime(2025, 6, 11, 21, 30, tzinfo=UTC)).get_bars("ALFA", "1W")
    assert midweek.last_bar_forming and midweek.verification is Verification.SIMULATED
    assert len(midweek.completed()) == len(midweek.frame) - 1


# -------------------------------------------------------------------- quality


def _days(n, start=date(2025, 3, 3)):
    return calendar.sessions(start, start + timedelta(days=n * 2))[:n]


def _frame(rows):
    return daily_frame(rows)


def test_quality_flags_bad_data():
    d = _days(6)
    good = [(x, 10, 11, 9, 10.5, 1000) for x in d]
    assert quality.check_daily(_frame(good)) == []
    assert quality.check_daily(_frame([])) == ["error:no_bars"]

    bad = list(good)
    bad[2] = (d[2], 10, 9.5, 9, 10.5, 1000)  # high below close
    assert "error:invalid_ohlc:1" in quality.check_daily(_frame(bad))
    zero = list(good)
    zero[3] = (d[3], 10, 11, 9, 10.5, 0)
    assert "zero_volume:1" in quality.check_daily(_frame(zero))
    assert quality.check_daily(_frame(zero), expect_volume=False) == []
    gap = good[:3] + good[4:]
    assert any(w.startswith(f"missing_sessions:1:first={d[3]}") for w in quality.check_daily(_frame(gap)))
    split = good[:3] + [(x, 5, 5.5, 4.5, 5.25, 2000) for x in d[3:]]  # looks like an unadjusted 2:1 split
    assert "large_gap:1" in quality.check_daily(_frame(split))
    weekend = good + [(date(2025, 3, 15), 10, 11, 9, 10.5, 1000)]
    assert "weekend_bars:1" in quality.check_daily(_frame(weekend))
    assert any(w.startswith("stale:") for w in quality.check_daily(_frame(good), now=FROZEN_NOW))


def test_normalize_sorts_and_dedupes():
    d = _days(3)
    rows = [(d[1], 10, 11, 9, 10, 1), (d[0], 10, 11, 9, 10, 1), (d[1], 20, 21, 19, 20, 2)]
    frame, warnings = quality.normalize(_frame(rows))
    assert list(frame.index.date) == d[:2] and frame["close"].iloc[-1] == 20
    assert warnings == ["unsorted_bars:sorted", "duplicate_bars:1"]


# -------------------------------------------------------------------- vendors


def test_build_provider_never_falls_back_to_demo():
    assert isinstance(build_provider("demo"), DemoProvider)
    with pytest.raises(ProviderError, match="ALPACA_API_KEY_ID"):
        build_provider("alpaca")
    with pytest.raises(ProviderError, match="POLYGON_API_KEY"):
        build_provider("polygon")


def test_alpaca_adapter_paginates_and_normalizes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["APCA-API-KEY-ID"] == "key" and request.headers["APCA-API-SECRET-KEY"] == "secret"
        if request.url.path == "/v2/assets/SPY":
            return httpx.Response(200, json={"symbol": "SPY", "name": "SPDR S&P 500", "exchange": "ARCA", "tradable": True})
        assert request.url.path == "/v2/stocks/SPY/bars" and request.url.params["adjustment"] == "all"
        if "page_token" not in request.url.params:
            return httpx.Response(200, json={"bars": [
                {"t": "2025-06-11T04:00:00Z", "o": 600, "h": 603, "l": 599, "c": 602, "v": 1000}],
                "next_page_token": "abc"})
        return httpx.Response(200, json={"bars": [
            {"t": "2025-06-12T04:00:00Z", "o": 602, "h": 605, "l": 601, "c": 604, "v": 1100},
            {"t": "2025-06-13T04:00:00Z", "o": 604, "h": 606, "l": 600, "c": 601, "v": 1200}], "next_page_token": None})

    p = AlpacaProvider("key", "secret", transport=httpx.MockTransport(handler))
    bars = p.get_bars("spy", start=date(2025, 6, 11), now=datetime(2025, 6, 13, 18, 0, tzinfo=UTC))
    assert list(bars.frame.index.date) == [date(2025, 6, 11), date(2025, 6, 12), date(2025, 6, 13)]
    assert bars.frame["close"].tolist() == [602, 604, 601]
    assert bars.status is DataStatus.DELAYED and bars.exchange == "ARCA"
    # 18:00 UTC is 14:00 in New York: today's bar is still forming, so the set is provisional.
    assert bars.last_bar_forming and bars.verification is Verification.PROVISIONAL
    assert len(bars.completed()) == 2
    after_close = p.get_bars("SPY", start=date(2025, 6, 11), now=FROZEN_NOW)
    assert not after_close.last_bar_forming and after_close.verification is Verification.VERIFIED


def test_polygon_adapter_maps_timestamps_and_errors():
    def ms(d):  # Polygon stamps daily bars at midnight New York
        return int(datetime(d.year, d.month, d.day, tzinfo=calendar.NY).timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        if request.url.path == "/v3/reference/tickers/MSFT":
            return httpx.Response(200, json={"results": {"ticker": "MSFT", "name": "Microsoft", "primary_exchange": "XNAS", "type": "CS"}})
        if request.url.path == "/v3/reference/tickers/NOPE":
            return httpx.Response(404, json={"status": "NOT_FOUND"})
        if request.url.path == "/v3/reference/tickers":
            return httpx.Response(200, json={"results": [{"ticker": "MSFT", "name": "Microsoft", "type": "CS"}]})
        assert request.url.path == "/v2/aggs/ticker/MSFT/range/1/day/2025-01-06/2025-01-08"
        return httpx.Response(200, json={"results": [
            {"t": ms(date(2025, 1, 6)), "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
            {"t": ms(date(2025, 1, 8)), "o": 1.5, "h": 2, "l": 1, "c": 1.8, "v": 12}]})

    p = PolygonProvider("k", transport=httpx.MockTransport(handler))
    bars = p.get_bars("MSFT", start=date(2025, 1, 6), end=date(2025, 1, 8), now=FROZEN_NOW)
    assert list(bars.frame.index.date) == [date(2025, 1, 6), date(2025, 1, 8)]  # winter (EST) dates survive conversion
    assert any(w.startswith("missing_sessions:1") for w in bars.warnings)
    assert not bars.complete and bars.verification is Verification.PROVISIONAL
    assert [s.symbol for s in p.search("micro")] == ["MSFT"]
    with pytest.raises(SymbolNotFound):
        p.get_symbol("NOPE")


def test_vendor_retries_then_reports_outage():
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"results": []})

    p = PolygonProvider("k", transport=httpx.MockTransport(flaky), backoff=0)
    assert p.search("x") == [] and calls["n"] == 3

    down = PolygonProvider("k", transport=httpx.MockTransport(lambda r: httpx.Response(503)), backoff=0, retries=2)
    with pytest.raises(ProviderError, match="failed after 3 attempts"):
        down.search("x")
    denied = PolygonProvider("k", transport=httpx.MockTransport(lambda r: httpx.Response(403)), backoff=0)
    with pytest.raises(ProviderError, match="credentials rejected"):
        denied.search("x")


def test_empty_vendor_response_is_unverified():
    p = PolygonProvider("k", transport=httpx.MockTransport(lambda r: httpx.Response(
        200, json={"results": {"ticker": "X", "name": "X"}} if "reference" in r.url.path else {"results": []})))
    bars = p.get_bars("X", now=FROZEN_NOW)
    assert bars.frame.empty and bars.verification is Verification.UNVERIFIED
    assert to_timeframe(bars, "1W").frame.empty
