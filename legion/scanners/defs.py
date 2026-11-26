"""The six Legion mechanical scanners, implemented exactly as specified in
specs/source/legion_scanner_instructions_2026-11-26.md. Every threshold comes from specs/<ID>.json.
Proprietary platform readings are consumed ONLY from Data.proprietary (never computed or approximated here);
when absent the condition is UNVERIFIED and the AND that contains it cannot pass."""
from dataclasses import dataclass, field
from datetime import timedelta
from . import series as S
from .tri import AND, OR, PASS, FAIL, UNV, cmp, within_pct, unv, node, window_group

# Exact platform signal names (keys into Data.proprietary). Values: list aligned to the relevant completed candles (newest last).
P_MINERVINI = "D Mark Minervini Trend Template Candles (yes)|Meets All 10 Trend Template Criteria Signal"
P_TURTLE_1 = "D Turtle Trading Strategy (Long-Only) (yes, yes, yes, yes, 2)|System 1 Entry Signal"
P_TURTLE_2 = "D Turtle Trading Strategy (Long-Only) (yes, yes, yes, yes, 2)|System 2 Entry Signal"
P_WEINSTEIN = "W Weinstein Stage Analysis (30,5,sma)|Stage"
P_RP_YEARLY = "RP(yearly) for SPX500"

@dataclass
class Data:
    ticker: str; now: object
    daily: list | None = None; weekly: list | None = None; monthly: list | None = None
    spread_pct: float | None = None                 # (ask-bid)/mid from a fresh quote
    market_cap: float | None = None; fundamentals_as_of: str | None = None
    eps: list | None = None                         # newest first: [{"eps": float, "report_date": "YYYY-MM-DD"}]
    eps_basis: str | None = None                    # e.g. "GAAP_DILUTED", "ADJUSTED", "UNDOCUMENTED"
    analyst_buy_dates: list | None = None           # dates of individual verified Buy ratings; None = not available
    market_daily: list | None = None                # index bars for CAN SLIM "M"
    operating_income_ttm: float | None = None; operating_income_source: str | None = None
    enterprise_value: float | None = None
    roic_ttm: float | None = None; roic_definition: str | None = None
    proprietary: dict = field(default_factory=dict)

def _closes(b): return [x.c for x in b]
def _vols(b): return [x.v for x in b]

def liquidity_gate(d: Data, g: dict):
    if not d.daily: return unv("LIQUIDITY", "no daily bars")
    return AND("LIQUIDITY", [cmp("PRICE_GE_MIN", d.daily[-1].c, ">=", g["min_price"]),
        cmp("MEDIAN_20D_DOLLAR_VOLUME_GE_MIN", S.median_dollar_volume(d.daily, 20), ">=", g["min_median_dollar_volume_20d"]),
        cmp("SPREAD_NOT_UNTRADEABLE", d.spread_pct, "<=", g["max_spread_pct_of_mid"]) if g.get("max_spread_pct_of_mid") is not None
        else unv("SPREAD_NOT_UNTRADEABLE", "threshold for 'clearly untradeable spread' not approved")])

# ---------------------------------------------------------------- 1 CAN SLIM
def can_slim(d: Data, p: dict):
    def E(k):
        return d.eps[k]["eps"] if d.eps and len(d.eps) > k and d.eps[k].get("eps") is not None else None
    def G(k):
        if d.eps_basis not in p["accepted_eps_bases"]: return unv(f"G({k})", f"EPS basis {d.eps_basis!r} not an approved consistent basis")
        a, b = E(k), E(k + 4)
        if a is None or b is None: return unv(f"G({k})", f"E[{k}] or E[{k+4}] unavailable")
        if b <= 0: return unv(f"G({k})", f"nonpositive base E[{k+4}]={b}: cannot automatically pass")
        return cmp(f"G({k})", a, ">=", b * (1 + p["eps_growth_min"]), f"E[{k}] vs 1.25*E[{k+4}]: ")
    C = AND("C", [G(0)])
    A = AND("A", [OR("A_GROUP1", [G(k) for k in (1, 2, 3, 4)]), OR("A_GROUP2", [G(k) for k in (5, 6, 7, 8)]), OR("A_GROUP3", [G(k) for k in (9, 10, 11, 12)])])
    wk = d.weekly or []
    N = within_pct("N", d.daily[-1].c if d.daily else None, S.rng_high(wk, 52, 1), p["n_band_pct"])
    mv = _vols(d.monthly or [])
    s1 = S.sma(mv, 20, 1)
    Sx = OR("S", [cmp(f"S_SMA20_O1_GT_O{k}", s1, ">", S.sma(mv, 20, k)) for k in (2, 3, 4)])
    rp = d.proprietary.get(P_RP_YEARLY)
    L = cmp("L", rp[-1] if rp else None, ">", p["rp_yearly_min"], "RP(yearly): ") if rp else unv("L", "RP(yearly) for SPX500 not available from any approved provider")
    if d.analyst_buy_dates is None: I = unv("I", "dated individual analyst Buy ratings not available (Robinhood returns aggregate counts only)")
    else:
        cut = (d.now - timedelta(days=p["analyst_lookback_days"])).date()
        I = node("I", PASS if any(x >= cut for x in d.analyst_buy_dates) else FAIL, f"buy ratings since {cut}")
    mk = _closes(d.market_daily or [])
    if len(mk) < p["min_market_bars"]: M = unv("M", f"need >= {p['min_market_bars']} completed market bars, have {len(mk)}")
    else:
        sma_now, sma_then = S.sma(mk, 200), S.sma(mk, 200, p["sma200_lookback_sessions"])
        M = AND("M", [cmp("M_CLOSE_GT_SMA200", mk[-1], ">", sma_now), cmp("M_SMA200_RISING_90", sma_now, ">", sma_then)])
    return AND("CAN_SLIM", [liquidity_gate(d, p["liquidity"]), C, A, N, Sx, L, I, M])

# ---------------------------------------------------------------- 2 MINERVINI
def minervini(d: Data, p: dict):
    b, w = d.daily or [], d.weekly or []
    tt = d.proprietary.get(P_MINERVINI)
    g1 = AND("G1_TREND_TEMPLATE", [node("TT_SIGNAL_ACTIVE", (PASS if tt[-1] else FAIL), "provider signal") if tt else unv("TT_SIGNAL_ACTIVE", "authentic 10-criteria provider signal unavailable"),
                                   cmp("MARKET_CAP_GT_2B", d.market_cap, ">", p["min_market_cap"])])
    h = S.rng_high(b, 100, 1); h10 = S.rng_high(S.shift(b, 10), 100, 1); c = b[-1].c if b else None
    g2 = AND("G2_NEAR_BREAKOUT", [cmp("R100_1_HIGH_UNCHANGED_10", h, "==", h10), within_pct("CLOSE_WITHIN_7PCT", c, h, p["daily_band_pct"]),
            within_pct("WEEKLY_CLOSE_WITHIN_20PCT", w[-1].c if w else None, S.rng_high(w, 100, 0), p["weekly_band_pct"]), cmp("CLOSE_LE_R100_1_HIGH", c, "<=", h)])
    g3 = AND("G3_HIGHER_LOWS", [cmp(f"LOW{n}_GT_{n}_AGO", S.rng_low(b, n, 0), ">", S.rng_low(S.shift(b, n), n, 0)) for n in (10, 20, 30)])
    v = _vols(b); base = S.sma(v, 20, 1)
    g4 = OR("G4_CONTRACTING_VOLUME", [cmp(f"VSMA20_O1_LT_O{k}", base, "<", S.sma(v, 20, k)) for k in p["volume_offsets"]])
    return AND("MINERVINI_VCP_SEPA", [liquidity_gate(d, p["liquidity"]), g1, g2, g3, g4], "mechanical qualification only - NOT a confirmed breakout")

# ---------------------------------------------------------------- 3 TURTLE
def _emerged(id, seq, why):
    if not seq or len(seq) < 2: return unv(id, why)
    return node(id, PASS if (seq[-1] and not seq[-2]) else FAIL, f"latest={seq[-1]} prior={seq[-2]}")
def turtle(d: Data, p: dict):
    return AND("TURTLE", [liquidity_gate(d, p["liquidity"]), OR("TURTLE_SIGNAL", [
        _emerged("SYSTEM1_EMERGED", d.proprietary.get(P_TURTLE_1), "platform System 1 signal unavailable"),
        _emerged("SYSTEM2_EMERGED", d.proprietary.get(P_TURTLE_2), "platform System 2 signal unavailable")])])
def turtle_research(d: Data):
    """SEPARATELY LABELED historical research (classic 20/55-day Donchian breakouts). Never a qualification."""
    b = d.daily or []
    def brk(n, k=0):
        x = S.shift(b, k); return None if len(x) < n + 1 else x[-1].c > max(y.h for y in x[-1 - n:-1])
    r = {}
    for n in (20, 55):
        now_, prev = brk(n), brk(n, 1)
        r[f"donchian_{n}_breakout_emerged"] = None if now_ is None or prev is None else (now_ and not prev)
    cl = _closes(b)
    r["rsi14_daily_gt_50"] = (lambda v: None if v is None else v > 50)(S.rsi_wilder(cl))
    r["rsi14_weekly_gt_50"] = (lambda v: None if v is None else v > 50)(S.rsi_wilder(_closes(d.weekly or [])))
    r["rsi14_monthly_gt_50"] = (lambda v: None if v is None else v > 50)(S.rsi_wilder(_closes(d.monthly or [])))
    r["label"] = "RESEARCH_ONLY_DIAGNOSTIC"; return r

# ---------------------------------------------------------------- 4 WEINSTEIN
def weinstein(d: Data, p: dict):
    st, w = d.proprietary.get(P_WEINSTEIN), d.weekly or []
    v = _vols(w)
    def stage(j, k, val, id):
        if not st or len(st) < j + k + 1: return unv(id, "platform stage readings unavailable")
        return node(id, PASS if st[-1 - j - k] == val else FAIL, f"stage[{j}+{k}]={st[-1 - j - k]}")
    def emerged(j):
        if not st or len(st) < j + 2: return unv("STAGE2_EMERGED", "platform stage readings unavailable")
        return node("STAGE2_EMERGED", PASS if st[-1 - j] == 2 and st[-2 - j] != 2 else FAIL)
    def rv(j): return cmp("W_RELVOL_20_SMA_1_GT_1", S.relvol(S.shift(v, j), 20, 1), ">", p["min_relative_volume"])
    conds = [("STAGE2_EMERGED", emerged), ("STAGE1_1_AGO", lambda j: stage(j, 1, 1, "STAGE1_1_AGO")),
             ("STAGE1_2_AGO", lambda j: stage(j, 2, 1, "STAGE1_2_AGO")), ("STAGE1_3_AGO", lambda j: stage(j, 3, 1, "STAGE1_3_AGO")), ("RELVOL", rv)]
    return window_group("WEINSTEIN_STAGE_2", conds, p["group_window"], p["group_window_mode"])
def weinstein_long_base(d: Data, min_weeks=52):
    """Separate long-base board (informational, NOT a mandatory condition)."""
    st = d.proprietary.get(P_WEINSTEIN)
    if not st or st[-1] != 2: return None
    n = 0
    for s in reversed(st[:-1]):
        if s != 1: break
        n += 1
    return {"stage1_base_weeks": n, "long_base": n >= min_weeks}

# ---------------------------------------------------------------- 5 MAGIC FORMULA
def magic(d: Data, p: dict):
    ok_src = d.operating_income_source in p["accepted_operating_income_sources"]
    ev_ok = cmp("EV_POSITIVE", d.enterprise_value, ">", 0)
    ey = None if not ok_src or not d.enterprise_value or d.enterprise_value <= 0 or d.operating_income_ttm is None else d.operating_income_ttm / d.enterprise_value
    eyn = cmp("EARNINGS_YIELD_GT_010", ey, ">", p["min_earnings_yield"]) if ok_src else unv("EARNINGS_YIELD_GT_010", f"operating income source {d.operating_income_source!r} not approved")
    vol = _vols(d.daily or [])
    roic_ok = d.roic_definition in p["accepted_roic_definitions"]
    rn = cmp("ROIC_TTM_GE_015", d.roic_ttm, ">=", p["min_roic"]) if roic_ok else unv("ROIC_TTM_GE_015", f"ROIC definition {d.roic_definition!r} not approved / unavailable")
    return AND("MAGIC_FORMULA", [ev_ok, eyn, cmp("MARKET_CAP_GT_10M", d.market_cap, ">", p["min_market_cap"]),
                                 cmp("VOLUME_SMA20_GT_300K", S.sma(vol, 20) if len(vol) >= 20 else None, ">", p["min_volume_sma20"]), rn],
               "mechanical qualification only - not BUY_NOW"), ey

# ---------------------------------------------------------------- 6 PARABOLIC
def parabolic(d: Data, p: dict):
    b = d.daily or []
    def at(j):
        x = S.shift(b, j); return _closes(x), _vols(x)
    def c_bb(j):
        c, _ = at(j); return cmp("CLOSE_GT_BB_UP", c[-1] if c else None, ">", S.bb_upper(c, 20, p["bb_std"], p["bb_ddof"]) if len(c) >= 20 else None)
    def c_rv(j):
        _, v = at(j); return cmp("RELVOL_20_SMA_1_GT_2", S.relvol(v, 20, 1) if len(v) >= 21 else None, ">", p["min_relative_volume"])
    def c_roc(j):
        c, _ = at(j); return cmp("ROC5_GT_40", S.roc(c, 5) if len(c) > 5 else None, ">", p["min_roc5_pct"])
    def c_px(j):
        c, _ = at(j); return cmp("CLOSE_GT_5", c[-1] if c else None, ">", p["min_close"])
    conds = [("BB", c_bb), ("RELVOL", c_rv), ("ROC", c_roc), ("PRICE", c_px)]
    res = window_group("PARABOLIC_MOMENTUM", conds, p["window"], p["window_mode"])
    alt = window_group("PARABOLIC_ALT", conds, p["window"], "independent" if p["window_mode"] == "common_anchor" else "common_anchor")
    anchors = [j for j in range(p["window"]) if len(b) > j and all(fn(j)["status"] == PASS for _, fn in conds)]
    cl = _closes(b); sma20 = S.sma(cl, 20)
    diag = {"qualifying_candles": [b[-1 - j].ts.date().isoformat() for j in anchors], "age_candles": min(anchors) if anchors else None,
            "extension_vs_sma20_pct": None if not sma20 else round(100 * (cl[-1] / sma20 - 1), 2), "atr14": S.atr_wilder(b),
            "median_dollar_volume_20d": S.median_dollar_volume(b), "other_window_mode_status": alt["status"],
            "risk_flags": [f for f, on in (("EXTENDED_GT_50PCT_ABOVE_SMA20", sma20 and cl[-1] / sma20 - 1 > 0.5), ("STALE_SIGNAL", anchors and min(anchors) >= 5)) if on]}
    return res, diag

STRATEGIES = {"CAN_SLIM": can_slim, "MINERVINI_VCP_SEPA": minervini, "TURTLE": turtle, "WEINSTEIN_STAGE_2": weinstein,
              "MAGIC_FORMULA": lambda d, p: magic(d, p)[0], "PARABOLIC_MOMENTUM": lambda d, p: parabolic(d, p)[0]}
