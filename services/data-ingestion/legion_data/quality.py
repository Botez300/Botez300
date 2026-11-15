"""Data-quality checks. Warnings are short machine-readable codes: `code:detail`.

Codes prefixed `error:` mean the bars must not be treated as verified.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from . import calendar


def normalize(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Sort ascending and drop duplicate timestamps (keeping the last), reporting what was fixed."""
    warnings: list[str] = []
    if not frame.index.is_monotonic_increasing:
        warnings.append("unsorted_bars:sorted")
        frame = frame.sort_index(kind="stable")
    dupes = int(frame.index.duplicated(keep="last").sum())
    if dupes:
        warnings.append(f"duplicate_bars:{dupes}")
        frame = frame[~frame.index.duplicated(keep="last")]
    return frame, warnings


def check_daily(frame: pd.DataFrame, *, now: datetime | None = None, expect_volume: bool = True) -> list[str]:
    """Validate normalized daily bars (index = session date at 00:00 UTC)."""
    if frame.empty:
        return ["error:no_bars"]
    w: list[str] = []
    o, h, l, c, v = (frame[k].to_numpy("float64") for k in ("open", "high", "low", "close", "volume"))

    if np.isnan(np.column_stack([o, h, l, c])).any():
        w.append(f"error:missing_prices:{int(np.isnan(np.column_stack([o, h, l, c])).any(axis=1).sum())}")
    bad = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)
    if bad.any():
        w.append(f"error:invalid_ohlc:{int(bad.sum())}")
    if (np.column_stack([o, h, l, c]) <= 0).any():
        w.append("error:non_positive_price")
    if (v < 0).any():
        w.append("error:negative_volume")
    if expect_volume and (v == 0).any():
        w.append(f"zero_volume:{int((v == 0).sum())}")

    days: list[date] = list(frame.index.date)
    off = [d for d in days if d.weekday() >= 5]
    if off:
        w.append(f"weekend_bars:{len(off)}")  # usually a timezone conversion error
    expected = set(calendar.sessions(days[0], days[-1]))
    missing = sorted(expected - set(days))
    if missing:
        w.append(f"missing_sessions:{len(missing)}:first={missing[0].isoformat()}")

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = c[1:] / c[:-1]
    jumps = int(((ratio > 1.8) | (ratio < 0.56)).sum())
    if jumps:
        w.append(f"large_gap:{jumps}")  # possible unadjusted split or bad print

    if now is not None:
        expected_last = calendar.last_completed_session(now)
        if days[-1] < expected_last:
            w.append(f"stale:last={days[-1].isoformat()}:expected={expected_last.isoformat()}")
    return w
