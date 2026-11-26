"""Entry-confirmation rules (separate from mechanical qualification). Every numeric threshold lives in the spec under
entry_confirmation.proposed_thresholds and is PROPOSED until the owner approves it; the gate refuses unapproved rules."""
from . import series as S
from .tri import AND, OR, cmp, unv, node, PASS, FAIL, UNV

def _rr(entry, stop, target):
    return None if None in (entry, stop, target) or entry <= stop else (target - entry) / (entry - stop)

def swing_contractions(bars, w=3):
    """Successive pullback depths (%) from swing highs to the following swing lows inside the base."""
    hs = [i for i in range(w, len(bars) - w) if bars[i].h == max(x.h for x in bars[i - w:i + w + 1])]
    out = []
    for a, b2 in zip(hs, hs[1:] + [len(bars) - 1]):
        lo = min(x.l for x in bars[a:b2 + 1]); out.append((a, 100 * (1 - lo / bars[a].h)))
    return out

def confirm(sid, d, c, t, diag=None):
    """d: Data; c: candidate (report); t: proposed thresholds. Returns a tri-state tree."""
    b = d.daily or []; cl = [x.c for x in b]; px = cl[-1] if cl else None; v = [x.v for x in b]
    stop, tgt = c.get("technical_invalidation"), (c.get("proposed_price_targets") or [None])[0]
    rr = cmp("REWARD_RISK", _rr(px, stop, tgt), ">=", t.get("min_reward_risk"))
    inv = cmp("INVALIDATION_DISTANCE_PCT", None if px is None or stop is None else 100 * (px - stop) / px, "<=", t.get("max_stop_distance_pct"))
    vol_x = None if len(v) < 51 or not S.sma(v, 50, 1) else v[-1] / S.sma(v, 50, 1)
    if sid in ("CAN_SLIM", "CAN_SLIM_NATIVE"):
        piv = S.rng_high(b, t["pivot_lookback"], 1)
        brk = AND("BREAKOUT", [cmp("CLOSE_GT_PIVOT", px, ">", piv), cmp("BREAKOUT_VOLUME_X50", vol_x, ">=", t["breakout_volume_x"])])
        s50 = S.sma(cl, 50)
        pb = AND("CONSTRUCTIVE_PULLBACK", [cmp("ABOVE_SMA50", px, ">", s50), cmp("WITHIN_PCT_OF_SMA50", None if not s50 else 100 * (px / s50 - 1), "<=", t["pullback_max_pct_above_sma50"])])
        return AND("ENTRY_CAN_SLIM", [OR("SETUP", [brk, pb]), inv, rr])
    if sid.startswith("MINERVINI"):
        base = b[-t["base_len"]:] if len(b) >= t["base_len"] else []
        ct = swing_contractions(base) if base else []
        depths = [x[1] for x in ct]
        vcp = node("VCP_CONTRACTIONS", UNV if not base else PASS if len(depths) >= t["min_contractions"] and all(a > b2 for a, b2 in zip(depths, depths[1:])) and depths[-1] <= t["max_final_contraction_pct"] else FAIL, f"depths={[round(x, 1) for x in depths]}")
        piv = base[ct[-1][0]].h if ct else None
        rs = None if len(cl) < 64 or not d.extra_spy else (cl[-1] / cl[-64]) / (d.extra_spy[-1] / d.extra_spy[-64]) - 1
        return AND("ENTRY_MINERVINI", [vcp, cmp("BREAKOUT_ABOVE_PIVOT", px, ">", piv), cmp("BREAKOUT_VOLUME_X50", vol_x, ">=", t["breakout_volume_x"]),
                   cmp("RS_VS_SPY_63D", rs, ">", 0.0), cmp("EXTENSION_ABOVE_PIVOT_PCT", None if not piv or px is None else 100 * (px / piv - 1), "<=", t["max_extension_pct"]), inv, rr])
    if sid.startswith("TURTLE"):
        sz = (diag or {}).get("sizing")
        return AND("ENTRY_TURTLE", [node("NEW_SIGNAL_VERIFIED", PASS if (diag or {}).get("mechanical") == PASS else UNV),
                   node("VOLATILITY_SIZING_DEFINED", PASS if sz else UNV, str(sz)), inv])
    if sid.startswith("WEINSTEIN"):
        w = d.weekly or []; res = S.rng_high(w, t["resistance_weeks"], 1); wc = w[-1].c if w else None
        rv = S.relvol([x.v for x in w], 20, 1) if len(w) > 21 else None
        return AND("ENTRY_WEINSTEIN", [node("STAGE2_TRANSITION_VERIFIED", PASS if (diag or {}).get("mechanical") == PASS else UNV),
                   cmp("WEEKLY_CLOSE_ABOVE_RESISTANCE", wc, ">", res), cmp("WEEKLY_RELVOL", rv, ">=", t["min_weekly_relvol"]), inv, rr])
    if sid.startswith("MAGIC"):
        return AND("ENTRY_MAGIC", [cmp("CLOSE_GT_SMA200", px, ">", S.sma(cl, 200)), cmp("SMA50_GT_SMA200", S.sma(cl, 50), ">", S.sma(cl, 200)), inv, rr])
    if sid.startswith("PARABOLIC"):
        age = (diag or {}).get("age_candles")
        rng = b[-(age or 0):] if age else []
        lo = min(x.l for x in rng) if rng else None; hi = max(x.h for x in rng[:-1]) if len(rng) > 1 else None
        # contraction: method is explicit (default unchanged = CONS_TR_OVER_ATR14_CURRENT); see backtest/contraction.py
        from ..backtest.contraction import ratio as _cratio
        meth = t.get("contraction_method", "CONS_TR_OVER_ATR14_CURRENT")
        crat = _cratio(meth, b, len(b) - 1 - age, len(b) - 1) if age else None
        return AND("ENTRY_PARABOLIC", [cmp("CONSOLIDATION_AGE_MIN", age, ">=", t["min_consolidation_candles"]), cmp("CONSOLIDATION_AGE_MAX", age, "<=", t["max_consolidation_candles"]),
            cmp(f"RANGE_CONTRACTION[{meth}]", crat, "<=", t["max_atr5_over_atr14"]),
            cmp("BREAKOUT_OF_CONSOLIDATION_HIGH", px, ">", hi), cmp("NOT_EXTENDED_VS_SMA20_PCT", None if not S.sma(cl, 20) else 100 * (px / S.sma(cl, 20) - 1), "<=", t["max_extension_vs_sma20_pct"]),
            cmp("STOP_AT_OR_BELOW_CONSOLIDATION_LOW", stop, "<=", lo), inv, rr])
    return unv("ENTRY", f"no entry rules for {sid}")
