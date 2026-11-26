"""Live exit protections for open paper positions (research thresholds, NOT owner-approved; read from spec exit_research).
Each check returns a reason string or None. A halted symbol cannot be exited: it is flagged, not 'filled'."""
from .scanners import series as S

def check(pos, bars, quote, earnings_dates, today, t):
    """pos: {pivot, entry_i_date, direction}; bars: completed daily bars up to now; t: thresholds dict."""
    out = []
    if getattr(quote, "state", "active") not in ("active", None, ""): out.append("TRADING_HALT_FLAG_NO_EXIT_POSSIBLE")
    since = [b for b in bars if b.ts.date() >= pos["entry_date"]]
    if pos.get("pivot") and 0 < len(since) <= t.get("failed_breakout_sessions", 3) and bars[-1].c < pos["pivot"]: out.append("FAILED_BREAKOUT")
    if earnings_dates is None: out.append("EARNINGS_DATE_UNKNOWN")
    elif any(0 <= (d - today).days <= t.get("earnings_blackout_days", 7) for d in earnings_dates): out.append("EARNINGS_BLACKOUT_EXIT")
    a5, a14 = (S.atr_wilder(bars[-6:], 5) if len(bars) > 6 else None), S.atr_wilder(bars)
    if a5 and a14 and a5 / a14 > t.get("max_vol_expansion", 2.0): out.append("VOLATILITY_EXPANSION")
    bid, ask = getattr(quote, "bid", None), getattr(quote, "ask", None)
    if bid and ask and (ask - bid) / ((ask + bid) / 2) > t.get("max_spread", 0.005): out.append("LIQUIDITY_SPREAD")
    v = [b.v for b in bars]
    if len(v) >= 20 and sum(v[-5:]) / 5 < t.get("min_vol_ratio", 0.5) * sum(v[-20:]) / 20: out.append("LIQUIDITY_VOLUME_COLLAPSE")
    return out
