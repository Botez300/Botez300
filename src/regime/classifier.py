"""Bullish / bearish / neutral market-regime classifier.

``regime_frame`` computes, for every completed daily candle, the regime a
trader would have known at that day's close. The live classifier (``classify``)
reads the row of the last completed candle before the as-of date, so live
scans and backtests share exactly one implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from src.config import Pair
from src.regime.indicators import (
    period_rsi_on_daily_index,
    realized_vol,
    rsi_wilder,
    sma,
    sma200_crosses,
)


class Regime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeResult:
    pair: str
    regime: Regime
    trade_symbol: str | None
    bar_date: date | None
    strength: float
    checks: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def _etf_trend(close: pd.Series, n: int, slope_days: int) -> pd.Series:
    m = sma(close, n)
    return (close > m) & (m > m.shift(slope_days))


def regime_frame(pair: Pair, bars: dict[str, pd.DataFrame], rcfg: dict[str, Any]) -> pd.DataFrame:
    """Vectorised regime per completed daily bar. ``bars`` are split-adjusted."""
    b = bars[pair.benchmark][["date", "close"]].rename(columns={"close": "bench"})
    u = bars[pair.bull][["date", "close"]].rename(columns={"close": "bull"})
    d = bars[pair.bear][["date", "close"]].rename(columns={"close": "bear"})
    df = b.merge(u, on="date", how="inner").merge(d, on="date", how="inner").reset_index(drop=True)

    n_fast, n_slow, n_rsi, thr = rcfg["sma_fast"], rcfg["sma_slow"], rcfg["rsi_period"], rcfg["rsi_threshold"]
    df["sma_fast"] = sma(df["bench"], n_fast)
    df["sma_slow"] = sma(df["bench"], n_slow)
    df["rsi_d"] = rsi_wilder(df["bench"], n_rsi)
    df["rsi_w"] = period_rsi_on_daily_index(df.rename(columns={"bench": "close"}), "W-FRI", n_rsi)
    df["rsi_m"] = period_rsi_on_daily_index(df.rename(columns={"bench": "close"}), "ME", n_rsi)
    df["bear_rsi_d"] = rsi_wilder(df["bear"], n_rsi)
    df["bear_rsi_w"] = period_rsi_on_daily_index(df.rename(columns={"bear": "close"}), "W-FRI", n_rsi)
    ratio = df["bull"] / df["bear"]
    df["rs_ratio_above"] = ratio > sma(ratio, rcfg["rs_sma"])
    df["rs_roc"] = ratio / ratio.shift(rcfg["rs_roc_days"]) - 1.0
    df["bull_trend"] = _etf_trend(df["bull"], rcfg["etf_trend_sma"], rcfg["etf_trend_slope_days"])
    df["bear_trend"] = _etf_trend(df["bear"], rcfg["etf_trend_sma"], rcfg["etf_trend_slope_days"])
    df["crosses"] = sma200_crosses(df["bench"], df["sma_slow"], rcfg["whipsaw_window"])
    rv = realized_vol(df["bench"], rcfg["vol_window"])
    df["rv"] = rv
    df["rv_ratio"] = rv / rv.rolling(rcfg["vol_baseline_window"], min_periods=60).median()

    required = ["sma_fast", "sma_slow", "rsi_d", "rsi_w", "bear_rsi_d", "bear_rsi_w", "rv_ratio", "crosses"]
    if rcfg.get("require_monthly_rsi"):
        required.append("rsi_m")
    complete = df[required].notna().all(axis=1)

    bull_ok = (
        (df["bench"] > df["sma_slow"])
        & (df["sma_fast"] > df["sma_slow"])
        & (df["rsi_d"] > thr)
        & (df["rsi_w"] > thr)
        & (df["rs_ratio_above"] | (df["rs_roc"] > 0))
        & df["bull_trend"]
    )
    bear_ok = (
        (df["bench"] < df["sma_slow"])
        & (df["sma_fast"] < df["sma_slow"])
        & (df["rsi_d"] < thr)
        & (df["rsi_w"] < thr)
        & df["bear_trend"]
        & (df["bear_rsi_d"] > thr)
        & (df["bear_rsi_w"] > thr)
    )
    if rcfg.get("require_monthly_rsi"):
        bull_ok &= df["rsi_m"] > thr
        bear_ok &= df["rsi_m"] < thr

    unstable = (df["crosses"] >= rcfg["whipsaw_max_crosses"]) | (df["rv_ratio"] > rcfg["vol_spike_ratio"])
    regime = np.where(~complete | unstable, "NEUTRAL", np.where(bull_ok, "BULLISH", np.where(bear_ok, "BEARISH", "NEUTRAL")))
    df["regime"] = regime
    df["complete"] = complete
    df["unstable"] = unstable

    dist = (df["bench"] / df["sma_slow"] - 1.0).abs() / 0.10
    rsi_m = (df["rsi_d"] - thr).abs() / 20.0
    df["strength"] = np.clip((np.clip(dist, 0, 1) + np.clip(rsi_m, 0, 1)) / 2.0, 0, 1)
    df.loc[df["regime"] == "NEUTRAL", "strength"] = 0.0
    return df


def classify(pair: Pair, bars: dict[str, pd.DataFrame], rcfg: dict[str, Any], as_of: date) -> RegimeResult:
    """Point-in-time classification using only candles completed before ``as_of``."""
    cut = {k: v[v["date"] < as_of].reset_index(drop=True) for k, v in bars.items()}
    try:
        f = regime_frame(pair, cut, rcfg)
    except KeyError as exc:
        return RegimeResult(pair.name, Regime.NEUTRAL, None, None, 0.0, reasons=[f"missing data: {exc}"])
    if f.empty:
        return RegimeResult(pair.name, Regime.NEUTRAL, None, None, 0.0, reasons=["no completed candles"])
    row = f.iloc[-1]
    bar_date: date = row["date"]
    reasons: list[str] = []
    regime = Regime(row["regime"])
    stale_days = (as_of - bar_date).days
    if stale_days > rcfg["max_bar_staleness_days"]:
        regime = Regime.NEUTRAL
        reasons.append(f"stale data: last completed bar {bar_date} is {stale_days} days old")
    if not row["complete"]:
        reasons.append("indicator history incomplete (not manufactured) -> NEUTRAL")
    if row["unstable"]:
        reasons.append(
            f"unstable: SMA200 crosses={row['crosses']:.0f} in window, vol ratio={row['rv_ratio']:.2f}"
        )
    thr = rcfg["rsi_threshold"]
    checks = {
        "benchmark_close": round(float(row["bench"]), 4),
        "sma50": round(float(row["sma_fast"]), 4),
        "sma200": round(float(row["sma_slow"]), 4),
        "bench_above_sma200": bool(row["bench"] > row["sma_slow"]),
        "sma50_above_sma200": bool(row["sma_fast"] > row["sma_slow"]),
        "rsi_daily": round(float(row["rsi_d"]), 2),
        "rsi_weekly": round(float(row["rsi_w"]), 2),
        "rsi_monthly": None if pd.isna(row["rsi_m"]) else round(float(row["rsi_m"]), 2),
        "bull_etf_uptrend": bool(row["bull_trend"]),
        "bear_etf_uptrend": bool(row["bear_trend"]),
        "bear_rsi_daily": round(float(row["bear_rsi_d"]), 2),
        "bear_rsi_weekly": round(float(row["bear_rsi_w"]), 2),
        "rs_bull_vs_bear_above_sma": bool(row["rs_ratio_above"]),
        "rs_roc": round(float(row["rs_roc"]), 4),
        "sma200_crosses_window": float(row["crosses"]),
        "realized_vol_20d": round(float(row["rv"]), 4),
        "vol_ratio_vs_1y_median": round(float(row["rv_ratio"]), 3),
        "rsi_threshold": thr,
    }
    if regime is Regime.NEUTRAL and not reasons:
        reasons.append("conflicting technical signals")
    trade_symbol = pair.bull if regime is Regime.BULLISH else pair.bear if regime is Regime.BEARISH else None
    strength = float(row["strength"]) if regime is not Regime.NEUTRAL else 0.0
    return RegimeResult(pair.name, regime, trade_symbol, bar_date, strength, checks, reasons)
