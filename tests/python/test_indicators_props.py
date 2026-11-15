"""Indicators without a TA-Lib counterpart are checked against calculations written out from the definition,
and every indicator is checked for lookahead."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from legion_indicators import REGISTRY, IndicatorError, catalog, compute


@pytest.fixture(scope="module")
def frame(demo) -> pd.DataFrame:
    return demo.get_bars("QBIT").frame.reset_index(drop=True).iloc[-600:].reset_index(drop=True)


def test_catalog_is_complete_and_consistent(frame):
    assert len(catalog()) >= 15
    for spec in REGISTRY.values():
        out = compute(spec.id, frame)
        assert list(out) == [o.name for o in spec.outputs], spec.id
        for name, values in out.items():
            assert len(values) == len(frame), f"{spec.id}.{name}"
            assert not np.isinf(values).any(), f"{spec.id}.{name}"
            assert not np.isnan(values[-1]), f"{spec.id}.{name} has no value on the last bar"


@pytest.mark.parametrize("indicator", sorted(REGISTRY))
def test_no_lookahead(frame, indicator):
    """Values up to bar t must not change when later bars are appended."""
    full = compute(indicator, frame)
    cut = 450
    partial = compute(indicator, frame.iloc[:cut])
    for name in full:
        np.testing.assert_allclose(partial[name], full[name][:cut], rtol=1e-10, atol=1e-10, equal_nan=True,
                                   err_msg=f"{indicator}.{name} depends on future bars")


def test_vwma(frame):
    c, v = frame["close"].to_numpy(), frame["volume"].to_numpy()
    out = compute("vwma", frame, {"length": 10})["vwma"]
    i = 300
    assert out[i] == pytest.approx((c[i - 9 : i + 1] * v[i - 9 : i + 1]).sum() / v[i - 9 : i + 1].sum())
    assert np.isnan(out[:9]).all() and not np.isnan(out[9])


def test_keltner_is_ema_plus_minus_atr(frame):
    k = compute("keltner", frame, {"length": 20, "atr_length": 10, "mult": 1.5})
    ema = compute("ema", frame, {"length": 20})["ema"]
    atr = compute("atr", frame, {"length": 10})["atr"]
    np.testing.assert_allclose(k["middle"], ema, equal_nan=True)
    ok = ~np.isnan(ema)  # the bands start when both the EMA(20) and the ATR(10) exist
    assert np.isnan(k["upper"][~ok]).all()
    np.testing.assert_allclose((k["upper"] - k["middle"])[ok], 1.5 * atr[ok])
    np.testing.assert_allclose((k["middle"] - k["lower"])[ok], 1.5 * atr[ok])


def test_cmf(frame):
    h, l, c, v = (frame[x].to_numpy() for x in ("high", "low", "close", "volume"))
    out = compute("cmf", frame, {"length": 20})["cmf"]
    i = 400
    s = slice(i - 19, i + 1)
    mfv = ((c[s] - l[s]) - (h[s] - c[s])) / (h[s] - l[s]) * v[s]
    assert out[i] == pytest.approx(mfv.sum() / v[s].sum())
    assert np.nanmin(out) >= -1 and np.nanmax(out) <= 1


def test_historical_volatility(frame):
    c = frame["close"].to_numpy()
    out = compute("hv", frame, {"length": 20, "periods_per_year": 252})["hv"]
    i = 250
    lr = np.log(c[i - 19 : i + 1] / c[i - 20 : i])
    assert out[i] == pytest.approx(lr.std(ddof=1) * np.sqrt(252) * 100)


def test_anchored_vwap(frame):
    h, l, c, v = (frame[x].to_numpy() for x in ("high", "low", "close", "volume"))
    out = compute("avwap", frame, {"anchor": 100})["avwap"]
    tp = (h + l + c) / 3
    assert np.isnan(out[:100]).all()
    assert out[100] == pytest.approx(tp[100])
    assert out[350] == pytest.approx((tp[100:351] * v[100:351]).sum() / v[100:351].sum())


def test_supertrend_invariants(frame):
    out = compute("supertrend", frame, {"length": 10, "mult": 3.0})
    st, d, c = out["supertrend"], out["direction"], frame["close"].to_numpy()
    ok = ~np.isnan(st)
    assert set(np.unique(d[ok])) <= {-1.0, 1.0}
    assert (c[ok & (d > 0)] >= st[ok & (d > 0)]).all()  # up-trend: line is a floor under the close
    assert (c[ok & (d < 0)] <= st[ok & (d < 0)]).all()  # down-trend: line is a ceiling
    idx = np.flatnonzero(ok)
    same_up = (d[idx[1:]] > 0) & (d[idx[:-1]] > 0)
    assert (np.diff(st[idx])[same_up] >= -1e-9).all()  # the floor never falls within an up-trend
    assert (np.abs(np.diff(d[idx])) > 0).sum() >= 2  # it does flip on this series


def test_oscillator_bounds(frame):
    for ind, key, lo, hi in (("rsi", "rsi", 0, 100), ("mfi", "mfi", 0, 100), ("stoch", "k", 0, 100),
                             ("stochrsi", "k", 0, 100), ("willr", "willr", -100, 0), ("adx", "adx", 0, 100)):
        v = compute(ind, frame)[key]
        assert np.nanmin(v) >= lo - 1e-9 and np.nanmax(v) <= hi + 1e-9, ind


def test_constant_series_does_not_divide_by_zero():
    flat = pd.DataFrame({k: np.full(120, 10.0) for k in ("open", "high", "low", "close")} | {"volume": np.full(120, 0.0)})
    for spec in REGISTRY.values():
        for values in compute(spec.id, flat).values():
            assert not np.isinf(values).any(), spec.id


@pytest.mark.parametrize("indicator,params,message", [
    ("nope", {}, "unknown indicator"),
    ("sma", {"length": 0}, "between"),
    ("sma", {"length": 2.5}, "integer"),
    ("sma", {"length": "20"}, "number"),
    ("sma", {"period": 20}, "unknown parameter"),
    ("sma", {"source": "vwap"}, "must be one of"),
    ("macd", {"fast": 26, "slow": 12}, "fast must be less"),
])
def test_parameter_validation(frame, indicator, params, message):
    with pytest.raises(IndicatorError, match=message):
        compute(indicator, frame, params)
