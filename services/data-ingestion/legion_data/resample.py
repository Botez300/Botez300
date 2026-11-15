"""Aggregate daily bars into weekly / monthly bars without lookahead."""

from __future__ import annotations

import pandas as pd

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample(daily: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Return bars indexed by the first session of each period (the bar's open time)."""
    if timeframe == "1D" or daily.empty:
        return daily
    if timeframe not in ("1W", "1M"):
        raise ValueError(f"unsupported timeframe '{timeframe}'")
    local = daily.index.tz_localize(None)  # daily bars are stamped 00:00 UTC of their session date
    keys = local.to_period("W-FRI" if timeframe == "1W" else "M")
    out = daily.groupby(keys).agg(_AGG)
    first = pd.Series(local, index=keys).groupby(level=0).first()
    out.index = pd.DatetimeIndex(first.to_numpy(), name=daily.index.name).tz_localize("UTC")
    return out


def period_incomplete(last_daily_session, next_session, timeframe: str) -> bool:
    """True if the period containing `last_daily_session` still has sessions to come."""
    if timeframe == "1D":
        return False
    freq = "W-FRI" if timeframe == "1W" else "M"
    return pd.Period(last_daily_session, freq) == pd.Period(next_session, freq)
