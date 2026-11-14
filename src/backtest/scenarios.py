"""Market-environment tagging of calendar months (benchmark-based, deterministic)."""

from __future__ import annotations

import numpy as np
import pandas as pd

LABELS = ["bull", "bear", "sideways", "crash", "recovery", "high_vol", "low_vol"]


def tag_months(bench: pd.DataFrame) -> pd.DataFrame:
    s = pd.Series(bench["close"].to_numpy(), index=pd.to_datetime(bench["date"]))
    dd63 = s / s.rolling(63, min_periods=20).max() - 1.0
    rv = np.log(s / s.shift(1)).rolling(20).std() * np.sqrt(252)
    me = s.resample("ME").last()
    ret_m = me.pct_change()
    ret_6m = me.pct_change(6)
    min_dd = dd63.resample("ME").min()
    avg_rv = rv.resample("ME").mean()
    hi, lo = avg_rv.quantile(0.70), avg_rv.quantile(0.30)
    rows = []
    crash_flag = (min_dd <= -0.12) & (ret_m < 0)
    for m in me.index:
        tags = []
        if crash_flag.get(m, False):
            tags.append("crash")
        prev3 = crash_flag[(crash_flag.index < m) & (crash_flag.index >= m - pd.DateOffset(months=3))]
        if ret_m.get(m, 0) >= 0.05 and (prev3.any() or min_dd.get(m, 0) <= -0.10):
            tags.append("recovery")
        r6 = ret_6m.get(m, np.nan)
        if r6 == r6:
            tags.append("bull" if r6 > 0.08 else "bear" if r6 < -0.08 else "sideways")
        v = avg_rv.get(m, np.nan)
        if v == v:
            if v >= hi:
                tags.append("high_vol")
            elif v <= lo:
                tags.append("low_vol")
        rows.append({"month": m, "tags": tags, "bench_return": ret_m.get(m, np.nan)})
    return pd.DataFrame(rows).set_index("month")


def returns_by_scenario(monthly: pd.Series, tags: pd.DataFrame) -> pd.DataFrame:
    out = []
    for lab in LABELS:
        months = [m for m, t in tags["tags"].items() if lab in t]
        r = monthly[monthly.index.isin(months)]
        b = tags.loc[tags.index.isin(r.index), "bench_return"]
        out.append({
            "scenario": lab,
            "months": int(len(r)),
            "avg_strategy_return": float(r.mean()) if len(r) else np.nan,
            "pct_positive": float((r > 0).mean()) if len(r) else np.nan,
            "worst": float(r.min()) if len(r) else np.nan,
            "avg_benchmark_return": float(b.mean()) if len(b) else np.nan,
        })
    return pd.DataFrame(out)
