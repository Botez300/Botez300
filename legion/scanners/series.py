"""Completed-candle series math. Bars are oldest->newest; index -1 is the evaluation (latest COMPLETED) bar.
Range(n, o): the n bars ending o bars before the evaluation bar (o=0 includes the evaluation bar). This is the
build's documented interpretation of the owner's wording; exact platform semantics are PENDING confirmation."""
import math, statistics
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from .. import calendar as cal

def completed(bars, interval, now):
    """Drop any bar whose period has not closed at `now` (America/New_York session rules)."""
    n = now.astimezone(cal.NY); out = []
    for b in bars:
        d = b.ts.date()                                  # Robinhood labels bars at 00:00Z of the session date
        if interval == "day": end = datetime.combine(d, cal.close_time(d) if cal.is_trading_day(d) else time(16), cal.NY)
        elif interval == "week": end = datetime.combine(d + timedelta(days=4), time(16), cal.NY)
        elif interval == "month": end = datetime.combine(date(d.year, d.month, monthrange(d.year, d.month)[1]), time(16), cal.NY)
        else: raise ValueError(interval)
        if n >= end: out.append(b)
    return out

def shift(xs, k): return xs[: len(xs) - k] if k else xs
def rng_high(bars, n, o=0):
    w = bars[len(bars) - o - n: len(bars) - o] if len(bars) >= n + o else None
    return max(b.h for b in w) if w else None
def rng_low(bars, n, o=0):
    w = bars[len(bars) - o - n: len(bars) - o] if len(bars) >= n + o else None
    return min(b.l for b in w) if w else None
def sma(vals, n, o=0):
    if len(vals) < n + o: return None
    w = vals[len(vals) - o - n: len(vals) - o]; return sum(w) / n
def ema(vals, n):
    if len(vals) < n: return None
    k, e = 2 / (n + 1), sum(vals[:n]) / n
    for v in vals[n:]: e = v * k + e * (1 - k)
    return e
def stdev(vals, n, ddof):
    if len(vals) < n: return None
    w = vals[-n:]; m = sum(w) / n; return math.sqrt(sum((x - m) ** 2 for x in w) / (n - ddof))
def bb_upper(closes, n, k, ddof):
    s = stdev(closes, n, ddof); return None if s is None else sum(closes[-n:]) / n + k * s
def roc(closes, n):
    return None if len(closes) <= n or closes[-1 - n] == 0 else 100.0 * (closes[-1] / closes[-1 - n] - 1)
def relvol(vols, n, o=1):
    """Current bar volume / SMA(n) of volume ending o bars back (o=1 => baseline excludes current bar). PENDING."""
    base = sma(vols, n, o); return None if not base else vols[-1] / base
def rsi_wilder(closes, n=14):
    if len(closes) <= n: return None
    g = [max(0, b - a) for a, b in zip(closes, closes[1:])]; l = [max(0, a - b) for a, b in zip(closes, closes[1:])]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for x, y in zip(g[n:], l[n:]): ag, al = (ag * (n - 1) + x) / n, (al * (n - 1) + y) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
def atr_wilder(bars, n=14):
    if len(bars) <= n: return None
    tr = [max(b.h - b.l, abs(b.h - p.c), abs(b.l - p.c)) for p, b in zip(bars, bars[1:])]
    a = sum(tr[:n]) / n
    for t in tr[n:]: a = (a * (n - 1) + t) / n
    return a
def median_dollar_volume(bars, n=20):
    return statistics.median(b.c * b.v for b in bars[-n:]) if len(bars) >= n else None
