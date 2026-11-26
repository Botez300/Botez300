"""Independent reproduction of report-claimed indicator values (Phase 5). Reported values are claims; this module
recomputes them from authorized OHLCV and records observed vs calculated, difference, method and a PASS/FAIL status."""
import math
from ..scanners import series as S

def reproduce_parabolic(closes, vols, dates, claims, tol=None):
    """closes/vols/dates oldest->newest, last element = evaluation candle. tol: per-metric absolute tolerances."""
    tol = tol or {"close": 0.005, "upper_bb20": 0.01, "relative_volume": 0.0005, "roc5_pct": 0.0005, "rsi14": 0.01}
    mid = S.sma(closes, 20); sd = S.stdev(closes, 20, 0); up = mid + 2 * sd
    rv = vols[-1] / (sum(vols[-21:-1]) / 20); roc = 100 * closes[-1] / closes[-6] - 100
    rsi = S.rsi_wilder(closes, 14)
    calc = {"close": closes[-1], "bb_mid20": mid, "bb_pop_std20": sd, "upper_bb20": up, "relative_volume": rv, "roc5_pct": roc, "rsi14": rsi}
    rows = []
    for k, v in claims.items():
        if k not in calc or v is None: continue
        diff = calc[k] - v; ok = abs(diff) <= tol.get(k, 0.01)
        rows.append({"metric": k, "reported": v, "calculated": round(calc[k], 6), "difference": round(diff, 6), "status": "PASS" if ok else "FAIL", "tolerance": tol.get(k)})
    # common-anchor qualification across the latest 10 completed candles (native approved semantics)
    anchors = []
    for j in range(10):
        c = closes[:len(closes) - j]; v = vols[:len(vols) - j]
        if len(c) < 21: continue
        u = S.sma(c, 20) + 2 * S.stdev(c, 20, 0)
        if c[-1] > u and v[-1] / (sum(v[-21:-1]) / 20) > 2 and 100 * c[-1] / c[-6] - 100 > 40 and c[-1] > 5: anchors.append(dates[len(dates) - 1 - j])
    return calc, rows, anchors
