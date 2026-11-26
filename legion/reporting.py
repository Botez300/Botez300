"""Paper-trading journal and risk report (published to Drive 05_Trade_Journal / 06_Risk_Reports). Reports only what
happened; zero trades is reported as zero trades."""
import json
from datetime import datetime, timezone
from .config import Limits
from .risk import halt_reason

def journal(decisions_path, journal_path):
    dec = [json.loads(l) for l in open(decisions_path)] if decisions_path and __import__("os").path.exists(decisions_path) else []
    fills = [json.loads(l) for l in open(journal_path)] if journal_path and __import__("os").path.exists(journal_path) else []
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "mode": "PAPER",
            "simulated_fills": fills, "decisions": dec,
            "summary": {"reports_or_candidates_evaluated": len(dec), "simulated_fills": len(fills),
                        "rejected": sum(1 for d in dec if d.get("outcome") not in ("PAPER_STOCK_ORDER", "PAPER_OPTION_ORDER"))}}

def risk_report(broker, L=Limits()):
    a = broker.account(); eq = a.equity or 1
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "mode": "PAPER", "equity": a.equity, "cash": a.cash,
            "uncommitted_cash_pct": a.uncommitted_cash / eq, "stock_allocation_pct": a.stock_value / eq, "options_capital_pct": a.options_capital / eq,
            "open_risk_pct": a.open_risk / eq, "halt": halt_reason(a, L), "positions": {"stocks": a.stocks, "options": a.options},
            "limits": {k: getattr(L, k) for k in L.__dataclass_fields__}}
