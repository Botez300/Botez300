"""Supporting-intelligence overlays: INFORMATIONAL ONLY, never mechanical gates. Each returns a value or an explicit
UNVERIFIED reason. Nothing here claims turnover/OBV/price appreciation is verified institutional inflow."""
from . import series as S

UNAVAILABLE = {
    "hamilton_tti_regime": "proprietary regime model; definition not supplied",
    "etf_industry_capital_flows": "no verified fund-flow source approved; price/volume/OBV are NOT flows",
    "sector_industry_leadership": "requires universe-wide sector ranking job (not implemented)",
    "squeeze_momentum": "exact platform definition not supplied",
    "luxalgo_signals": "LuxAlgo MCP failed to connect in this session; not an approved data provider for Legion",
    "short_interest_days_to_cover": "not exposed by Robinhood tools probed",
    "insider_transactions": "not exposed by Robinhood tools probed (insiderPercentOwned is a holding, not transactions)",
    "earnings_quality": "definition not supplied",
    "long_term_quality_compounders": "definition not supplied",
}
def compute(d, spy_daily=None, spy_weekly=None):
    b, w, m = d.daily or [], d.weekly or [], d.monthly or []
    cl, wc, mc = [x.c for x in b], [x.c for x in w], [x.c for x in m]
    out = {k: {"status": "UNVERIFIED", "reason": v} for k, v in UNAVAILABLE.items()}
    def put(k, v, note=""): out[k] = {"status": "UNVERIFIED", "reason": note or "insufficient history"} if v is None else {"status": "VALUE", "value": v, "note": note}
    rd, rw = S.rsi_wilder(cl), S.rsi_wilder(wc)
    put("rsi14_daily_or_weekly_le_30", None if rd is None and rw is None else bool((rd is not None and rd <= 30) or (rw is not None and rw <= 30)), "Wilder RSI14")
    put("ema_200_week", S.ema(wc, 200)); put("sma_200_month", S.sma(mc, 200))
    if b:
        i = max(range(len(b)), key=lambda k: b[k].h); seg = b[i:]; vol = sum(x.v for x in seg)
        put("ath_anchored_vwap", None if not vol else sum((x.h + x.l + x.c) / 3 * x.v for x in seg) / vol, f"anchored at {b[i].ts.date()} (highest high in supplied history)")
    if spy_daily and len(spy_daily) > 20 and len(cl) > 20:
        put("rs_vs_spy_daily_20", (cl[-1] / cl[-21]) / (spy_daily[-1].c / spy_daily[-21].c) - 1, "ratio change over 20 daily bars")
    if spy_weekly and len(spy_weekly) > 13 and len(wc) > 13:
        put("rs_vs_spy_weekly_13", (wc[-1] / wc[-14]) / (spy_weekly[-1].c / spy_weekly[-14].c) - 1, "ratio change over 13 weekly bars")
    put("pct_from_52w_high", None if len(b) < 252 else b[-1].c / max(x.h for x in b[-252:]) - 1)
    return out

def top_52w_highs(datas, n=10):
    rows = [(d.daily[-1].c / max(x.h for x in d.daily[-252:]) - 1, d.ticker) for d in datas if d.daily and len(d.daily) >= 252]
    return [t for _, t in sorted(rows, key=lambda r: (-r[0], r[1]))[:n]]
