"""One PAPER trading session: regime -> manage -> screen -> risk -> intents -> fills.

Driven by a validated Robinhood MCP snapshot. Any data failure suspends new
simulated entries while preserving existing records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.config import all_symbols, pair_for_symbol, pairs
from src.data.history import load_bars
from src.data.models import OptionQuote, Snapshot
from src.options.screener import NO_QUALIFIED_TRADE, Candidate, nearest_misses, screen
from src.paper.broker import PaperBroker
from src.paper.fills import quote_is_fresh
from src.paper.manager import evaluate_position
from src.portfolio.portfolio import Portfolio
from src.regime.classifier import Regime, RegimeResult, classify
from src.regime.indicators import realized_vol
from src.risk.engine import RiskDecision, Verdict, breaker_state, evaluate_entry
from src.safety import assert_paper_mode


@dataclass
class Proposal:
    portfolio_id: str
    candidate: Candidate
    decision: RiskDecision
    order_id: str | None = None
    fill_status: str = "NOT SUBMITTED"


@dataclass
class SessionResult:
    as_of: date
    now: datetime
    regimes: dict[str, RegimeResult]
    eligible: list[Candidate]
    rejected: list[Candidate]
    misses: list[Candidate]
    proposals: dict[str, list[Proposal]] = field(default_factory=dict)
    shadow: dict[str, list[Proposal]] = field(default_factory=dict)   # regime gate waived; ILLUSTRATIVE ONLY
    management: dict[str, list[str]] = field(default_factory=dict)
    data_problems: list[str] = field(default_factory=list)
    entries_suspended: bool = False
    headline: str = ""


def validate_snapshot(snap: Snapshot, as_of: date, cfg: dict[str, Any]) -> list[str]:
    probs = list(snap.problems)
    for s in [p.bull for p in pairs(cfg)] + [p.bear for p in pairs(cfg)]:
        q = snap.equity_quotes.get(s)
        if q is None:
            probs.append(f"{s}: equity quote missing")
        elif q.state != "active":
            probs.append(f"{s}: instrument state {q.state}")
    if not snap.option_quotes:
        probs.append("no option quotes in snapshot")
    max_h = cfg["screener"]["max_proposal_quote_age_hours"]
    stale = [q for q in snap.option_quotes if (snap.captured_at - q.updated_at).total_seconds() / 3600 > max_h]
    if stale:
        probs.append(f"{len(stale)} option quotes older than {max_h}h")
    return probs


def _quote_index(snap: Snapshot) -> dict[str, OptionQuote]:
    return {q.instrument_id: q for q in snap.option_quotes}


def run_session(portfolios: dict[str, Portfolio], snap: Snapshot, cfg: dict[str, Any], now: datetime,
                bars: dict[str, pd.DataFrame] | None = None, auto_submit: bool = True) -> SessionResult:
    assert_paper_mode()
    as_of = snap.as_of
    bars = bars or {s: load_bars(s) for s in all_symbols(cfg)}
    regimes = {p.name: classify(p, bars, cfg["regime"], as_of) for p in pairs(cfg)}
    problems = validate_snapshot(snap, as_of, cfg)
    broker = PaperBroker(cfg)
    qidx = _quote_index(snap)
    iv_rv = {}
    for p in pairs(cfg):
        for s in p.etfs:
            rv = realized_vol(bars[s][bars[s]["date"] < as_of]["close"], 20)
            if len(rv.dropna()):
                iv_rv[s] = float(rv.iloc[-1])

    eligible, rejected = screen(snap.option_quotes, as_of, regimes, cfg, iv_rv)
    res = SessionResult(as_of, now, regimes, eligible, rejected, nearest_misses(rejected, cfg), data_problems=problems)
    res.entries_suspended = bool(problems)

    for pid, pf in portfolios.items():
        log: list[str] = []
        broker.expire_unfilled(pf, as_of)
        # ---- manage open positions
        for pos in pf.open_puts():
            q = qidx.get(pos.instrument_id or "")
            und = snap.equity_quotes.get(pos.symbol)
            exp = date.fromisoformat(pos.expiration)
            if und and exp < as_of:
                outcome = broker.settle_expiration(pf, pos, und.last, exp)
                log.append(f"{pos.symbol} {pos.strike:g}P {pos.expiration}: {outcome} (underlying {und.last})")
                continue
            if q is None or und is None:
                log.append(f"{pos.symbol} {pos.strike:g}P: [MISSING] no current quote — position preserved, not re-marked")
                continue
            broker.mark(pos, q)
            pair = pair_for_symbol(cfg, pos.symbol)
            rr = regimes.get(pair.name) if pair else None
            still = bool(rr and rr.trade_symbol == pos.symbol)
            acts = evaluate_position(pos.entry_credit, q.mark, exp, as_of, pos.strike, und.last, still, cfg["management"])
            for a in acts:
                log.append(f"{pos.symbol} {pos.strike:g}P: {a.action} — {a.reason}")
                if a.action == "FLAG" and a.reason not in pos.flags:
                    pos.flags.append(f"{as_of}: {a.reason}")
            if any(a.action == "CLOSE" for a in acts):
                fr = broker.close(pf, pos, q, now, "; ".join(a.reason for a in acts if a.action == "CLOSE"),
                                  snap.chains.get(pos.symbol))
                log.append(f"  close attempt: {fr.reason}")
        for sp in pf.shares:
            if sp.shares > 0 and sp.symbol in snap.equity_quotes:
                sp.last_price = snap.equity_quotes[sp.symbol].last
        res.management[pid] = log

        # ---- proposals
        props: list[Proposal] = []
        for c in eligible[: max(cfg["screener"]["top_n"] * 3, 6)]:
            fresh, _ = quote_is_fresh(c.quote, now, cfg["screener"]["max_quote_age_minutes"])
            dec = evaluate_entry(pf, c.quote.symbol, c.quote.strike, c.quote.multiplier, as_of, cfg,
                                 contracts=1, regime_confirmed=True, quote_fresh_for_fill=fresh,
                                 preference_flags=c.preference_flags, bars=bars)
            if res.entries_suspended:
                dec.vetoes.append("data/system problems: new simulated entries suspended")
                dec.verdict = Verdict.VETO
            props.append(Proposal(pid, c, dec))
        props.sort(key=lambda pr: ({"PASS": 0, "CONDITIONAL": 1, "VETO": 2}[pr.decision.verdict.value], -pr.candidate.score))
        if auto_submit and props and props[0].decision.verdict is Verdict.PASS:
            top = props[0]
            q = top.candidate.quote
            limit = max(q.bid, round(q.bid + 0.25 * (q.mid - q.bid), 2))
            o = broker.create_sell_intent(pf, q, 1, as_of, now, limit, top.decision.verdict.value,
                                          top.candidate.pair, top.candidate.group)
            fr = broker.try_fill_sell(pf, o, q, now, snap.chains.get(q.symbol))
            top.order_id, top.fill_status = o.order_id, fr.reason
        res.proposals[pid] = props[: cfg["screener"]["top_n"]]
        # Shadow proposals: what the remaining gates say if the regime gate were waived. Never submitted.
        shadow: list[Proposal] = []
        for c in res.misses:
            dec = evaluate_entry(pf, c.quote.symbol, c.quote.strike, c.quote.multiplier, as_of, cfg, contracts=1,
                                 regime_confirmed=True, quote_fresh_for_fill=False,
                                 preference_flags=c.preference_flags, bars=bars)
            shadow.append(Proposal(pid, c, dec, fill_status="ILLUSTRATIVE ONLY — regime gate waived, never submitted"))
        res.shadow[pid] = shadow
        bs = breaker_state(pf, as_of, cfg)
        if bs.halt and not pf.halted:
            pf.halted = True
        if bs.review:
            pf.review_required = True
        pf.record_equity(as_of, note="session")
        pf.risk_log.append({"date": as_of.isoformat(), "daily_dd": bs.daily_dd, "weekly_dd": bs.weekly_dd,
                            "peak_dd": bs.peak_dd, "notes": bs.notes})

    confirmed = [r for r in regimes.values() if r.regime is not Regime.NEUTRAL]
    if not eligible:
        res.headline = f"{NO_QUALIFIED_TRADE} — " + (
            "all regimes NEUTRAL; remaining in simulated cash" if not confirmed else "no contract met every mandatory requirement"
        )
    else:
        res.headline = f"{len(eligible)} contract(s) passed screening; see risk verdicts per portfolio"
    return res
