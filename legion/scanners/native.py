"""LEGION_NATIVE scanner variants: explicitly documented, independently reproducible rules approved by the owner on
2026-11-26 (Phase 4) for paper research ONLY. They are NOT exact platform signals and must never be labeled as such.
The EXACT_PLATFORM scanners in defs.py are untouched."""
import copy
from . import series as S
from .defs import can_slim, weinstein, magic, parabolic, liquidity_gate, Data, P_WEINSTEIN
from .tri import AND, OR, PASS, FAIL, UNV, cmp, within_pct, unv, node

CLASS = "LEGION_NATIVE"

def can_slim_native(d: Data, p):
    """Approved: GAAP diluted EPS (17 quarters), M on the stock itself (close > SMA200, SMA200 > SMA200 90 sessions earlier).
    L (RP yearly) and I (dated analyst Buy ratings) are unchanged and stay UNVERIFIED without authentic data."""
    x = copy.copy(d); x.market_daily = d.daily
    t = can_slim(x, {**p, "accepted_eps_bases": ["GAAP_DILUTED"]})
    t["id"], t["detail"] = "CAN_SLIM_NATIVE", f"{CLASS}: M evaluated on the stock's own daily closes"
    return t

def _published_trend_template(d, p):
    """PROPOSED (not approved): Minervini's published trend-template criteria on daily closes. The RS-rating criterion has
    no authorized source, so it is UNVERIFIED and the group cannot pass until the owner approves an RS definition."""
    c = [b.c for b in d.daily or []]; px = c[-1] if c else None
    s50, s150, s200, s200_1m = S.sma(c, 50), S.sma(c, 150), S.sma(c, 200), S.sma(c, 200, 22)
    lo = min(b.l for b in d.daily[-252:]) if d.daily and len(d.daily) >= 252 else None
    hi = max(b.h for b in d.daily[-252:]) if d.daily and len(d.daily) >= 252 else None
    return AND("NATIVE_TREND_TEMPLATE_PROPOSED", [cmp("PX_GT_SMA150", px, ">", s150), cmp("PX_GT_SMA200", px, ">", s200), cmp("SMA150_GT_SMA200", s150, ">", s200),
        cmp("SMA200_RISING_1M", s200, ">", s200_1m), cmp("SMA50_GT_SMA150", s50, ">", s150), cmp("SMA50_GT_SMA200", s50, ">", s200), cmp("PX_GT_SMA50", px, ">", s50),
        cmp("PX_30PCT_ABOVE_52W_LOW", px, ">=", None if lo is None else 1.30 * lo), cmp("PX_WITHIN_25PCT_OF_52W_HIGH", px, ">=", None if hi is None else 0.75 * hi),
        unv("RS_RATING", "no authorized RS-rating source; native RS definition not approved")])

def minervini_native_proposed(d: Data, p):
    from .defs import minervini, P_MINERVINI
    x = copy.copy(d); x.proprietary = {k: v for k, v in d.proprietary.items() if k != P_MINERVINI}
    t = minervini(x, p)
    t["children"][1] = AND("G1_NATIVE", [_published_trend_template(d, p), cmp("MARKET_CAP_GT_2B", d.market_cap, ">", p["min_market_cap"])])
    t["status"] = AND("x", t["children"])["status"]; t["id"] = "MINERVINI_NATIVE_PROPOSED"
    return t

def _n_series(b, n=20):
    """Original Turtle N: Wilder-style smoothing of true range over n days."""
    if len(b) <= n: return None
    tr = [max(x.h - x.l, abs(x.h - p.c), abs(x.l - p.c)) for p, x in zip(b, b[1:])]
    out = [None] * n; v = sum(tr[:n]) / n; out.append(v)
    for t in tr[n:]: v = (v * (n - 1) + t) / n; out.append(v)
    return out                                          # aligned to b (index i -> N known at close of bar i)

def turtle_native(d: Data, p):
    """Separately labeled ORIGINAL historical Turtle rules (public record), NOT the platform '(yes, yes, yes, yes, 2)' tuple.
    System 1: close above prior 20-day high, skipped if the previous S1 breakout would have been a winner (exit 10-day low,
    stop 2N). System 2: close above prior 55-day high (no skip rule). Signals must EMERGE on the latest completed candle."""
    b = d.daily or []; N = _n_series(b)
    def brk(i, n): return i >= n and b[i].c > max(x.h for x in b[i - n:i])
    def emerged(n): i = len(b) - 1; return None if i < n + 1 else brk(i, n) and not brk(i - 1, n)
    def prior_s1_winner():
        i = len(b) - 2
        while i > 20 and not (brk(i, 20) and not brk(i - 1, 20)): i -= 1
        if i <= 20 or N is None or N[i] is None: return None
        entry, stop = b[i].c, b[i].c - 2 * N[i]
        for j in range(i + 1, len(b) - 1):
            if b[j].l <= stop: return False
            if b[j].c < min(x.l for x in b[max(0, j - 10):j]): return b[j].c > entry
        return None                                     # still open at evaluation => treated as not a winner
    s1, s2 = emerged(20), emerged(55)
    win = prior_s1_winner() if s1 else None
    n1 = node("S1_EMERGED_NOT_SKIPPED", UNV if s1 is None else PASS if s1 and win is not True else FAIL, f"emerged={s1} prior_winner={win}")
    n2 = node("S2_EMERGED", UNV if s2 is None else PASS if s2 else FAIL)
    t = AND("TURTLE_NATIVE", [liquidity_gate(d, p["liquidity"]), OR("TURTLE_NATIVE_SIGNAL", [n1, n2])], f"{CLASS}: historical Donchian rules")
    t["sizing"] = None if not N or N[-1] is None else {"N": N[-1], "stop_2N": b[-1].c - 2 * N[-1], "unit_risk_note": "Turtle unit = 1% equity per N; capped by the Legion risk engine (0.5%/trade)",
                                                    "exit": "S1: 10-day low; S2: 20-day low; stop 2N"}
    return t

def weinstein_native(d: Data, p):
    """Approved window semantics (common anchor within latest 3 completed weekly candles; Stage 1 offsets relative to the anchor).
    The Stage classification itself is NOT invented: it must come from imported authentic indicator evidence."""
    t = weinstein(d, {**p, "group_window": 3, "group_window_mode": "common_anchor"}); t["id"] = "WEINSTEIN_NATIVE"; return t

def magic_native(d: Data, p):
    """Approved native ROIC (LEGION_NATIVE_ROIC_V1, SEC-derived) and SEC TTM operating income; original thresholds."""
    t, ey = magic(d, {**p, "accepted_operating_income_sources": ["SEC_TTM_OPERATING_INCOME"], "accepted_roic_definitions": ["LEGION_NATIVE_ROIC_V1"]})
    t["id"] = "MAGIC_FORMULA_NATIVE"; return t, ey

def parabolic_native(d: Data, p):
    """Approved: all four conditions on a COMMON completed daily candle within the latest 10; Bollinger 20 SMA +/- 2 population
    std; relvol = candle volume / mean of the preceding 20 completed candles; ROC = 100*C/C[-5] - 100; close > $5."""
    t, diag = parabolic(d, {**p, "window": 10, "window_mode": "common_anchor", "bb_std": 2.0, "bb_ddof": 0, "min_relative_volume": 2.0, "min_roc5_pct": 40.0, "min_close": 5.0})
    t["id"] = "PARABOLIC_NATIVE"; return t, diag

NATIVE = {"CAN_SLIM_NATIVE": can_slim_native, "MINERVINI_NATIVE_PROPOSED": minervini_native_proposed, "TURTLE_NATIVE": turtle_native,
          "WEINSTEIN_NATIVE": weinstein_native, "MAGIC_FORMULA_NATIVE": lambda d, p: magic_native(d, p)[0],
          "PARABOLIC_NATIVE": lambda d, p: parabolic_native(d, p)[0]}
