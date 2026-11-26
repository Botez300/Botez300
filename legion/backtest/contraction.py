"""Consolidation-contraction measures for PARABOLIC_NATIVE, kept as SEPARATELY IDENTIFIED research variants.
None is owner-approved (P4). Each module keeps its pre-existing default; nothing is silently substituted.

ATR5_OVER_ATR14              Wilder ATR(5) / Wilder ATR(14), both at the decision bar (the name used by the spec key
                             `max_atr5_over_atr14`). Includes the anchor candle whenever the anchor is within 5 bars.
CONS_TR_OVER_ATR14_ANCHOR    mean true range of the consolidation candles / ATR(14) at the anchor  (backtester default)
CONS_TR_OVER_ATR14_CURRENT   mean true range of the consolidation candles / ATR(14) at the decision bar (live gate default)"""
from ..scanners import series as S

METHODS = ("ATR5_OVER_ATR14", "CONS_TR_OVER_ATR14_ANCHOR", "CONS_TR_OVER_ATR14_CURRENT")

def _tr(b, j): return max(b[j].h - b[j].l, abs(b[j].h - b[j - 1].c), abs(b[j].l - b[j - 1].c))

def ratio(method, bars, anchor, i):
    """bars: all completed bars; anchor: index of anchor candle; i: decision bar (last consolidation candle)."""
    if method not in METHODS: raise ValueError(f"unknown contraction method {method}")
    if method == "ATR5_OVER_ATR14":
        a5, a14 = S.atr_wilder(bars[:i + 1], 5), S.atr_wilder(bars[:i + 1], 14)
        return a5 / a14 if a5 and a14 else None
    k = i - anchor
    if k < 1: return None
    mean_tr = sum(_tr(bars, j) for j in range(anchor + 1, i + 1)) / k
    den = S.atr_wilder(bars[:anchor + 1], 14) if method == "CONS_TR_OVER_ATR14_ANCHOR" else S.atr_wilder(bars[:i + 1], 14)
    return mean_tr / den if den else None

def compare(bars, anchor, i):
    return {m: ratio(m, bars, anchor, i) for m in METHODS}
