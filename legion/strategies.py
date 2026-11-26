"""Stock strategy modules. Strategy thresholds come ONLY from specs/<STRATEGY>.json (the original Legion scanner
specification). A strategy whose spec is not COMPLETE is INCOMPLETE and blocks every entry it would originate.
Nothing here supplies default thresholds."""
import json, os
from dataclasses import dataclass, field
from datetime import datetime
from . import freshness
from .config import SystemParams

SPEC_DIR = os.path.join(os.path.dirname(__file__), "..", "specs")
EXIT_TYPES = {"channel_exit", "ma_break_weeks", "max_hold_days", "trailing_pct"}

@dataclass
class Snapshot:
    ticker: str; quote: object; bars: list; spy_bars: list; fundamentals: dict; earnings: list | None
    now: datetime; extra: dict = field(default_factory=dict)

def load_spec(sid, spec_dir=SPEC_DIR):
    try: return json.load(open(os.path.join(spec_dir, f"{sid}.json")))
    except (OSError, ValueError): return {"strategy": sid, "status": "MISSING_OR_UNREADABLE", "params": {}, "exit_rules": []}
def spec_complete(spec, required):
    miss = [k for k in required if spec.get("params", {}).get(k) is None]
    why = []
    if spec.get("status") != "COMPLETE": why.append("SPEC_STATUS_NOT_COMPLETE")
    if not spec.get("source_document") or not spec.get("source_sha256"): why.append("SPEC_SOURCE_NOT_RECORDED")
    if miss: why.append(f"SPEC_PARAMS_MISSING {miss}")
    if not spec.get("exit_rules"): why.append("SPEC_EXIT_RULES_MISSING")
    elif any(r.get("type") not in EXIT_TYPES for r in spec["exit_rules"]): why.append("SPEC_EXIT_RULE_UNKNOWN_TYPE")
    return not why, why

# ---- primitives -----------------------------------------------------------------------------------------------
def sma(xs, n): return sum(xs[-n:]) / n if len(xs) >= n else None
def atr(bars, n):
    if len(bars) < n + 1: return None
    tr = [max(b.h - b.l, abs(b.h - p.c), abs(b.l - p.c)) for p, b in zip(bars, bars[1:])]
    return sum(tr[-n:]) / n
def weekly_closes(bars):
    out = {}
    for b in bars: out[b.ts.isocalendar()[:2]] = b.c
    return [out[k] for k in sorted(out)]
def avg_vol(bars, n=50): return sum(b.v for b in bars[-n:]) / min(n, len(bars)) if bars else None
def ret(bars, n): return bars[-1].c / bars[-1 - n].c - 1 if len(bars) > n else None

R = lambda cid, st, det="": {"criterion_id": cid, "status": st, "detail": det}
def _cmp(cid, val, ok, det=""):
    return R(cid, "UNVERIFIED", "no data") if val is None else R(cid, "PASS" if ok(val) else "FAIL", f"{det}{val:.4g}")

def common(c, s: Snapshot, sp: SystemParams):
    """Strategy-independent independent verification (owner-specified)."""
    out, q = [], s.quote
    ok, why = freshness.assess(q.ts, s.now, sp.quote_max_age_s)
    out.append(R("QUOTE_FRESH", "PASS" if ok else "FAIL", why))
    px = q.price
    out.append(_cmp("PRICE_DRIFT_VS_REPORT", None if px is None else abs(px / c["current_price"] - 1), lambda d: d <= sp.max_price_drift_pct))
    z = c["entry_zone"]
    out.append(R("PRICE_IN_ENTRY_ZONE", "UNVERIFIED" if px is None or not z else "PASS" if z["low"] <= px <= z["high"] else "FAIL", f"px={px}"))
    sl = c["technical_invalidation"]
    out.append(R("INVALIDATION_NOT_BREACHED", "UNVERIFIED" if px is None or sl is None else
                 "PASS" if (px > sl if c["trade_direction"] == "LONG" else px < sl) else "FAIL", f"px={px} stop={sl}"))
    av = avg_vol(s.bars)
    out.append(_cmp("LIQUIDITY_AVG_VOLUME", av, lambda v: v >= sp.min_avg_volume, "avg50="))
    out.append(_cmp("LIQUIDITY_DOLLAR_VOLUME", None if av is None or px is None else av * px, lambda v: v >= sp.min_dollar_volume, "$vol="))
    # earnings risk: unknown = block
    if s.earnings is None: out.append(R("EARNINGS_RISK", "UNVERIFIED", "calendar unavailable/unparsed"))
    else:
        today = s.now.date(); near = [d for d in s.earnings if 0 <= (datetime.fromisoformat(d).date() - today).days <= sp.earnings_blackout_days]
        out.append(R("EARNINGS_RISK", "FAIL" if near else "PASS", f"within {sp.earnings_blackout_days}d: {near}"))
    return out

def _vol_rs(s, p, sp):
    out = []; vr = None if not s.bars or not avg_vol(s.bars) else s.bars[-1].v / avg_vol(s.bars)
    if "breakout_volume_multiple" in p: out.append(_cmp("VOLUME_VS_50D", vr, lambda v: v >= p["breakout_volume_multiple"], "ratio="))
    if "min_rs_excess_return_pct" in p:
        a, b = ret(s.bars, sp.rs_lookback_days), ret(s.spy_bars, sp.rs_lookback_days)
        out.append(_cmp("RS_VS_SPY_EXCESS_RETURN", None if a is None or b is None else (a - b) * 100, lambda v: v >= p["min_rs_excess_return_pct"]))
    return out

def v_can_slim(c, s, p, sp):
    ext = None if s.quote.price is None else (s.quote.price / c["proposed_entry"] - 1) * 100
    return [_cmp("EXTENSION_ABOVE_PIVOT_PCT", ext, lambda e: e <= p["max_extension_above_pivot_pct"]),
            R("EPS_GROWTH", "UNVERIFIED", "EPS growth not provided by Robinhood fundamentals; cannot be independently verified")] + _vol_rs(s, p, sp)
def v_minervini(c, s, p, sp):
    cl, px = [b.c for b in s.bars], s.quote.price; per = sorted(p["sma_stack_periods"]); m = [sma(cl, n) for n in per]
    stack = px is not None and None not in m and px > m[0] and all(a > b for a, b in zip(m, m[1:]))
    out = [R("SMA_STACK", "UNVERIFIED" if px is None or None in m else "PASS" if stack else "FAIL", str(m))]
    L, d = per[-1], p["sma_long_rising_days"]
    out.append(R("LONG_SMA_RISING", "UNVERIFIED" if len(cl) < L + d else "PASS" if sma(cl, L) > sma(cl[:-d], L) else "FAIL"))
    lo, hi = s.fundamentals.get("low_52_weeks"), s.fundamentals.get("high_52_weeks")
    out.append(_cmp("PCT_ABOVE_52W_LOW", None if px is None or not lo else (px / lo - 1) * 100, lambda v: v >= p["min_pct_above_52w_low"]))
    out.append(_cmp("PCT_BELOW_52W_HIGH", None if px is None or not hi else (1 - px / hi) * 100, lambda v: v <= p["max_pct_below_52w_high"]))
    return out + _vol_rs(s, p, sp)
def v_turtle(c, s, p, sp):
    px, n = s.quote.price, p["entry_lookback"]; prior = s.bars[-n:]
    out = [_cmp("BREAKOUT_ABOVE_PRIOR_HIGH", None if px is None or len(s.bars) < n else px, lambda v: v > max(b.h for b in prior), "px=")]
    a = atr(s.bars, p["atr_period"]); sl = c["technical_invalidation"]
    out.append(R("STOP_NOT_LOOSER_THAN_SPEC", "UNVERIFIED" if a is None or px is None else
                 "PASS" if sl >= px - p["stop_atr_multiple"] * a else "FAIL", f"atr={a}"))
    return out
def v_weinstein(c, s, p, sp):
    w, px = weekly_closes(s.bars), s.quote.price; n, k = p["ma_weeks"], p["ma_slope_weeks"]
    if len(w) < n + k or px is None: out = [R("STAGE2_MA", "UNVERIFIED", "insufficient weekly history")]
    else:
        out = [R("PRICE_ABOVE_WEEKLY_MA", "PASS" if px > sma(w, n) else "FAIL"), R("WEEKLY_MA_RISING", "PASS" if sma(w, n) > sma(w[:-k], n) else "FAIL")]
    return out + _vol_rs(s, p, sp)
def v_magic(c, s, p, sp):
    r = s.extra.get("magic_formula_rank")
    return [_cmp("COMBINED_RANK", r, lambda v: v <= p["max_combined_rank"], "rank=")]
def v_parabolic(c, s, p, sp):
    n, cl, px = p["momentum_lookback_days"], [b.c for b in s.bars], s.quote.price
    r = ret(s.bars, n); m = sma(cl, p["sma_period"])
    return [_cmp("MOMENTUM_RETURN_PCT", None if r is None else r * 100, lambda v: v >= p["min_return_pct"]),
            _cmp("EXTENSION_FROM_SMA_PCT", None if px is None or m is None else (px / m - 1) * 100, lambda v: v <= p["max_extension_from_sma_pct"])] + _vol_rs(s, p, sp)

STRATEGIES = {
 "CAN_SLIM": (["breakout_volume_multiple", "max_extension_above_pivot_pct", "min_eps_growth_pct", "min_rs_excess_return_pct"], v_can_slim),
 "MINERVINI_VCP_SEPA": (["sma_stack_periods", "sma_long_rising_days", "min_pct_above_52w_low", "max_pct_below_52w_high", "breakout_volume_multiple", "min_rs_excess_return_pct"], v_minervini),
 "TURTLE": (["entry_lookback", "atr_period", "stop_atr_multiple", "exit_lookback"], v_turtle),
 "WEINSTEIN_STAGE_2": (["ma_weeks", "ma_slope_weeks", "breakout_volume_multiple", "min_rs_excess_return_pct"], v_weinstein),
 "MAGIC_FORMULA": (["max_combined_rank", "rebalance_days"], v_magic),
 "PARABOLIC_MOMENTUM": (["momentum_lookback_days", "min_return_pct", "breakout_volume_multiple", "max_extension_from_sma_pct", "sma_period"], v_parabolic)}

def verify_candidate(c, s: Snapshot, spec_dir=SPEC_DIR, sp=SystemParams(), variant=None):
    """-> (passed: bool, criteria: list, blockers: list). Candidate must pass for its originating strategy
    AND every additional qualifying strategy that is claimed (a claimed-but-incomplete strategy is ignored, not trusted)."""
    sid = c["originating_strategy"]
    if variant:                                       # LEGION_NATIVE routing; never mixed with EXACT_PLATFORM results
        from .scanners.gate import gate_native, NATIVE_SPEC_DIR
        return gate_native(c, s, load_spec(variant, NATIVE_SPEC_DIR), sp)
    req, fn = STRATEGIES[sid]; spec = load_spec(sid, spec_dir)
    if spec.get("format") == 2:
        from .scanners.gate import gate_v2
        return gate_v2(c, s, spec, sp)
    ok, why = spec_complete(spec, req)
    if not ok: return False, [], [f"STRATEGY_INCOMPLETE {sid}: {w}" for w in why]
    res = common(c, s, sp) + fn(c, s, spec["params"], sp)
    bad = [f"{r['criterion_id']}_{r['status']}" for r in res if r["status"] != "PASS"]
    return not bad, res, bad

def exit_signal(pos: dict, s: Snapshot, spec: dict | None):
    """Deterministic exit check. Stop/target always apply; strategy rules only from a COMPLETE spec."""
    px = s.quote.price
    if px is None: return None
    if (px <= pos["stop"]) if pos["direction"] == "LONG" else (px >= pos["stop"]): return "STOP"
    if pos.get("targets") and ((px >= pos["targets"][0]) if pos["direction"] == "LONG" else (px <= pos["targets"][0])): return "TARGET_1"
    if not spec or spec.get("status") != "COMPLETE": return None
    for r in spec["exit_rules"]:
        t = r["type"]
        if t == "channel_exit" and len(s.bars) > r["lookback"]:
            if px < min(b.l for b in s.bars[-r["lookback"]:]): return "CHANNEL_EXIT"
        elif t == "ma_break_weeks":
            w = weekly_closes(s.bars)
            if len(w) >= r["weeks"] and px < sma(w, r["weeks"]): return "WEEKLY_MA_BREAK"
        elif t == "max_hold_days" and (s.now.date() - datetime.fromisoformat(pos["opened"]).date()).days >= r["days"]: return "MAX_HOLD"
        elif t == "trailing_pct" and px <= pos.get("high_water", px) * (1 - r["pct"] / 100): return "TRAILING_STOP"
    return None
