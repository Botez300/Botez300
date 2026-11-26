"""PAPER broker. Simulated fills only; there is no code path to a real brokerage. Every order is re-checked
against the deterministic risk engine and the naked-option guard at the moment of submission."""
import json, os, tempfile
from datetime import datetime
from . import MODE
from .config import Limits
from .options import Structure, assert_defined_risk
from .risk import Account, recheck_stock_intent, recheck_option_intent

class RiskViolation(RuntimeError): pass
class LiveTradingForbidden(RuntimeError): pass

class PaperBroker:
    def __init__(self, state_path, journal_path, start_equity=100_000.0, limits=Limits()):
        if MODE != "PAPER": raise LiveTradingForbidden("MODE must be PAPER")
        self.path, self.jpath, self.L = state_path, journal_path, limits
        self.s = json.load(open(state_path)) if os.path.exists(state_path) else {
            "cash": start_equity, "stocks": [], "options": [], "executed_signals": [], "day_start": start_equity, "week_start": start_equity,
            "day": None, "week": None, "halted": None}
    def _save(self):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or "."); 
        with os.fdopen(fd, "w") as f: json.dump(self.s, f, indent=1)
        os.replace(tmp, self.path)
    def _log(self, rec):
        with open(self.jpath, "a") as f: f.write(json.dumps({"mode": "PAPER", "at": datetime.now().isoformat(), **rec}) + "\n")
    def account(self) -> Account:
        eq = self.s["cash"] + sum(p["qty"] * p["price"] for p in self.s["stocks"]) + sum(o["value"] for o in self.s["options"])
        return Account(eq, self.s["cash"], self.s["day_start"], self.s["week_start"], self.s["stocks"], self.s["options"])
    def roll_periods(self, day: str, week: str):
        eq = self.account().equity
        if self.s["day"] != day: self.s["day"], self.s["day_start"] = day, eq
        if self.s["week"] != week: self.s["week"], self.s["week_start"] = week, eq
        self._save()
    def mark_stock(self, sym, price):
        for p in self.s["stocks"]:
            if p["symbol"] == sym: p["price"] = price; p["high_water"] = max(p.get("high_water", price), price)
        self._save()
    def close_option(self, signal_id, value, reason):
        for o in list(self.s["options"]):
            if o["signal_id"] == signal_id:
                self.s["cash"] += value; self.s["options"].remove(o); self._save()
                self._log({"type": "OPTION_CLOSE", "signal_id": signal_id, "value": value, "reason": reason}); return True
        return False
    def has_signal(self, sid): return sid in self.s["executed_signals"]

    def submit_stock(self, i: dict, now=None):
        now = now or datetime.now()
        if i.get("live"): raise LiveTradingForbidden("live orders are not supported")
        if self.has_signal(i["signal_id"]): raise RiskViolation("DUPLICATE_SIGNAL")
        if i["qty"] < 1: raise RiskViolation("QTY_LT_1")
        v = recheck_stock_intent(self.account(), i["symbol"], i["qty"], i["entry"], i["stop"], i["direction"], self.L)
        if v: raise RiskViolation(";".join(v))
        self.s["cash"] -= i["qty"] * i["entry"] * (1 if i["direction"] == "LONG" else -1)
        self.s["stocks"].append({"symbol": i["symbol"], "qty": i["qty"] * (1 if i["direction"] == "LONG" else -1), "price": i["entry"], "stop": i["stop"], "direction": i["direction"],
            "targets": i.get("targets", []), "strategy": i.get("strategy"), "signal_id": i["signal_id"], "opened": now.date().isoformat(), "high_water": i["entry"]})
        self.s["executed_signals"].append(i["signal_id"]); self._save(); self._log({"type": "STOCK_OPEN", **i}); return True

    def close_stock(self, sym, price, reason):
        for p in list(self.s["stocks"]):
            if p["symbol"] == sym:
                self.s["cash"] += p["qty"] * price; self.s["stocks"].remove(p)
                self._save(); self._log({"type": "STOCK_CLOSE", "symbol": sym, "price": price, "reason": reason}); return True
        return False

    def submit_option(self, st: Structure, qty: int, signal_id: str, shares_free=0, now=None):
        now = now or datetime.now()
        """Whole structure only. Spread legs are never submitted independently."""
        if self.has_signal(signal_id): raise RiskViolation("DUPLICATE_SIGNAL")
        if qty < 1: raise RiskViolation("QTY_LT_1")
        assert_defined_risk(st, shares_free)
        if any((datetime.fromisoformat(c.expiry).date() - now.date()).days < 1 for _, c in st.legs): raise RiskViolation("ZERO_DTE")
        v = recheck_option_intent(self.account(), st, qty, self.L, shares_free)
        if v: raise RiskViolation(";".join(v))
        m = st.legs[0][1].multiplier; debit = st.net > 0
        self.s["cash"] -= st.net * m * qty
        self.s["options"].append({"underlying": st.underlying, "kind": st.kind, "qty": qty, "signal_id": signal_id, "expiry": st.expiry,
            "legs": [[sd, c.id, c.strike, c.type] for sd, c in st.legs], "max_loss": st.max_loss_per * qty, "capital": st.capital_per * qty,
            "cash_reserved": 0 if debit or st.kind == "COVERED_CALL" else (st.max_loss_per + (-st.net) * m) * qty, "value": st.net * m * qty})
        self.s["executed_signals"].append(signal_id); self._save()
        self._log({"type": "OPTION_OPEN", "kind": st.kind, "underlying": st.underlying, "qty": qty, "net": st.net, "max_loss": st.max_loss_per * qty, "signal_id": signal_id}); return True
