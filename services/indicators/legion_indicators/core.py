"""Indicator math.

Every function takes float64 NumPy arrays and returns arrays of the same length with
NaN where the value is not yet defined (warm-up). Nothing here reads a bar later than
the one being computed: output[i] depends only on input[0..i].

Seeding conventions follow the widely documented originals (Wilder for RSI/ATR/ADX,
SMA-seeded EMA) so results can be checked against independent references; see
tests/python/test_indicators_golden.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Array = np.ndarray


def _f(a: Array) -> Array:
    return np.asarray(a, dtype="float64")


def _nan(n: int) -> Array:
    return np.full(n, np.nan)


def _first_valid(a: Array) -> int:
    """Index of the first non-NaN value, or len(a) if there is none."""
    ok = ~np.isnan(a)
    return int(np.argmax(ok)) if ok.any() else len(a)


# --------------------------------------------------------------------------- averages


def sma(x: Array, length: int) -> Array:
    return pd.Series(_f(x)).rolling(length, min_periods=length).mean().to_numpy()


def ema(x: Array, length: int) -> Array:
    """EMA with alpha = 2/(length+1), seeded with the SMA of the first `length` values."""
    x = _f(x)
    out = _nan(len(x))
    start = _first_valid(x)
    seed_at = start + length - 1
    if seed_at >= len(x):
        return out
    alpha = 2.0 / (length + 1.0)
    prev = x[start : seed_at + 1].mean()
    out[seed_at] = prev
    for i in range(seed_at + 1, len(x)):
        prev = alpha * x[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def rma(x: Array, length: int) -> Array:
    """Wilder's moving average (alpha = 1/length), seeded with the SMA of the first `length` values."""
    x = _f(x)
    out = _nan(len(x))
    start = _first_valid(x)
    seed_at = start + length - 1
    if seed_at >= len(x):
        return out
    prev = x[start : seed_at + 1].mean()
    out[seed_at] = prev
    for i in range(seed_at + 1, len(x)):
        prev = (prev * (length - 1) + x[i]) / length
        out[i] = prev
    return out


def wma(x: Array, length: int) -> Array:
    """Linearly weighted moving average; the newest bar has weight `length`."""
    w = np.arange(1, length + 1, dtype="float64")
    return (
        pd.Series(_f(x))
        .rolling(length, min_periods=length)
        .apply(lambda v: float(np.dot(v, w) / w.sum()), raw=True)
        .to_numpy()
    )


def vwma(close: Array, volume: Array, length: int) -> Array:
    c, v = pd.Series(_f(close)), pd.Series(_f(volume))
    num = (c * v).rolling(length, min_periods=length).sum()
    den = v.rolling(length, min_periods=length).sum()
    return (num / den.where(den != 0)).to_numpy()


# --------------------------------------------------------------------------- momentum


def rsi(close: Array, length: int = 14) -> Array:
    """Wilder RSI. First value at index `length`."""
    c = _f(close)
    n = len(c)
    out = _nan(n)
    if n <= length:
        return out
    delta = np.diff(c)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:length].mean()
    avg_loss = loss[:length].mean()

    def value(g: float, l: float) -> float:
        if g + l == 0:
            return 0.0
        return 100.0 * g / (g + l)

    out[length] = value(avg_gain, avg_loss)
    for i in range(length + 1, n):
        avg_gain = (avg_gain * (length - 1) + gain[i - 1]) / length
        avg_loss = (avg_loss * (length - 1) + loss[i - 1]) / length
        out[i] = value(avg_gain, avg_loss)
    return out


def macd(close: Array, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Array, Array, Array]:
    """MACD line, signal line, histogram.

    Both EMAs start at index slow-1 (the fast EMA is seeded with the SMA of the `fast`
    closes ending there) so the line is defined from the first bar where both exist.
    """
    c = _f(close)
    n = len(c)
    line = _nan(n)
    if n < slow:
        return line, _nan(n), _nan(n)
    slow_ema = ema(c, slow)
    fast_ema = _nan(n)
    a = 2.0 / (fast + 1.0)
    prev = c[slow - fast : slow].mean()
    fast_ema[slow - 1] = prev
    for i in range(slow, n):
        prev = a * c[i] + (1.0 - a) * prev
        fast_ema[i] = prev
    line = fast_ema - slow_ema
    sig = ema(line, signal)
    return line, sig, line - sig


def roc(close: Array, length: int = 10) -> Array:
    c = _f(close)
    out = _nan(len(c))
    if len(c) > length:
        prev = c[:-length]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[length:] = np.where(prev != 0, (c[length:] / prev - 1.0) * 100.0, np.nan)
    return out


def stochastic(
    high: Array, low: Array, close: Array, k_length: int = 14, k_smooth: int = 3, d_smooth: int = 3
) -> tuple[Array, Array]:
    """Slow stochastic: %K = SMA(raw %K, k_smooth), %D = SMA(%K, d_smooth)."""
    h, l, c = pd.Series(_f(high)), pd.Series(_f(low)), pd.Series(_f(close))
    hh = h.rolling(k_length, min_periods=k_length).max()
    ll = l.rolling(k_length, min_periods=k_length).min()
    rng = hh - ll
    raw = (100.0 * (c - ll) / rng.where(rng != 0)).where(rng != 0, 0.0).where(hh.notna())
    k = raw.rolling(k_smooth, min_periods=k_smooth).mean()
    d = k.rolling(d_smooth, min_periods=d_smooth).mean()
    return k.to_numpy(), d.to_numpy()


def stoch_rsi(
    close: Array, rsi_length: int = 14, stoch_length: int = 14, k_smooth: int = 3, d_smooth: int = 3
) -> tuple[Array, Array]:
    r = rsi(close, rsi_length)
    return stochastic(r, r, r, stoch_length, k_smooth, d_smooth)


def williams_r(high: Array, low: Array, close: Array, length: int = 14) -> Array:
    h, l, c = pd.Series(_f(high)), pd.Series(_f(low)), pd.Series(_f(close))
    hh = h.rolling(length, min_periods=length).max()
    ll = l.rolling(length, min_periods=length).min()
    rng = hh - ll
    return (-100.0 * (hh - c) / rng.where(rng != 0)).where(rng != 0, 0.0).where(hh.notna()).to_numpy()


def cci(high: Array, low: Array, close: Array, length: int = 20) -> Array:
    tp = pd.Series((_f(high) + _f(low) + _f(close)) / 3.0)
    mean = tp.rolling(length, min_periods=length).mean()
    mad = tp.rolling(length, min_periods=length).apply(lambda v: float(np.abs(v - v.mean()).mean()), raw=True)
    return ((tp - mean) / (0.015 * mad.where(mad != 0))).where(mad != 0, 0.0).where(mean.notna()).to_numpy()


def mfi(high: Array, low: Array, close: Array, volume: Array, length: int = 14) -> Array:
    tp = (_f(high) + _f(low) + _f(close)) / 3.0
    n = len(tp)
    out = _nan(n)
    if n <= length:
        return out
    flow = tp * _f(volume)
    change = np.diff(tp)
    # An unchanged typical price contributes to neither side. Compare with a relative tolerance so that
    # two mathematically equal prices that differ by a floating-point ulp are still treated as unchanged.
    eps = 1e-12 * np.abs(tp[1:])
    pos = pd.Series(np.where(change > eps, flow[1:], 0.0)).rolling(length).sum().to_numpy()
    neg = pd.Series(np.where(change < -eps, flow[1:], 0.0)).rolling(length).sum().to_numpy()
    total = pos + neg
    with np.errstate(divide="ignore", invalid="ignore"):
        out[1:] = np.where(total > 0, 100.0 * pos / total, np.where(np.isnan(total), np.nan, 0.0))
    return out


# ------------------------------------------------------------------------- volatility


def true_range(high: Array, low: Array, close: Array) -> Array:
    """True range; NaN at index 0 because there is no prior close."""
    h, l, c = _f(high), _f(low), _f(close)
    tr = _nan(len(c))
    if len(c) > 1:
        pc = c[:-1]
        tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    return tr


def atr(high: Array, low: Array, close: Array, length: int = 14) -> Array:
    """Wilder ATR. First value at index `length`."""
    return rma(true_range(high, low, close), length)


def bollinger(close: Array, length: int = 20, mult: float = 2.0) -> tuple[Array, Array, Array]:
    """Middle = SMA, bands = middle ± mult × population standard deviation."""
    s = pd.Series(_f(close))
    mid = s.rolling(length, min_periods=length).mean()
    sd = s.rolling(length, min_periods=length).std(ddof=0)
    return (mid + mult * sd).to_numpy(), mid.to_numpy(), (mid - mult * sd).to_numpy()


def keltner(
    high: Array, low: Array, close: Array, length: int = 20, atr_length: int = 10, mult: float = 2.0
) -> tuple[Array, Array, Array]:
    """Middle = EMA(close), bands = middle ± mult × ATR."""
    mid = ema(close, length)
    a = atr(high, low, close, atr_length)
    return mid + mult * a, mid, mid - mult * a


def donchian(high: Array, low: Array, length: int = 20) -> tuple[Array, Array, Array]:
    """Highest high / lowest low over `length` bars INCLUDING the current bar."""
    up = pd.Series(_f(high)).rolling(length, min_periods=length).max().to_numpy()
    lo = pd.Series(_f(low)).rolling(length, min_periods=length).min().to_numpy()
    return up, (up + lo) / 2.0, lo


def historical_volatility(close: Array, length: int = 20, periods_per_year: int = 252) -> Array:
    """Annualised sample standard deviation of log returns, in percent."""
    c = _f(close)
    out = _nan(len(c))
    if len(c) < 2:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.log(c[1:] / c[:-1])
    sd = pd.Series(lr).rolling(length, min_periods=length).std(ddof=1).to_numpy()
    out[1:] = sd * np.sqrt(periods_per_year) * 100.0
    return out


# ------------------------------------------------------------------------------ trend


def adx(high: Array, low: Array, close: Array, length: int = 14) -> tuple[Array, Array, Array]:
    """Wilder ADX, +DI, -DI. DI first at index `length`, ADX at index 2*length-1."""
    h, l = _f(high), _f(low)
    n = len(h)
    if n <= length:
        return _nan(n), _nan(n), _nan(n)
    up = h[1:] - h[:-1]
    down = l[:-1] - l[1:]
    plus_dm = np.concatenate([[np.nan], np.where((up > down) & (up > 0), up, 0.0)])
    minus_dm = np.concatenate([[np.nan], np.where((down > up) & (down > 0), down, 0.0)])
    tr = rma(true_range(high, low, close), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = np.where(tr > 0, 100.0 * rma(plus_dm, length) / tr, np.where(np.isnan(tr), np.nan, 0.0))
        minus_di = np.where(tr > 0, 100.0 * rma(minus_dm, length) / tr, np.where(np.isnan(tr), np.nan, 0.0))
        total = plus_di + minus_di
        dx = np.where(total > 0, 100.0 * np.abs(plus_di - minus_di) / total, np.where(np.isnan(total), np.nan, 0.0))
    return rma(dx, length), plus_di, minus_di


def supertrend(high: Array, low: Array, close: Array, length: int = 10, mult: float = 3.0) -> tuple[Array, Array]:
    """SuperTrend line and direction (+1 up-trend, -1 down-trend).

    Basic bands = (H+L)/2 ± mult × ATR. A final band only ratchets toward price while the
    previous close stays on its side. Direction flips when the close crosses the active band.
    """
    h, l, c = _f(high), _f(low), _f(close)
    n = len(c)
    a = atr(h, l, c, length)
    line, direction = _nan(n), _nan(n)
    start = _first_valid(a)
    if start >= n:
        return line, direction
    mid = (h + l) / 2.0
    upper = mid + mult * a
    lower = mid - mult * a
    fu, fl, d = upper[start], lower[start], 1.0
    line[start], direction[start] = fl, d
    for i in range(start + 1, n):
        nu = upper[i] if (upper[i] < fu or c[i - 1] > fu) else fu
        nl = lower[i] if (lower[i] > fl or c[i - 1] < fl) else fl
        if d > 0 and c[i] < nl:
            d = -1.0
        elif d < 0 and c[i] > nu:
            d = 1.0
        fu, fl = nu, nl
        line[i] = fl if d > 0 else fu
        direction[i] = d
    return line, direction


def parabolic_sar(high: Array, low: Array, step: float = 0.02, max_step: float = 0.2) -> Array:
    """Wilder's Parabolic SAR. First value at index 1.

    Initial direction: short if the first bar-to-bar move is a down-move (-DM > 0), else long.
    The SAR may never sit inside the range of the previous or current bar.
    """
    h, l = _f(high), _f(low)
    n = len(h)
    out = _nan(n)
    if n < 2:
        return out
    up, down = h[1] - h[0], l[0] - l[1]
    is_long = not (down > up and down > 0)
    af = step
    if is_long:
        ep, sar = h[1], l[0]
    else:
        ep, sar = l[1], h[0]
    new_low, new_high = l[1], h[1]
    for i in range(1, n):
        prev_low, prev_high = new_low, new_high
        new_low, new_high = l[i], h[i]
        if is_long:
            if new_low <= sar:
                is_long = False
                sar = max(ep, prev_high, new_high)
                out[i] = sar
                af, ep = step, new_low
                sar = max(sar + af * (ep - sar), prev_high, new_high)
            else:
                out[i] = sar
                if new_high > ep:
                    ep = new_high
                    af = min(af + step, max_step)
                sar = min(sar + af * (ep - sar), prev_low, new_low)
        else:
            if new_high >= sar:
                is_long = True
                sar = min(ep, prev_low, new_low)
                out[i] = sar
                af, ep = step, new_high
                sar = min(sar + af * (ep - sar), prev_low, new_low)
            else:
                out[i] = sar
                if new_low < ep:
                    ep = new_low
                    af = min(af + step, max_step)
                sar = max(sar + af * (ep - sar), prev_high, new_high)
    return out


# ----------------------------------------------------------------------------- volume


def obv(close: Array, volume: Array) -> Array:
    """On-balance volume, starting at the first bar's volume."""
    c, v = _f(close), _f(volume)
    if len(c) == 0:
        return c
    sign = np.concatenate([[1.0], np.sign(np.diff(c))])
    return np.cumsum(sign * v)


def _money_flow_multiplier(high: Array, low: Array, close: Array) -> Array:
    h, l, c = _f(high), _f(low), _f(close)
    rng = h - l
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(rng > 0, ((c - l) - (h - c)) / rng, 0.0)


def accumulation_distribution(high: Array, low: Array, close: Array, volume: Array) -> Array:
    return np.cumsum(_money_flow_multiplier(high, low, close) * _f(volume))


def cmf(high: Array, low: Array, close: Array, volume: Array, length: int = 20) -> Array:
    """Chaikin Money Flow = sum(money-flow volume) / sum(volume) over `length` bars."""
    v = pd.Series(_f(volume))
    mfv = pd.Series(_money_flow_multiplier(high, low, close) * _f(volume))
    den = v.rolling(length, min_periods=length).sum()
    return (mfv.rolling(length, min_periods=length).sum() / den.where(den != 0)).to_numpy()


def anchored_vwap(high: Array, low: Array, close: Array, volume: Array, anchor: int = 0) -> Array:
    """Cumulative VWAP of typical price from bar index `anchor` onward. NaN before the anchor."""
    tp = (_f(high) + _f(low) + _f(close)) / 3.0
    v = _f(volume)
    n = len(tp)
    out = _nan(n)
    anchor = max(0, min(int(anchor), n))
    if anchor >= n:
        return out
    cum_v = np.cumsum(v[anchor:])
    cum_pv = np.cumsum(tp[anchor:] * v[anchor:])
    with np.errstate(divide="ignore", invalid="ignore"):
        out[anchor:] = np.where(cum_v > 0, cum_pv / cum_v, np.nan)
    return out
