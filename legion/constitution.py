"""Risk constitution additions (Phase 5). Deterministic; no model or report can override.
- Halt latch: any limit breach writes state/RISK_HALT.json; new entries stay blocked until a human runs
  `python -m legion.ops resume --confirm` (manual authorization). Approved risk-reduction procedures: NONE yet, so open
  simulated positions are reviewed and listed, never auto-liquidated by this module.
- Exposure report: whole-portfolio stock/options/collateral/sector/open-risk, including pending simulated orders."""
import json, os
from datetime import datetime, timezone
from .risk import halt_reason
from .config import Limits

def latch_path(state_dir): return os.path.join(state_dir, "RISK_HALT.json")
def latched(state_dir): return state_dir is not None and os.path.exists(latch_path(state_dir))

def trip(state_dir, reason, account, alert=None):
    if latched(state_dir): return False
    rec = {"at": datetime.now(timezone.utc).isoformat(), "reason": reason, "equity": account.equity,
           "open_positions_review": {"stocks": [p["symbol"] for p in account.stocks], "options": [o["underlying"] for o in account.options]},
           "risk_reduction_applied": "none (no owner-approved procedure)", "resume": "manual: python -m legion.ops resume --confirm"}
    json.dump(rec, open(latch_path(state_dir), "w"), indent=1)
    if alert: alert("RISK_HALT", reason)
    return True

def resume(state_dir, confirm=False):
    if not confirm: raise PermissionError("resume requires explicit --confirm")
    if latched(state_dir): os.rename(latch_path(state_dir), latch_path(state_dir) + f".resolved.{int(datetime.now().timestamp())}")
    return True

def exposure(account, sectors=None, pending=(), L=Limits()):
    eq = account.equity or 1; sectors = sectors or {}
    by = {}
    for p in account.stocks: by[sectors.get(p["symbol"], "UNKNOWN")] = by.get(sectors.get(p["symbol"], "UNKNOWN"), 0) + abs(p["qty"]) * p["price"]
    pend = sum(x.get("notional", 0) for x in pending); pend_risk = sum(x.get("risk", 0) for x in pending)
    return {"equity": account.equity, "stock_pct": account.stock_value / eq, "options_capital_pct": account.options_capital / eq,
            "collateral_reserved_pct": account.reserved / eq, "uncommitted_cash_pct": (account.uncommitted_cash - pend) / eq,
            "open_risk_pct_incl_pending": (account.open_risk + pend_risk) / eq, "sector_pct": {k: v / eq for k, v in by.items()},
            "halt": halt_reason(account, L), "sector_limit": None, "correlation_limit": None,
            "note": "sector/correlation limits are not owner-approved; reported, not enforced"}
