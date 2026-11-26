"""ResearchHub: assembles a scanner Data bundle from AUTHORIZED sources only, with per-field provenance.
Robinhood (market data, SEC filings tools) + official ETF holdings + imported authenticated indicator evidence."""
from datetime import date, datetime, timedelta, timezone
from ..evidence import require_authorized, Evidence
from ..scanners.rh_data import build
from . import sec

class ResearchHub:
    def __init__(self, client, now=None, evidence_imports=None):
        self.c, self.now = client, now or datetime.now(timezone.utc); self.ev = evidence_imports or {}
    def sec_bundle(self, ticker, n_filings=12, since_years=5):
        require_authorized(sec.SOURCE)
        idx = self.c.call("get_sec_filing_index", {"symbol": ticker, "form_type": ["10-Q", "10-K"], "since": (self.now - timedelta(days=365 * since_years)).date().isoformat()})
        fl = idx["filings"][:n_filings]; dates = {f["filing_id"]: f["date_filed"] for f in fl}
        facts = {}
        concepts = ["EarningsPerShareDiluted", "OperatingIncomeLoss", "IncomeTaxExpenseBenefit",
                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                    "StockholdersEquity", "CashAndCashEquivalentsAtCarryingValue", *sec.DEBT_CONCEPTS]
        for i in range(0, len(fl), 3):
            ids = [f["filing_id"] for f in fl[i:i + 3]]
            for f in self.c.call("get_sec_filing_facts", {"filing_ids": ids, "concepts": concepts[:10]})["facts"]:
                facts.setdefault(f["filing_id"], []).append(f)
        return facts, dates
    def build(self, ticker, market_index=None, with_sec=True):
        d = build(self.c, ticker, self.now, market_index)
        d.provenance["ohlcv"] = {"source": "ROBINHOOD_MCP", "observed_at": self.now.isoformat(), "method": "get_equity_historicals, completed bars only"}
        if with_sec:
            try:
                facts, dates = self.sec_bundle(ticker)
                rows, conflicts = sec.quarterly_eps(facts, dates)
                rows = sec.contiguous(rows)
                d.eps, d.eps_basis = [{"eps": r["eps"], "report_date": r["end"]} for r in rows], "GAAP_DILUTED"
                d.provenance["eps"] = {"source": sec.SOURCE, "quarters": len(rows), "conflicts": conflicts, "method": "3-month EarningsPerShareDiluted, first-filed value"}
                allf = [f for v in facts.values() for f in v]; c = sec.consolidated(allf)
                ends = sorted({r[1] for r in c.get("OperatingIncomeLoss", []) if r[0] is not None}, reverse=True)
                if ends:
                    end = ends[0]; begin = next((e for e in sorted({r[1] for r in c.get("StockholdersEquity", [])}, reverse=True) if 350 <= (end - e).days <= 380), None)
                    oi, m = sec.ttm_flow(c, "OperatingIncomeLoss", end)
                    d.operating_income_ttm, d.operating_income_source = oi, "SEC_TTM_OPERATING_INCOME" if oi is not None else None
                    if begin:
                        d.roic_ttm, prov = sec.native_roic(c, end, begin, d.sector); d.roic_definition = sec.ROIC_DEFINITION if d.roic_ttm is not None else None
                        d.provenance["roic"] = prov
                    ic, _ = sec.invested_capital(c, end)
                    if ic is not None and d.market_cap:
                        eq = sec.instant(c, "StockholdersEquity", end); d.enterprise_value = d.market_cap + (ic - eq)
                        d.provenance["enterprise_value"] = {"method": "Robinhood market cap + SEC (debt - cash) at " + end.isoformat(), "source": "ROBINHOOD_MCP+" + sec.SOURCE}
            except Exception as e:
                d.provenance["sec_error"] = f"{type(e).__name__}: {e}"
        for key, ev in self.ev.get(ticker, {}).items():           # authenticated indicator readings imported from Drive
            require_authorized(ev["source"]); d.proprietary[key] = ev["values"]; d.provenance[key] = ev
        return d
