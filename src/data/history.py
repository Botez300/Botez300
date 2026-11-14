"""Validated daily OHLCV history (CSV) and completed-candle resampling.

Two series are stored per symbol:
  data/history/adjusted/<SYM>.csv  split-adjusted (indicators, continuity)
  data/history/raw/<SYM>.csv       unadjusted (what actually traded; collateral sizing)
Split events are derived from the ratio between the two series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT

HISTORY_DIR = ROOT / "data" / "history"
COLUMNS = ["date", "open", "high", "low", "close", "volume"]


class DataValidationError(ValueError):
    pass


def validate_bars(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df.empty:
        raise DataValidationError(f"{symbol}: no bars")
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise DataValidationError(f"{symbol}: missing columns {missing}")
    df = df.sort_values("date").reset_index(drop=True)
    if df["date"].duplicated().any():
        raise DataValidationError(f"{symbol}: duplicate dates")
    px = df[["open", "high", "low", "close"]]
    if (px <= 0).any().any() or px.isna().any().any():
        raise DataValidationError(f"{symbol}: non-positive or missing prices")
    if (df["high"] + 1e-9 < df[["open", "close", "low"]].max(axis=1)).any():
        raise DataValidationError(f"{symbol}: high below open/close/low")
    if (df["low"] - 1e-9 > df[["open", "close", "high"]].min(axis=1)).any():
        raise DataValidationError(f"{symbol}: low above open/close/high")
    return df


def load_bars(symbol: str, kind: str = "adjusted", base: Path | None = None) -> pd.DataFrame:
    path = (base or HISTORY_DIR) / kind / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"history missing: {path}")
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.date
    return validate_bars(df, symbol)


def completed_bars(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Only bars whose session finished strictly before ``as_of`` (no partial candle)."""
    return df[df["date"] < as_of].reset_index(drop=True)


def _resample(df: pd.DataFrame, rule: str, as_of: date) -> pd.DataFrame:
    s = df.copy()
    s.index = pd.to_datetime(s["date"])
    agg = s.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "date": "last"}
    ).dropna(subset=["close"])
    # A period is complete only when its calendar end is before as_of.
    period_end = agg.index.date
    agg = agg[[pe < as_of for pe in period_end]]
    return agg.reset_index(drop=True)


def weekly_completed(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Completed weekly candles (weeks ending Friday, labelled by last trading day)."""
    # Week ending Friday: calendar end = Friday date; complete when Friday < as_of
    # unless Friday was a holiday, in which case last trading day is earlier and
    # the period end (Friday) is still the completion test.
    return _resample(df, "W-FRI", as_of)


def monthly_completed(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    return _resample(df, "ME", as_of)


@dataclass(frozen=True)
class SplitEvent:
    symbol: str
    effective_date: date
    price_factor: float  # new_raw_price = old_raw_price * price_factor (reverse split > 1)


_SPLIT_RATIOS = np.array(
    [2, 3, 4, 5, 8, 10, 15, 20, 25, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 8, 1 / 10, 1 / 15, 1 / 20, 1 / 25]
)


def _raw_adj_steps(raw: pd.DataFrame, adjusted: pd.DataFrame, tol: float) -> tuple[pd.DataFrame, list[int]]:
    m = raw[["date", "close"]].merge(adjusted[["date", "close"]], on="date", suffixes=("_raw", "_adj"))
    ratio = (m["close_raw"] / m["close_adj"]).to_numpy()
    steps = [i for i in range(1, len(ratio)) if abs(ratio[i] / ratio[i - 1] - 1.0) > tol]
    m["ratio"] = ratio
    return m, steps


def find_adjustment_glitches(raw: pd.DataFrame, adjusted: pd.DataFrame, tol: float = 0.03) -> list[date]:
    """Single bars whose raw/adjusted ratio jumps and immediately reverts (bad data, not a split)."""
    m, steps = _raw_adj_steps(raw, adjusted, tol)
    bad: list[date] = []
    r = m["ratio"].to_numpy()
    for i in steps:
        if i + 1 < len(r) and abs(r[i + 1] / r[i - 1] - 1.0) <= tol:
            bad.append(m["date"].iloc[i])
    return bad


def detect_splits(raw: pd.DataFrame, adjusted: pd.DataFrame, symbol: str, tol: float = 0.03) -> list[SplitEvent]:
    """Derive split events from persistent step changes in the raw/adjusted close ratio."""
    m, steps = _raw_adj_steps(raw, adjusted, tol)
    glitches = set(find_adjustment_glitches(raw, adjusted, tol))
    r = m["ratio"].to_numpy()
    events: list[SplitEvent] = []
    for i in steps:
        d = m["date"].iloc[i]
        if d in glitches or m["date"].iloc[i - 1] in glitches:
            continue
        step = r[i] / r[i - 1]
        snapped = float(_SPLIT_RATIOS[np.argmin(np.abs(np.log(_SPLIT_RATIOS / step)))])
        events.append(SplitEvent(symbol, d, snapped))
    return events


def repair_adjusted_glitches(raw: pd.DataFrame, adjusted: pd.DataFrame) -> tuple[pd.DataFrame, list[date]]:
    """Rebuild glitch bars of the adjusted series from raw × the neighbouring ratio."""
    bad = find_adjustment_glitches(raw, adjusted)
    if not bad:
        return adjusted, []
    adj = adjusted.copy().set_index("date")
    rw = raw.set_index("date")
    dates = list(adj.index)
    for d in bad:
        prev = dates[dates.index(d) - 1]
        factor = adj.loc[prev, "close"] / rw.loc[prev, "close"]
        for c in ("open", "high", "low", "close"):
            adj.loc[d, c] = rw.loc[d, c] * factor
    return adj.reset_index(), bad


def realized_vol(close: pd.Series, window: int) -> pd.Series:
    lr = np.log(close / close.shift(1))
    return lr.rolling(window).std() * np.sqrt(252)
