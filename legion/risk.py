"""Deterministic risk engine. Plain arithmetic, no AI inputs; every rule is enforced in code."""
import math
from dataclasses import dataclass, field
from .config import Limits

@dataclass
class Account:
    equity: float; cash: float; day_start_equity: float; week_start_equity: float
    stocks: list = field(default_factory=list)    # dicts: symbol, qty, price, stop, direction
    options: list = field(default_factory=list)   # dicts: underlying, max_loss, capital, cash_reserved
    @property
    def stock_value(self): return sum(abs(p["qty"]) * p["price"] for p in self.stocks)
    @property
    def options_capital(self): return sum(o["capital"] for o in self.options)
    @property
    def reserved(self): return sum(o.get("cash_reserved", 0) for o in self.options)
    @property
    def uncommitted_cash(self): return self.cash - self.reserved
    @property
    def open_risk(self):
        return sum(abs(p["qty"]) * max(0.0, (p["price"] - p["stop"]) if p["direction"] == "LONG" else (p["stop"] - p["price"])) for p in self.stocks) \
             + sum(o["max_loss"] for o in self.options)
    def exposure(self, sym): return any(p["symbol"] == sym for p in self.stocks) or any(o["underlying"] == sym for o in self.options)

def halt_reason(a: Account, L=Limits()):
    if a.day_start_equity > 0 and (a.day_start_equity - a.equity) / a.day_start_equity >= L.daily_halt_pct: return "DAILY_DRAWDOWN_HALT"
    if a.week_start_equity > 0 and (a.week_start_equity - a.equity) / a.week_start_equity >= L.weekly_halt_pct: return "WEEKLY_DRAWDOWN_HALT"
    return None

@dataclass
class Sizing: qty: int; reasons: list; detail: dict = field(default_factory=dict)

def size_stock(a: Account, sym, entry, stop, direction="LONG", L=Limits()) -> Sizing:
    r = []
    if (h := halt_reason(a, L)): return Sizing(0, [h])
    if a.exposure(sym): return Sizing(0, ["DUPLICATE_EXPOSURE"])
    per = (entry - stop) if direction == "LONG" else (stop - entry)
    if per <= 0: return Sizing(0, ["INVALID_STOP_DISTANCE"])
    caps = {"risk": L.stock_risk_pct * a.equity / per, "single_name": L.max_stock_alloc_pct * a.equity / entry,
            "stock_ceiling": (L.stock_ceiling_pct * a.equity - a.stock_value) / entry,
            "min_cash": (a.uncommitted_cash - L.min_cash_pct * a.equity) / entry,
            "aggregate_risk": (L.max_open_risk_pct * a.equity - a.open_risk) / per}
    qty = max(0, math.floor(min(caps.values())))
    if qty < 1: r = [f"BLOCKED_BY_{k.upper()}" for k, v in caps.items() if v < 1]
    return Sizing(qty, r, {k: round(v, 2) for k, v in caps.items()})

def size_option(a: Account, st, L=Limits(), shares_free=0) -> Sizing:
    """st needs: kind, underlying, max_loss_per, capital_per, cash_impact_per."""
    if (h := halt_reason(a, L)): return Sizing(0, [h])
    if st.kind == "COVERED_CALL":     # no incremental downside beyond shares already inside the stock risk budget
        q = int(shares_free // 100); return Sizing(q, [] if q else ["NO_SHARES_FOR_COVERED_CALL"], {"shares_free": shares_free})
    if any(o["underlying"] == st.underlying for o in a.options) or a.exposure(st.underlying): return Sizing(0, ["DUPLICATE_EXPOSURE"])
    if st.max_loss_per is None or st.max_loss_per <= 0: return Sizing(0, ["UNDEFINED_MAX_LOSS"])
    caps = {"max_loss": L.option_max_loss_pct * a.equity / st.max_loss_per,
            "options_ceiling": (L.options_ceiling_pct * a.equity - a.options_capital) / st.capital_per,
            "min_cash": (a.uncommitted_cash - L.min_cash_pct * a.equity) / st.cash_impact_per if st.cash_impact_per > 0 else math.inf,
            "aggregate_risk": (L.max_open_risk_pct * a.equity - a.open_risk) / st.max_loss_per}
    qty = max(0, math.floor(min(caps.values())))
    return Sizing(qty, [f"BLOCKED_BY_{k.upper()}" for k, v in caps.items() if v < 1] if qty < 1 else [],
                  {k: round(v, 2) if v != math.inf else None for k, v in caps.items()})

def recheck_option_intent(a: Account, st, qty, L=Limits(), shares_free=0):
    """Independent post-sizing verification used by the paper broker (defence in depth)."""
    s = size_option(a, st, L, shares_free); return [] if qty <= s.qty else (s.reasons or [f"QTY_EXCEEDS_LIMIT max={s.qty}"])
def recheck_stock_intent(a: Account, sym, qty, entry, stop, direction, L=Limits()):
    s = size_stock(a, sym, entry, stop, direction, L); return [] if qty <= s.qty else (s.reasons or [f"QTY_EXCEEDS_LIMIT max={s.qty}"])
