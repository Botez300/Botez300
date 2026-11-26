"""Deterministic PARABOLIC_NATIVE setup -> entry trigger (research configuration, NOT owner-approved).
Uses only bars[0..i] when deciding at bar i (no look-ahead).

Definitions
- Anchor A: a completed candle where all four native conditions hold on that candle (common anchor).
- Consolidation: candles A+1..A+k (k = min..max). Consolidation high H = max high, low L = min low of those candles.
- Contraction: mean true range of the consolidation candles / ATR14 measured at A  <= max_tr_ratio.
- Pivot P = H. Extension check: P / SMA20(at the decision bar) - 1 <= max_ext.
- Trigger: the next candle trades through P (buy-stop at P). Permitted entry range [P, P x (1 + max_drift)]; a candle that
  OPENS above the range is skipped (no chasing a gap). Fill = max(open, P) adverse-slipped.
- Initial stop = L (technical invalidation) unless the stop variant says otherwise; skip if (entry - stop)/entry > max_stop.
"""
from ..scanners import series as S

DEFAULT = {"min_cons": 3, "max_cons": 10, "max_tr_ratio": 0.80, "max_ext": 0.20, "max_drift": 0.01, "max_stop": 0.08, "min_rr": 2.0,
           "contraction_method": "CONS_TR_OVER_ATR14_ANCHOR"}     # unchanged default; see contraction.py for the alternatives

def anchor_ok(c, v, i):
    if i < 21: return False
    w = c[i - 19:i + 1]; m = sum(w) / 20; sd = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
    rv = v[i] / (sum(v[i - 20:i]) / 20) if sum(v[i - 20:i]) else 0
    return c[i] > m + 2 * sd and rv > 2 and 100 * c[i] / c[i - 5] - 100 > 40 and c[i] > 5

def _tr(b, j): return max(b[j].h - b[j].l, abs(b[j].h - b[j - 1].c), abs(b[j].l - b[j - 1].c))

def setup_at(b, i, p=DEFAULT):
    """Is there a valid consolidation ending at bar i (so the trigger can fire on bar i+1)? Returns dict or None."""
    c, v = [x.c for x in b[:i + 1]], [x.v for x in b[:i + 1]]
    for k in range(p["min_cons"], p["max_cons"] + 1):
        a = i - k
        if a < 21 or not anchor_ok(c, v, a): continue
        cons = b[a + 1:i + 1]; H = max(x.h for x in cons); L = min(x.l for x in cons)
        from .contraction import ratio as _ratio
        ratio = _ratio(p.get("contraction_method", "CONS_TR_OVER_ATR14_ANCHOR"), b[:i + 1], a, i)
        if ratio is None or ratio > p["max_tr_ratio"]: continue
        sma = S.sma(c, 20)
        if not sma or H / sma - 1 > p["max_ext"]: continue
        return {"anchor": a, "cons_len": k, "pivot": H, "cons_low": L, "tr_ratio": ratio, "contraction_method": p.get("contraction_method", "CONS_TR_OVER_ATR14_ANCHOR"), "ext": H / sma - 1, "atr14": S.atr_wilder(b[:i + 1], 14)}
    return None
