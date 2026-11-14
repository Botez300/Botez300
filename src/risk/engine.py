"""Simulated collateral, concentration, correlation and drawdown gates.

Every new simulated position AND every adjustment passes through
``evaluate_entry``. Verdicts: PASS, CONDITIONAL, VETO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from src.config import pair_for_symbol
from src.portfolio.portfolio import Portfolio
from src.safety import assert_paper_mode


class Verdict(str, Enum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    VETO = "VETO"


@dataclass
class RiskDecision:
    verdict: Verdict
    max_contracts: int
    vetoes: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class BreakerState:
    daily_dd: float
    weekly_dd: float
    peak_dd: float
    suspend: bool
    review: bool
    halt: bool
    notes: list[str] = field(default_factory=list)


def drawdowns(history: list[dict[str, Any]], current_equity: float, as_of: date, hwm: float) -> tuple[float, float, float]:
    """Flow-adjusted daily, weekly and peak drawdowns (positive numbers = loss)."""
    def _adj(row: dict[str, Any]) -> float:
        return row["equity"] - row.get("net_flows", 0.0)

    cur_flows = history[-1].get("net_flows", 0.0) if history else 0.0
    cur = current_equity - cur_flows
    as_iso, wk_iso = as_of.isoformat(), (as_of - timedelta(days=7)).isoformat()
    # ISO dates sort lexicographically; scan backwards (history is date-sorted).
    prior: list[dict[str, Any]] = []
    for r in reversed(history):
        if r["date"] >= as_iso:
            continue
        if r["date"] < wk_iso:
            if not prior:
                prior.append(r)  # older than a week: still the daily reference
            break
        prior.append(r)
    daily_ref = _adj(prior[0]) if prior else cur
    wk = [r for r in prior if r["date"] >= wk_iso]
    weekly_ref = max([_adj(r) for r in wk] + [daily_ref]) if wk else daily_ref
    peak_ref = max(hwm - cur_flows, cur)
    dd = lambda ref: max(0.0, (ref - cur) / ref) if ref > 0 else 0.0  # noqa: E731
    return dd(daily_ref), dd(weekly_ref), dd(peak_ref)


def breaker_state(p: Portfolio, as_of: date, cfg: dict[str, Any]) -> BreakerState:
    rc = cfg["risk"]
    d, w, pk = drawdowns(p.equity_history, p.equity(), as_of, p.high_water_mark)
    st = BreakerState(d, w, pk, d >= rc["daily_drawdown_suspend"], w >= rc["weekly_drawdown_review"], pk >= rc["peak_drawdown_halt"])
    if st.suspend:
        st.notes.append(f"daily drawdown {d:.2%} >= {rc['daily_drawdown_suspend']:.0%}: new entries suspended")
    if st.review:
        st.notes.append(f"weekly drawdown {w:.2%} >= {rc['weekly_drawdown_review']:.0%}: entries suspended, risk review required")
    if st.halt:
        st.notes.append(f"drawdown from equity high {pk:.2%} >= {rc['peak_drawdown_halt']:.0%}: HALT pending review")
    return st


def return_correlation(a: pd.DataFrame, b: pd.DataFrame, window: int) -> float | None:
    m = a[["date", "close"]].merge(b[["date", "close"]], on="date", suffixes=("_a", "_b")).tail(window + 1)
    if len(m) < window // 2:
        return None
    ra = np.log(m["close_a"]).diff().dropna()
    rb = np.log(m["close_b"]).diff().dropna()
    return float(np.corrcoef(ra, rb)[0, 1])


def evaluate_entry(
    p: Portfolio,
    symbol: str,
    strike: float,
    multiplier: int,
    as_of: date,
    cfg: dict[str, Any],
    *,
    contracts: int = 1,
    regime_confirmed: bool,
    quote_fresh_for_fill: bool,
    preference_flags: list[str] | None = None,
    bars: dict[str, pd.DataFrame] | None = None,
) -> RiskDecision:
    assert_paper_mode()
    pc = cfg["portfolios"][p.portfolio_id]
    rc = cfg["risk"]
    vetoes: list[str] = []
    conds: list[str] = list(preference_flags or [])

    equity = p.equity()
    capital = p.risk_capital()
    coll_one = strike * multiplier
    max_contracts_allowed = pc["max_contracts_if_validated"] if p.validated_two_contracts else pc["max_open_contracts"]
    open_n = p.open_contracts(include_pending=True)
    multi = (open_n + contracts) > 1
    per_pct = pc["max_collateral_per_contract_pct_multi"] if multi else pc["max_collateral_per_contract_pct"]

    if not regime_confirmed:
        vetoes.append("market regime not confirmed for this ETF")
    if p.halted or p.review_required:
        vetoes.append("portfolio halted / awaiting risk review")
    bs = breaker_state(p, as_of, cfg)
    if bs.suspend or bs.review or bs.halt:
        vetoes.extend(bs.notes)
    if open_n + contracts > max_contracts_allowed:
        vetoes.append(f"contract limit: {open_n} open/pending + {contracts} > {max_contracts_allowed}")
    if coll_one > per_pct * capital:
        vetoes.append(
            f"collateral/contract ${coll_one:,.0f} > {per_pct:.0%} of risk capital ${capital:,.0f} (${per_pct * capital:,.0f})"
        )
    total_after = p.reserved_collateral(True) + coll_one * contracts
    if total_after > pc["max_total_collateral_pct"] * capital:
        vetoes.append(f"total collateral ${total_after:,.0f} > {pc['max_total_collateral_pct']:.0%} of risk capital")
    unenc_after = p.cash - total_after
    if unenc_after < pc["min_unencumbered_cash_pct"] * equity:
        vetoes.append(
            f"unencumbered cash after entry ${unenc_after:,.0f} < {pc['min_unencumbered_cash_pct']:.0%} of equity"
        )
    if p.cash < total_after:
        vetoes.append("insufficient cash to fully secure the put (no margin permitted)")

    # Conflicts: same symbol or opposing ETF (positions, pending orders, assigned shares)
    pair = pair_for_symbol(cfg, symbol)
    held = {x.symbol for x in p.open_puts()} | {o.symbol for o in p.pending_orders()} | {s.symbol for s in p.shares if s.shares > 0}
    if symbol in held:
        vetoes.append(f"conflicting simulated order/holding already exists in {symbol}")
    if pair and not cfg["universe"]["allow_opposing_pair_positions"]:
        opp = pair.bear if symbol == pair.bull else pair.bull
        if opp in held:
            vetoes.append(f"opposing ETF {opp} held: simultaneous bull/bear puts not validated")

    # Correlation for any second simultaneous position
    corr_val = None
    if bars and held - {symbol}:
        for other in held - {symbol}:
            if other in bars and symbol in bars:
                c = return_correlation(bars[symbol], bars[other], rc["correlation_window"])
                if c is not None:
                    corr_val = c if corr_val is None else max(corr_val, c)
                    if c > rc["max_pair_correlation"]:
                        vetoes.append(f"return correlation {symbol}/{other} {c:.2f} > {rc['max_pair_correlation']:.2f}")

    if not quote_fresh_for_fill:
        conds.append("quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill")

    by_coll = int((per_pct * capital) // coll_one) if coll_one > 0 else 0
    max_c = max(0, min(max_contracts_allowed - open_n, by_coll))
    verdict = Verdict.VETO if vetoes else (Verdict.CONDITIONAL if conds else Verdict.PASS)
    return RiskDecision(
        verdict,
        max_c if verdict is not Verdict.VETO else 0,
        vetoes,
        conds,
        {
            "equity": round(equity, 2),
            "risk_capital": round(capital, 2),
            "collateral_per_contract": round(coll_one, 2),
            "max_collateral_per_contract": round(per_pct * capital, 2),
            "reserved_after": round(total_after, 2),
            "unencumbered_after": round(unenc_after, 2),
            "daily_dd": round(bs.daily_dd, 4),
            "weekly_dd": round(bs.weekly_dd, 4),
            "peak_dd": round(bs.peak_dd, 4),
            **({"max_correlation": round(corr_val, 3)} if corr_val is not None else {}),
        },
    )


def two_contract_validation(p: Portfolio, cfg: dict[str, Any]) -> tuple[bool, list[str]]:
    """Portfolio B may hold two contracts only after paper validation."""
    u = cfg["risk"]["two_contract_unlock"]
    closed = [x for x in p.puts if x.status != "OPEN" and x.realized_pnl is not None]
    msgs: list[str] = []
    ok = True
    if len(closed) < u["min_closed_trades"]:
        ok = False
        msgs.append(f"closed paper trades {len(closed)} < {u['min_closed_trades']}")
    if p.equity_history:
        first = date.fromisoformat(p.equity_history[0]["date"])
        last = date.fromisoformat(p.equity_history[-1]["date"])
        months = (last - first).days / 30.4
        if months < u["min_months"]:
            ok = False
            msgs.append(f"paper history {months:.1f} months < {u['min_months']}")
    else:
        ok = False
        msgs.append("no paper equity history")
    eqs = [r["equity"] for r in p.equity_history]
    if eqs:
        peak, mdd = eqs[0], 0.0
        for e in eqs:
            peak = max(peak, e)
            mdd = max(mdd, (peak - e) / peak)
        if mdd > u["max_drawdown"]:
            ok = False
            msgs.append(f"max drawdown {mdd:.2%} > {u['max_drawdown']:.0%}")
    gains = sum(x.realized_pnl for x in closed if x.realized_pnl > 0)
    losses = -sum(x.realized_pnl for x in closed if x.realized_pnl < 0)
    pf = gains / losses if losses > 0 else (float("inf") if gains > 0 else 0.0)
    if pf < u["min_profit_factor"]:
        ok = False
        msgs.append(f"profit factor {pf:.2f} < {u['min_profit_factor']}")
    return ok, msgs
