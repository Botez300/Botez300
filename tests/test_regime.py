from datetime import date, timedelta

import numpy as np

from src.config import Pair
from src.regime.classifier import Regime, classify, regime_frame
from src.regime.indicators import rsi_wilder, sma
from tests.conftest import make_bars

PAIR = Pair("T", "IDX", "BULL", "BEAR", "broad", "primary")


def _bars(trend: float, n=400, noise=0.004, seed=1):
    rng = np.random.default_rng(seed)
    r = trend + rng.normal(0, noise, n)
    idx = 100 * np.exp(np.cumsum(r))
    bull = 50 * np.exp(np.cumsum(3 * r))
    bear = 50 * np.exp(np.cumsum(-3 * r))
    return {"IDX": make_bars(idx), "BULL": make_bars(bull), "BEAR": make_bars(bear)}


def test_rsi_bounds_and_nan_warmup():
    s = make_bars(np.linspace(100, 150, 60))["close"]
    r = rsi_wilder(s, 14)
    assert r.iloc[:14].isna().all()
    assert (r.dropna() >= 0).all() and (r.dropna() <= 100).all()
    assert r.iloc[-1] > 90  # monotonic rise


def test_sma_needs_full_window():
    s = make_bars(np.arange(1, 11))["close"]
    assert sma(s, 5).iloc[3] != sma(s, 5).iloc[3]  # NaN
    assert sma(s, 5).iloc[4] == 3.0


def test_bullish_regime(cfg):
    bars = _bars(0.0015)
    as_of = bars["IDX"]["date"].iloc[-1] + timedelta(days=1)
    r = classify(PAIR, bars, cfg["regime"], as_of)
    assert r.regime is Regime.BULLISH and r.trade_symbol == "BULL"


def test_bearish_regime(cfg):
    bars = _bars(-0.0015)
    as_of = bars["IDX"]["date"].iloc[-1] + timedelta(days=1)
    r = classify(PAIR, bars, cfg["regime"], as_of)
    assert r.regime is Regime.BEARISH and r.trade_symbol == "BEAR"


def test_insufficient_history_is_neutral(cfg):
    bars = _bars(0.0015, n=120)
    as_of = bars["IDX"]["date"].iloc[-1] + timedelta(days=1)
    r = classify(PAIR, bars, cfg["regime"], as_of)
    assert r.regime is Regime.NEUTRAL


def test_stale_data_is_neutral(cfg):
    bars = _bars(0.0015)
    as_of = bars["IDX"]["date"].iloc[-1] + timedelta(days=30)
    r = classify(PAIR, bars, cfg["regime"], as_of)
    assert r.regime is Regime.NEUTRAL and any("stale" in x for x in r.reasons)


def test_incomplete_candle_excluded(cfg):
    bars = _bars(0.0015)
    last = bars["IDX"]["date"].iloc[-1]
    r = classify(PAIR, bars, cfg["regime"], last)  # as_of == last bar date -> that bar is not complete
    assert r.bar_date < last


def test_frame_is_causal(cfg):
    """Regime on day d must not change when future bars are appended."""
    bars = _bars(0.0008, n=450)
    full = regime_frame(PAIR, bars, cfg["regime"])
    cut = {k: v.iloc[:400] for k, v in bars.items()}
    part = regime_frame(PAIR, cut, cfg["regime"])
    assert list(full["regime"].iloc[:395]) == list(part["regime"].iloc[:395])


def test_live_data_regime_runs(cfg):
    from src.config import all_symbols, pairs
    from src.data.history import load_bars
    bars = {s: load_bars(s) for s in all_symbols(cfg)}
    for p in pairs(cfg):
        r = classify(p, bars, cfg["regime"], date(2026, 11, 14))
        assert r.bar_date == date(2026, 11, 13)
