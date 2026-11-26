"""SEC XBRL facts (via Robinhood's SEC tools, an authorized integration) -> GAAP diluted quarterly EPS history,
TTM flows, invested capital and the LEGION_NATIVE ROIC. Only consolidated facts (no dimensional axes) are used."""
from collections import defaultdict
from datetime import date

SOURCE = "SEC_EDGAR_VIA_ROBINHOOD"
DEBT_CONCEPTS = ("LongTermDebtNoncurrent", "LongTermDebtCurrent", "CommercialPaper", "ShortTermBorrowings")

def _d(s): return date.fromisoformat(s[:10])
def consolidated(facts):
    """{concept: [(start|None, end, value, filing_id)]} for facts without axes; numeric only."""
    out = defaultdict(list)
    for f in facts:
        if f.get("axises"): continue
        try: v = float(f["value"])
        except (TypeError, ValueError): continue
        out[f["concept"]].append((_d(f["start_date"]) if f.get("start_date") else None, _d(f["end_date"]), v, f.get("filing_id")))
    return out

def _dur(s, e): return (e - s).days
def quarterly_eps(facts_by_filing, filing_dates):
    """GAAP diluted EPS per fiscal quarter, newest first: [{"end", "eps", "status", "filing_id", "reason"}].
    Point-in-time: a quarter's value is taken from the EARLIEST filing that reported it; later restatements are
    recorded as conflicts, not silently substituted. Q4 has no separately filed 3-month value (it lives inside the 10-K)
    and FY-minus-9M EPS is not an exact quarterly EPS, so Q4 slots are kept with eps=None, status UNVERIFIED."""
    q, fy, conflicts = {}, set(), []
    for fid in sorted(facts_by_filing, key=lambda f: filing_dates[f]):
        for s, e, v, _ in consolidated(facts_by_filing[fid]).get("EarningsPerShareDiluted", []):
            if s is None: continue
            n = _dur(s, e)
            if 80 <= n <= 100:
                if e in q and q[e]["eps"] != v: conflicts.append((e.isoformat(), q[e]["eps"], v, fid))
                q.setdefault(e, {"end": e.isoformat(), "eps": v, "status": "VERIFIED", "filing_id": fid, "reason": "3-month diluted EPS"})
            elif 350 <= n <= 380: fy.add(e)
    for e in fy:
        q.setdefault(e, {"end": e.isoformat(), "eps": None, "status": "UNVERIFIED", "filing_id": None, "reason": "Q4_NOT_SEPARATELY_REPORTED"})
    return sorted(q.values(), key=lambda r: r["end"], reverse=True), conflicts

def contiguous(eps_rows, max_gap_days=100):
    """Truncate at the first missing quarter so E[k] always means 'k fiscal quarters ago'."""
    out = eps_rows[:1]
    for r in eps_rows[1:]:
        if (_d(out[-1]["end"]) - _d(r["end"])).days > max_gap_days: break
        out.append(r)
    return out

def ttm_flow(c, concept, end):
    """TTM of a flow item ending at `end`: YTD(end) + FY(prior) - YTD(same point prior year). Exact for flows, unlike EPS."""
    rows = c.get(concept, [])
    ytd = [r for r in rows if r[1] == end and r[0] is not None]
    if not ytd: return None, "no YTD value at period end"
    s, e, v, _ = max(ytd, key=lambda r: _dur(r[0], r[1]))
    n = _dur(s, e)
    if 350 <= n <= 380: return v, "fiscal year"
    fy = [r for r in rows if r[0] is not None and 350 <= _dur(r[0], r[1]) <= 380 and r[1] < end and (end - r[1]).days < 370]
    prior = [r for r in rows if r[0] is not None and abs(_dur(r[0], r[1]) - n) <= 7 and abs((e - r[1]).days - 364) <= 10]
    if not fy or not prior: return None, "missing FY or prior-year YTD for TTM"
    return v + max(fy, key=lambda r: r[1])[2] - prior[0][2], "YTD + FY(prior) - YTD(prior year)"

def instant(c, concept, at):
    vals = [r[2] for r in c.get(concept, []) if r[0] is None and r[1] == at]
    return vals[0] if vals else None

def invested_capital(c, at):
    """IC = total debt (LongTermDebtNoncurrent + LongTermDebtCurrent + CommercialPaper + ShortTermBorrowings, when tagged)
    + StockholdersEquity - CashAndCashEquivalentsAtCarryingValue. Equity and cash are mandatory; missing debt lines count as 0
    only if at least one debt concept is tagged at that date (otherwise the balance sheet is treated as incomplete)."""
    eq, cash = instant(c, "StockholdersEquity", at), instant(c, "CashAndCashEquivalentsAtCarryingValue", at)
    debts = {k: instant(c, k, at) for k in DEBT_CONCEPTS}
    if eq is None or cash is None or all(v is None for v in debts.values()): return None, {"reason": "incomplete balance sheet", "at": at.isoformat()}
    ic = sum(v for v in debts.values() if v is not None) + eq - cash
    return ic, {"at": at.isoformat(), "equity": eq, "cash": cash, **{k: v for k, v in debts.items() if v is not None}}

ROIC_DEFINITION = "LEGION_NATIVE_ROIC_V1"
def native_roic(c, end, begin, sector=None, tax_bounds=(0.0, 0.50)):
    """ROIC = TTM NOPAT / average(IC_begin, IC_end); NOPAT = TTM operating income x (1 - TTM effective tax rate),
    effective rate = TTM income tax expense / TTM pretax income. -> (value|None, provenance)."""
    prov = {"definition": ROIC_DEFINITION, "source": SOURCE, "end": end.isoformat(), "begin": begin.isoformat()}
    if sector and "financ" in sector.lower(): return None, {**prov, "reason": "FINANCIAL_INSTITUTION_EXCLUDED"}
    oi, m1 = ttm_flow(c, "OperatingIncomeLoss", end)
    tax, m2 = ttm_flow(c, "IncomeTaxExpenseBenefit", end)
    pre, m3 = ttm_flow(c, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", end)
    prov.update(operating_income_ttm=oi, tax_ttm=tax, pretax_ttm=pre, methods=[m1, m2, m3])
    if None in (oi, tax, pre): return None, {**prov, "reason": "incomplete income statement"}
    if pre <= 0: return None, {**prov, "reason": "UNUSUAL_TAX_RATE nonpositive pretax income"}
    rate = tax / pre; prov["effective_tax_rate"] = rate
    if not tax_bounds[0] <= rate <= tax_bounds[1]: return None, {**prov, "reason": f"UNUSUAL_TAX_RATE {rate:.3f}"}
    ic1, p1 = invested_capital(c, end); ic0, p0 = invested_capital(c, begin); prov.update(ic_end=p1, ic_begin=p0)
    if ic1 is None or ic0 is None: return None, {**prov, "reason": "incomplete balance sheet"}
    avg = (ic0 + ic1) / 2; prov["avg_invested_capital"] = avg
    if avg <= 0: return None, {**prov, "reason": "NEGATIVE_OR_ZERO_INVESTED_CAPITAL"}
    nopat = oi * (1 - rate); prov["nopat_ttm"] = nopat
    return nopat / avg, {**prov, "reason": "ok"}
