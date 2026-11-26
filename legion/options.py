"""Options research + paper-structure selection. Defined-risk only. Returns NO TRADE unless every requirement holds."""
from dataclasses import dataclass, field
from datetime import date, datetime
from . import freshness
from .config import OptionRules

BULL = {"LONG_CALL", "LEAPS", "BULL_CALL_SPREAD", "BULL_PUT_SPREAD", "CASH_SECURED_PUT", "COVERED_CALL"}
BEAR = {"LONG_PUT", "BEAR_PUT_SPREAD", "BEAR_CALL_SPREAD"}
KINDS = BULL | BEAR
class NakedOptionError(ValueError): pass

@dataclass
class Structure:
    kind: str; underlying: str; legs: list           # [(side, Contract)]
    net: float; max_loss_per: float; max_profit_per: float | None; breakeven: float
    capital_per: float; cash_impact_per: float; assignment_downside_per: float; dte: int
    flags: list = field(default_factory=list)
    @property
    def expiry(self): return self.legs[0][1].expiry
@dataclass
class Decision: kind: str; structure: Structure | None; rejections: dict

def _dte(expiry, today): return (date.fromisoformat(expiry) - today).days
def _mid(c): return (c.bid + c.ask) / 2

def liquidity_reasons(c, R: OptionRules, now):
    r = []
    if not c.tradable: r.append("NOT_TRADABLE")
    if c.bid is None or c.ask is None or c.bid <= 0 or c.ask <= 0 or c.ask < c.bid: return r + ["NO_VALID_BID_ASK"]
    if (c.ask - c.bid) / _mid(c) > R.max_spread_pct: r.append("SPREAD_TOO_WIDE")
    if c.oi is None or c.oi < R.min_oi: r.append("OPEN_INTEREST_LOW")
    if c.volume is None or c.volume < R.min_volume: r.append("VOLUME_LOW")
    if c.delta is None or c.iv is None or c.gamma is None or c.theta is None or c.vega is None: r.append("GREEKS_MISSING")
    ok, why = freshness.assess(c.updated, now, R.quote_max_age_s)
    if not ok: r.append(f"QUOTE_{why}")
    return r

def assert_defined_risk(st: Structure, held_shares=0):
    sells = [c for s, c in st.legs if s == "SELL"]; buys = [c for s, c in st.legs if s == "BUY"]
    for sc in sells:
        if st.kind == "CASH_SECURED_PUT" and sc.type == "put" and len(st.legs) == 1: continue
        if st.kind == "COVERED_CALL" and sc.type == "call" and len(st.legs) == 1 and held_shares >= 100: continue
        cover = [b for b in buys if b.type == sc.type and b.expiry == sc.expiry]   # any same-type/same-expiry long leg bounds the loss (debit or credit vertical)
        if not cover: raise NakedOptionError(f"{st.kind}: short {sc.type} {sc.strike} is uncovered")
    if st.kind in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"} and len(st.legs) != 2: raise NakedOptionError("spread must have exactly 2 legs")

def _earn(expiry, ctx):
    e = ctx.get("earnings")
    if e is None: return "EARNINGS_UNKNOWN"
    if any(ctx["today"] <= date.fromisoformat(d) <= date.fromisoformat(expiry) for d in e): return "EARNINGS_BEFORE_EXPIRY"
    return None

def _pool(chain, typ, dte_rng, delta_rng, ctx, R, rej, check_delta=True):
    out = []
    for ex, bt in chain.items():
        d = _dte(ex, ctx["today"])
        if d < 1: rej["ZERO_DTE_OR_EXPIRED"] = rej.get("ZERO_DTE_OR_EXPIRED", 0) + 1; continue
        if not dte_rng[0] <= d <= dte_rng[1]: rej["DTE_OUT_OF_RANGE"] = rej.get("DTE_OUT_OF_RANGE", 0) + 1; continue
        if (er := _earn(ex, ctx)): rej[er] = rej.get(er, 0) + len(bt.get(typ, [])); continue
        for c in bt.get(typ, []):
            rs = liquidity_reasons(c, R, ctx["now"])
            if check_delta and not rs and not delta_rng[0] <= abs(c.delta) <= delta_rng[1]: rs = ["DELTA_OUT_OF_BAND"]
            if rs:
                for x in rs: rej[x] = rej.get(x, 0) + 1
            else: out.append((ex, d, c))
    return out

def _long(kind, typ, chain, ctx, R, rej, dte_rng, delta_rng):
    pool = _pool(chain, typ, dte_rng, delta_rng, ctx, R, rej); mid = sum(delta_rng) / 2
    if not pool: return None
    ex, d, c = min(pool, key=lambda t: (abs(abs(t[2].delta) - mid), (t[2].ask - t[2].bid) / _mid(t[2]), t[2].strike, t[0]))
    be = c.strike + c.ask if typ == "call" else c.strike - c.ask
    return Structure(kind, c.underlying, [("BUY", c)], c.ask, c.ask * c.multiplier, None, be, c.ask * c.multiplier, c.ask * c.multiplier, c.ask * c.multiplier, d)

def _vertical(kind, chain, ctx, R, rej):
    debit = kind in ("BULL_CALL_SPREAD", "BEAR_PUT_SPREAD")
    typ = "call" if kind in ("BULL_CALL_SPREAD", "BEAR_CALL_SPREAD") else "put"
    tgt, inv = (ctx.get("targets") or [None])[0], ctx.get("invalidation")
    if tgt is None or inv is None: rej["MISSING_TARGET_OR_INVALIDATION"] = 1; return None
    best = None
    for ex, bt in chain.items():
        d = _dte(ex, ctx["today"])
        if d < 1 or not R.vertical_dte[0] <= d <= R.vertical_dte[1]: rej["DTE_OUT_OF_RANGE"] = rej.get("DTE_OUT_OF_RANGE", 0) + 1; continue
        if (er := _earn(ex, ctx)): rej[er] = rej.get(er, 0) + 1; continue
        good = {}
        for c in bt.get(typ, []):
            rs = liquidity_reasons(c, R, ctx["now"])
            for x in rs: rej[x] = rej.get(x, 0) + 1
            if not rs: good[c.strike] = c
        for a in good.values():                       # a = the leg that carries the delta test
            band = R.directional_delta if debit else R.credit_spread_short_delta
            if not band[0] <= abs(a.delta) <= band[1]: rej["DELTA_OUT_OF_BAND"] = rej.get("DELTA_OUT_OF_BAND", 0) + 1; continue
            for b in good.values():
                if a.strike == b.strike: continue
                if kind == "BULL_CALL_SPREAD": lg, sh, ok = a, b, b.strike > a.strike and b.strike <= tgt
                elif kind == "BEAR_PUT_SPREAD": lg, sh, ok = a, b, b.strike < a.strike and b.strike >= tgt
                elif kind == "BULL_PUT_SPREAD": sh, lg, ok = a, b, b.strike < a.strike and a.strike <= inv
                else: sh, lg, ok = a, b, b.strike > a.strike and a.strike >= inv
                if not ok: continue
                w = abs(lg.strike - sh.strike)
                net = (lg.ask - sh.bid) if debit else (sh.bid - lg.ask)       # debit>0 ; credit>0
                if net <= 0 or net >= w: rej["NO_EDGE_PRICING"] = rej.get("NO_EDGE_PRICING", 0) + 1; continue
                ml = (net if debit else w - net) * a.multiplier; mp = ((w - net) if debit else net) * a.multiplier
                be = (lg.strike + net if kind == "BULL_CALL_SPREAD" else lg.strike - net) if debit else (sh.strike - net if kind == "BULL_PUT_SPREAD" else sh.strike + net)
                st = Structure(kind, a.underlying, [("BUY", lg), ("SELL", sh)], net if debit else -net, ml, mp, be, ml, ml, ml, d)
                key = (-mp / ml, d, lg.strike, sh.strike)
                if best is None or key < best[0]: best = (key, st)
    return best[1] if best else None

def _csp_cc(kind, chain, ctx, R, rej):
    cc = kind == "COVERED_CALL"
    if cc and ctx.get("shares_free", 0) < 100: rej["NO_SHARES_FOR_COVERED_CALL"] = 1; return None
    rng, band = (R.covered_call_dte, R.covered_call_delta) if cc else (R.csp_dte, R.csp_delta)
    pool = _pool(chain, "call" if cc else "put", rng, band, ctx, R, rej)
    if cc: pool = [t for t in pool if t[2].strike > ctx["spot"]]
    if not pool: return None
    ex, d, c = min(pool, key=lambda t: (abs(abs(t[2].delta) - sum(band) / 2), -t[2].bid, t[2].strike, t[0]))
    m = c.multiplier
    if cc:
        return Structure(kind, c.underlying, [("SELL", c)], -c.bid, 0.0, (c.strike - ctx["spot"] + c.bid) * m, ctx["spot"] - c.bid, 0.0, 0.0,
                         (ctx["spot"] - c.bid) * m, d, ["assignment_caps_upside"] + (["ITM_ASSIGNMENT_RISK"] if c.strike <= ctx["spot"] else []))
    dn = (c.strike - c.bid) * m
    return Structure(kind, c.underlying, [("SELL", c)], -c.bid, dn, c.bid * m, c.strike - c.bid, c.strike * m, dn, dn, d,
                     ["full_assignment_downside_counted_as_max_loss"] + (["ITM_ASSIGNMENT_RISK"] if c.strike >= ctx["spot"] else []))

def select(kind, chain, ctx, R=OptionRules()) -> Decision:
    """chain: {expiry: {"call":[Contract], "put":[Contract]}}; ctx: spot,today,now,targets,invalidation,earnings,direction,
    options_eligible,bearish_verified,shares_free."""
    rej = {}
    def no(why): rej[why] = rej.get(why, 0) + 1; return Decision(kind, None, rej)
    if kind not in KINDS: return no("UNKNOWN_KIND")
    if not ctx.get("options_eligible"): return no("OPTIONS_NOT_ELIGIBLE")
    if kind in BEAR and not (ctx.get("direction") == "SHORT" and ctx.get("bearish_verified")): return no("BEARISH_SETUP_NOT_INDEPENDENTLY_VERIFIED")
    if kind in BULL and ctx.get("direction") != "LONG": return no("DIRECTION_MISMATCH")
    if kind == "LONG_CALL": st = _long(kind, "call", chain, ctx, R, rej, R.directional_dte, R.directional_delta)
    elif kind == "LONG_PUT": st = _long(kind, "put", chain, ctx, R, rej, R.directional_dte, R.directional_delta)
    elif kind == "LEAPS": st = _long(kind, "call", chain, ctx, R, rej, R.leaps_dte, R.leaps_delta)
    elif kind in ("CASH_SECURED_PUT", "COVERED_CALL"): st = _csp_cc(kind, chain, ctx, R, rej)
    else: st = _vertical(kind, chain, ctx, R, rej)
    if st is None: return Decision(kind, None, rej or {"NO_QUALIFYING_CONTRACT": 1})
    assert_defined_risk(st, ctx.get("shares_free", 0))
    return Decision(kind, st, rej)

def load_chain(client, ticker, spot, kinds, today, band=0.30):
    """Fetch only expirations/strikes that can matter (ASSUMPTION: strikes within +/-30% of spot)."""
    R = OptionRules(); rng = {"LONG_CALL": R.directional_dte, "LONG_PUT": R.directional_dte, "LEAPS": R.leaps_dte, "CASH_SECURED_PUT": R.csp_dte,
        "COVERED_CALL": R.covered_call_dte}
    ch = client.chain(ticker); out = {}
    for ex in ch["expirations"]:
        d = _dte(ex, today)
        need = [k for k in kinds if (rng.get(k) or R.vertical_dte)[0] <= d <= (rng.get(k) or R.vertical_dte)[1]]
        if not need: continue
        out[ex] = {}
        for t in ("call", "put"):
            cs = [c for c in client.contracts(ch["id"], ex, t) if (1 - band) * spot <= c.strike <= (1 + band) * spot]
            out[ex][t] = client.option_quotes(cs)
    return out
