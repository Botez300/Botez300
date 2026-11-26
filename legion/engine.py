"""Orchestrator: report -> eligibility -> independent verification -> risk sizing -> PAPER order.
Reports are DATA. They never authorize a brokerage action; every order is produced and re-checked locally."""
import json, os
from datetime import datetime, timezone
from . import options as O
from .config import Limits, OptionRules, SystemParams
from .eligibility import evaluate_report
from .paper import PaperBroker, RiskViolation
from .risk import size_stock, size_option, halt_reason
from .strategies import verify_candidate

class Orchestrator:
    def __init__(self, ledger, broker: PaperBroker, market, client, decisions_path, spec_dir=None, sp=SystemParams(),
                 option_kinds=(), limits=Limits(), rules=OptionRules(), alert=lambda *a, **k: None,
                 variants=None, require_report_evidence=False):
        self.ledger, self.b, self.m, self.rh = ledger, broker, market, client
        self.dp, self.spec_dir, self.sp, self.kinds, self.L, self.R, self.alert = decisions_path, spec_dir, sp, option_kinds, limits, rules, alert
        self.variants, self.require_evidence = variants or {}, require_report_evidence
    def _log(self, rec):
        with open(self.dp, "a") as f: f.write(json.dumps(rec, default=str) + "\n")

    def ingest(self, item, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        raw = item.read()
        d = evaluate_report(raw, item.name, now, item.size, getattr(item, "md5", None), self.ledger.ids, self.ledger.hashes, getattr(item, "age", 1e9))
        if d.deferred: self._log({"file": item.name, "outcome": "DEFERRED_PARTIAL_SYNC"}); return d
        if not d.tradeable:
            self.ledger.record(d, "REJECTED") if not any(x.startswith("DUPLICATE") for x in d.reasons) else None
            self._log({"file": item.name, "outcome": "REJECTED", "reasons": d.reasons}); return d
        self.ledger.record(d, "ADMITTED")                      # recorded first => a crash can never double-process a report
        for cd, c in zip(d.candidates, d.doc["candidates"]):
            try: res = self._candidate(c, cd, now)
            except Exception as e:                       # fail closed: an unexpected error never becomes an order
                self.alert("CANDIDATE_ERROR", f"{c['ticker']}: {type(e).__name__}: {e}"); res = {"outcome": "BLOCKED", "reasons": [f"ERROR {type(e).__name__}"]}
            self._log({"file": item.name, "signal": c["signal_id"], **res})
        return d

    def _candidate(self, c, cd, now):
        from .evidence import audit_report_candidate
        audit = audit_report_candidate(c, now)
        if not cd.eligible: return {"outcome": "NOT_ELIGIBLE", "reasons": cd.reasons, "evidence_audit": audit}
        if self.require_evidence and any(a["status"] != "VERIFIED" for a in audit):
            return {"outcome": "NOT_ELIGIBLE", "reasons": ["REPORT_CRITERIA_EVIDENCE_UNVERIFIED"], "evidence_audit": audit}
        if self.b.has_signal(c["signal_id"]): return {"outcome": "DUPLICATE_SIGNAL"}
        h = halt_reason(self.b.account(), self.L)
        if h: self.alert("HALT", h); return {"outcome": "BLOCKED", "reasons": [h]}
        try: snap = self.m.snapshot(c["ticker"], now)
        except Exception as e: self.alert("DATA_FAILURE", f"{c['ticker']}: {e}"); return {"outcome": "BLOCKED", "reasons": [f"MARKET_DATA_UNAVAILABLE {type(e).__name__}"]}
        var = self.variants.get(c["originating_strategy"])
        if var: ok, crit, bad = verify_candidate(c, snap, sp=self.sp, variant=var)
        else: ok, crit, bad = verify_candidate(c, snap, self.spec_dir, self.sp) if self.spec_dir else verify_candidate(c, snap, sp=self.sp)
        if not ok: return {"outcome": "VERIFICATION_FAILED", "reasons": bad, "criteria": crit}
        acct, px = self.b.account(), snap.quote.price
        sz = size_stock(acct, c["ticker"], px, c["technical_invalidation"], c["trade_direction"], self.L)
        if sz.qty >= 1:
            try:
                self.b.submit_stock({"symbol": c["ticker"], "qty": sz.qty, "entry": px, "stop": c["technical_invalidation"], "direction": c["trade_direction"],
                    "targets": c["proposed_price_targets"], "strategy": c["originating_strategy"], "signal_id": c["signal_id"]}, now)
                return {"outcome": "PAPER_STOCK_ORDER", "qty": sz.qty, "price": px, "sizing": sz.detail}
            except RiskViolation as e: return {"outcome": "BLOCKED", "reasons": [str(e)]}
        out = {"stock_blocked": sz.reasons}
        if self.kinds and c["options_eligibility"]["eligible"]:
            return {**out, **self._options(c, snap, now)}
        return {"outcome": "NO_TRADE", **out}

    def _options(self, c, snap, now):
        today = now.astimezone(__import__("legion.calendar", fromlist=["NY"]).NY).date()
        ctx = {"spot": snap.quote.price, "today": today, "now": now, "targets": c["proposed_price_targets"], "invalidation": c["technical_invalidation"],
               "earnings": snap.earnings, "direction": c["trade_direction"], "options_eligible": True, "bearish_verified": False, "shares_free": 0}
        try: chain = O.load_chain(self.rh, c["ticker"], snap.quote.price, self.kinds, today)
        except Exception as e: return {"outcome": "BLOCKED", "reasons": [f"OPTIONS_DATA_UNAVAILABLE {type(e).__name__}"]}
        tried = {}
        for k in self.kinds:
            dec = O.select(k, chain, ctx, self.R); tried[k] = dec.rejections
            if dec.structure:
                q = size_option(self.b.account(), dec.structure, self.L).qty
                if q >= 1:
                    try: self.b.submit_option(dec.structure, q, c["signal_id"], now=now); return {"outcome": "PAPER_OPTION_ORDER", "kind": k, "qty": q}
                    except RiskViolation as e: tried[k] = {str(e): 1}
                else: tried[k] = {"SIZED_TO_ZERO": 1}
        return {"outcome": "NO_TRADE", "options_rejections": tried}
