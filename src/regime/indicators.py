"""Deterministic technical indicators computed from verified completed candles."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI. Returns NaN until n+1 observations exist (never manufactured)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out[avg_gain.isna() | avg_loss.isna()] = np.nan
    return out


def period_rsi_on_daily_index(daily: pd.DataFrame, rule: str, n: int) -> pd.Series:
    """RSI on completed weekly ('W-FRI') or monthly ('ME') candles, mapped to each day.

    For a daily date d, the value is the RSI of the most recent period whose
    calendar end is <= d, i.e. only fully completed candles are used.
    """
    s = daily.set_index(pd.to_datetime(daily["date"]))["close"]
    per = s.resample(rule).last().dropna()
    per_rsi = rsi_wilder(per, n)
    # per index = period end label (Friday / month end). Available from that date on.
    mapped = per_rsi.reindex(s.index.union(per_rsi.index)).ffill().reindex(s.index)
    # A label equal to day d counts as completed at d's close.
    mapped.index = daily.index
    return mapped


def sma200_crosses(close: pd.Series, sma_slow: pd.Series, window: int) -> pd.Series:
    sign = np.sign(close - sma_slow)
    flips = (sign != sign.shift(1)) & sign.notna() & sign.shift(1).notna()
    return flips.astype(float).rolling(window, min_periods=window).sum()


def realized_vol(close: pd.Series, window: int) -> pd.Series:
    lr = np.log(close / close.shift(1))
    return lr.rolling(window, min_periods=window).std() * np.sqrt(252)
