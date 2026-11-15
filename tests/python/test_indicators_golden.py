"""Golden tests: Legion indicators vs TA-Lib (BSD-licensed, independent implementation).

TA-Lib is a test-only dependency; nothing in the product imports it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

talib = pytest.importorskip("talib")

from legion_indicators import compute  # noqa: E402


def _random_walk(seed: int, n: int = 900) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 50.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.018, n)))
    open_ = np.concatenate([[50.0], close[:-1]]) * np.exp(rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.006, n)))
    volume = np.round(rng.lognormal(13, 0.5, n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


@pytest.fixture(scope="module", params=["walk-1", "walk-2", "demo-ALFA", "demo-PETR"])
def frame(request, demo) -> pd.DataFrame:
    if request.param.startswith("walk"):
        return _random_walk(int(request.param[-1]))
    return demo.get_bars(request.param.split("-")[1]).frame.reset_index(drop=True)


def _eq(ours: np.ndarray, ref: np.ndarray, *, skip: int = 0, rtol: float = 1e-9, atol: float = 1e-9) -> None:
    """Same warm-up (NaN pattern) and same values from `skip` onward."""
    ours, ref = np.asarray(ours, float)[skip:], np.asarray(ref, float)[skip:]
    np.testing.assert_array_equal(np.isnan(ours), np.isnan(ref), err_msg="warm-up length differs")
    ok = ~np.isnan(ref)
    assert ok.sum() > 100
    np.testing.assert_allclose(ours[ok], ref[ok], rtol=rtol, atol=atol)


def _cols(df):
    return (df[c].to_numpy("float64") for c in ("high", "low", "close", "volume"))


@pytest.mark.parametrize("length", [5, 20, 50, 200])
def test_moving_averages(frame, length):
    c = frame["close"].to_numpy("float64")
    _eq(compute("sma", frame, {"length": length})["sma"], talib.SMA(c, length))
    _eq(compute("ema", frame, {"length": length})["ema"], talib.EMA(c, length))
    _eq(compute("wma", frame, {"length": length})["wma"], talib.WMA(c, length))


@pytest.mark.parametrize("length", [7, 14, 21])
def test_rsi(frame, length):
    _eq(compute("rsi", frame, {"length": length})["rsi"], talib.RSI(frame["close"].to_numpy("float64"), length))


@pytest.mark.parametrize("fast,slow,signal", [(12, 26, 9), (5, 35, 5)])
def test_macd(frame, fast, slow, signal):
    out = compute("macd", frame, {"fast": fast, "slow": slow, "signal": signal})
    macd, sig, hist = talib.MACD(frame["close"].to_numpy("float64"), fast, slow, signal)
    # TA-Lib only reports MACD once the signal exists; ours also reports the line during signal warm-up.
    first = int(np.argmax(~np.isnan(macd)))
    assert np.isnan(out["signal"][:first]).all()
    for ours, ref in ((out["macd"], macd), (out["signal"], sig), (out["histogram"], hist)):
        _eq(ours, ref, skip=first)


def test_stochastic(frame):
    h, l, c, _ = _cols(frame)
    out = compute("stoch", frame, {"k_length": 14, "k_smooth": 3, "d_smooth": 3})
    k, d = talib.STOCH(h, l, c, fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    first = int(np.argmax(~np.isnan(d)))  # TA-Lib withholds %K until %D exists
    _eq(out["k"], k, skip=first)
    _eq(out["d"], d, skip=first)


def test_stoch_rsi_is_stochastic_of_rsi(frame):
    c = frame["close"].to_numpy("float64")
    r = talib.RSI(c, 14)
    valid = r[~np.isnan(r)]
    k, d = talib.STOCH(valid, valid, valid, fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    out = compute("stochrsi", frame)
    pad = len(c) - len(valid)
    first = pad + int(np.argmax(~np.isnan(d)))
    _eq(out["k"], np.concatenate([np.full(pad, np.nan), k]), skip=first, atol=1e-7)
    _eq(out["d"], np.concatenate([np.full(pad, np.nan), d]), skip=first, atol=1e-7)


def test_bollinger(frame):
    out = compute("bbands", frame, {"length": 20, "mult": 2.0})
    up, mid, lo = talib.BBANDS(frame["close"].to_numpy("float64"), 20, 2.0, 2.0, 0)
    _eq(out["upper"], up, rtol=1e-8)
    _eq(out["middle"], mid)
    _eq(out["lower"], lo, rtol=1e-8)


def test_atr(frame):
    h, l, c, _ = _cols(frame)
    _eq(compute("atr", frame, {"length": 14})["atr"], talib.ATR(h, l, c, 14))


def test_adx_dmi_converges_to_talib(frame):
    h, l, c, _ = _cols(frame)
    out = compute("adx", frame, {"length": 14})
    # Different first-bar seeding of the Wilder sums; the difference decays by (13/14) per bar.
    skip = 400
    np.testing.assert_allclose(out["plus_di"][skip:], talib.PLUS_DI(h, l, c, 14)[skip:], rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(out["minus_di"][skip:], talib.MINUS_DI(h, l, c, 14)[skip:], rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(out["adx"][skip:], talib.ADX(h, l, c, 14)[skip:], rtol=1e-6, atol=1e-6)


def test_cci(frame):
    h, l, c, _ = _cols(frame)
    _eq(compute("cci", frame, {"length": 20})["cci"], talib.CCI(h, l, c, 20), rtol=1e-7, atol=1e-6)


def test_mfi(frame):
    h, l, c, v = _cols(frame)
    _eq(compute("mfi", frame, {"length": 14})["mfi"], talib.MFI(h, l, c, v, 14), rtol=1e-8, atol=1e-8)


def test_roc_and_williams(frame):
    h, l, c, _ = _cols(frame)
    _eq(compute("roc", frame, {"length": 10})["roc"], talib.ROC(c, 10))
    _eq(compute("willr", frame, {"length": 14})["willr"], talib.WILLR(h, l, c, 14))


def test_obv_and_ad(frame):
    h, l, c, v = _cols(frame)
    _eq(compute("obv", frame)["obv"], talib.OBV(c, v), rtol=1e-12, atol=1e-3)
    _eq(compute("ad", frame)["ad"], talib.AD(h, l, c, v), rtol=1e-9, atol=1e-3)


def test_parabolic_sar(frame):
    h, l, _, _ = _cols(frame)
    _eq(compute("psar", frame, {"step": 0.02, "max_step": 0.2})["psar"], talib.SAR(h, l, 0.02, 0.2))


def test_donchian_and_volume_sma(frame):
    h, l, _, v = _cols(frame)
    out = compute("donchian", frame, {"length": 20})
    _eq(out["upper"], talib.MAX(h, 20))
    _eq(out["lower"], talib.MIN(l, 20))
    _eq(compute("volume_sma", frame, {"length": 50})["volume_sma"], talib.SMA(v, 50), rtol=1e-9, atol=1e-6)
