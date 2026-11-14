"""Reproducible historical backtest engine.

TWO MODES, NEVER MIXED:
  * HYPOTHETICAL (implemented, run here): underlying prices are verified
    Robinhood daily bars; option prices are SYNTHETIC (Black-Scholes with a
    realized-vol IV proxy, skew and spread assumptions). Results describe the
    rules' behaviour, not achievable historical fills.
  * HISTORICAL OPTIONS (adapter in src/backtest/chains.py): requires a dataset
    of real historical option quotes (bid/ask/delta/OI per day). None is
    available in this environment, so no such result is claimed.

Timing: signals use the close of day d (completed candle); all simulated
executions occur at the OPEN of day d+1 (captures overnight gaps). Expiration,
assignment and marks use day closes. Split events adjust open positions the
way OCC adjusts deliverables (strike x f, deliverable / f).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.config import Pair, pairs
from src.data.history import SplitEvent, detect_splits, load_bars
from src.options.pricing import bs_put, bs_put_delta, round_down_tick, round_up_tick, tick_for
from src.portfolio.portfolio import Portfolio, SharePosition, ShortPut, new_portfolio
from src.regime.classifier import regime_frame
from src.risk.engine import Verdict, evaluate_entry, two_contract_validation

MODE = "HYPOTHETICAL (synthetic option prices on verified underlying bars)"


@dataclass
class Trade:
    portfolio: str
    symbol: str
    pair: str
    entry_date: date
    expiration: date
    strike: float
    contracts: int
    deliverable: float
    entry_credit: float
    entry_iv: float
    entry_delta: float
    collateral: float
    exit_date: date | None = None
    exit_price: float | None = None
    outcome: str = "OPEN"
    option_pnl: float = 0.0
    share_pnl: float = 0.0
    fees: float = 0.0
    spread_cost: float = 0.0

    @property
    def pnl(self) -> float:
        return self.option_pnl + self.share_pnl - self.fees

    @property
    def days(self) -> int:
        return ((self.exit_date or self.entry_date) - self.entry_date).days


@dataclass
class BacktestResult:
    portfolio_id: str
    params: dict[str, Any]
    equity: pd.Series
    exposure: pd.Series
    collateral: pd.Series
    trades: list[Trade]
    events: list[str] = field(default_factory=list)
    mode: str = MODE


# --------------------------------------------------------------- market data
class MarketData:
    def __init__(self, cfg: dict[str, Any], base=None):
        self.cfg = cfg
        self.pairs: list[Pair] = pairs(cfg)
        syms: list[str] = []
        for p in self.pairs:
            syms += [p.benchmark, p.bull, p.bear]
        syms.append(cfg["universe"]["market_benchmark"])
        self.symbols = list(dict.fromkeys(syms))
        self.adj = {s: load_bars(s, "adjusted", base) for s in self.symbols}
        self.raw = {s: load_bars(s, "raw", base) for s in self.symbols}
        self.splits: dict[str, dict[date, float]] = {}
        for s in self.symbols:
            ev: list[SplitEvent] = detect_splits(self.raw[s], self.adj[s], s)
            self.splits[s] = {e.effective_date: e.price_factor for e in ev}
        self.dates: list[date] = sorted(set.intersection(*(set(df["date"]) for df in self.adj.values())))
        self.idx = {d: i for i, d in enumerate(self.dates)}
        self.o: dict[str, dict[date, float]] = {s: dict(zip(self.raw[s]["date"], self.raw[s]["open"])) for s in self.symbols}
        self.c: dict[str, dict[date, float]] = {s: dict(zip(self.raw[s]["date"], self.raw[s]["close"])) for s in self.symbols}
        self.rv: dict[str, dict[date, float]] = {}
        w = cfg["backtest"]["iv_model"]["rv_window"]
        for s in self.symbols:
            a = self.adj[s]
            lr = np.log(a["close"] / a["close"].shift(1))
            self.rv[s] = dict(zip(a["date"], (lr.rolling(w).std() * math.sqrt(252)).to_numpy()))
        self.regimes: dict[str, pd.DataFrame] = {}

    def regime_lookup(self, rcfg: dict[str, Any]) -> dict[str, dict[date, tuple[str, float]]]:
        key = str(sorted(rcfg.items()))
        if key not in self.regimes:
            out = {}
            for p in self.pairs:
                f = regime_frame(p, self.adj, rcfg)
                out[p.name] = dict(zip(f["date"], zip(f["regime"], f["strength"])))
            self.regimes[key] = out  # type: ignore[assignment]
        return self.regimes[key]  # type: ignore[return-value]


# --------------------------------------------------------------- option model
class SyntheticOptions:
    """HYPOTHETICAL option pricing. Every output is a research assumption."""

    def __init__(self, cfg: dict[str, Any]):
        m = cfg["backtest"]["iv_model"]
        self.ratio, self.floor, self.r = m["iv_rv_ratio"], m["iv_floor"], m["risk_free_rate"]
        self.skew_bull, self.skew_bear = m["skew_bull"], m["skew_bear"]
        self.bear_symbols = {p["bear"] for p in cfg["universe"]["pairs"]}
        sp = cfg["backtest"]["spread_model"]
        self.pct, self.minw = sp["pct_of_mid"], sp["min_width"]
        ex = cfg["execution"]
        self.a_sell, self.a_buy, self.slip = ex["sell_aggressiveness"], ex["buy_aggressiveness"], ex["slippage_ticks"]
        self.symbol: str | None = None

    def iv(self, rv: float, s: float, k: float, symbol: str | None = None) -> float:
        atm = max(self.floor, (rv if rv == rv else self.floor) * self.ratio)
        skew = self.skew_bear if (symbol or self.symbol) in self.bear_symbols else self.skew_bull
        return float(min(max(atm * (1.0 + skew * math.log(k / s)), self.floor), 3.0 * atm))

    def theo(self, s: float, k: float, t: float, rv: float, symbol: str | None = None) -> tuple[float, float, float]:
        sig = self.iv(rv, s, k, symbol)
        return bs_put(s, k, t, self.r, sig), bs_put_delta(s, k, t, self.r, sig), sig

    def half_width(self, theo: float) -> float:
        return max(self.minw / 2.0, self.pct * theo / 2.0)

    def sell_fill(self, theo: float) -> float:
        hw = self.half_width(theo)
        bid = max(theo - hw, 0.0)
        px = bid + self.a_sell * (theo - bid)
        tick = tick_for(px)
        return max(round_down_tick(px - self.slip * tick, tick), 0.0)

    def buy_fill(self, theo: float, intrinsic: float) -> float:
        hw = self.half_width(theo)
        ask = theo + hw
        px = ask - self.a_buy * (ask - theo)
        tick = tick_for(px)
        return max(round_up_tick(px + self.slip * tick, tick), intrinsic)


def _strike_grid(s: float) -> np.ndarray:
    step = 0.5 if s < 25 else 1.0 if s < 200 else 5.0
    lo, hi = math.floor(s * 0.40 / step) * step, math.ceil(s / step) * step
    return np.arange(max(step, lo), hi + step / 2, step)


def _expiry(d: date, dmin: int, dmax: int) -> date | None:
    """Friday expiry in [dmin, dmax] calendar days, closest to 30 DTE."""
    best = None
    for k in range(dmin, dmax + 1):
        e = d + timedelta(days=k)
        if e.weekday() == 4 and (best is None or abs(k - 30) < abs((best - d).days - 30)):
            best = e
    return best


# --------------------------------------------------------------- engine
def run_backtest(
    md: MarketData,
    cfg: dict[str, Any],
    portfolio_id: str,
    start: date,
    end: date,
    initial_cash: float | None = None,
    overrides: dict[str, Any] | None = None,
) -> BacktestResult:
    cfg = copy.deepcopy(cfg)
    ov = overrides or {}
    if "profit_target_pct" in ov:
        cfg["management"]["profit_target_pct"] = ov["profit_target_pct"]
    if "stop_action" in ov:
        cfg["management"]["stop_action"] = ov["stop_action"]
    if "require_monthly_rsi" in ov:
        cfg["regime"]["require_monthly_rsi"] = ov["require_monthly_rsi"]
    if "close_on_regime_loss" in ov:
        cfg["management"]["close_on_regime_loss"] = ov["close_on_regime_loss"]
    delta_target = ov.get("delta_target")

    pc = copy.deepcopy(cfg["portfolios"][portfolio_id])
    if initial_cash is not None:
        pc["starting_cash"] = initial_cash
    p: Portfolio = new_portfolio(portfolio_id, pc)
    mg, sc, ex = cfg["management"], cfg["screener"], cfg["execution"]
    opt = SyntheticOptions(cfg)
    regimes = md.regime_lookup(cfg["regime"])
    pair_by_sym = {s: pr for pr in md.pairs for s in (pr.bull, pr.bear)}
    fee = ex["fee_per_contract"]
    halt_days = cfg["backtest"]["halt_review_days"]

    dates = [d for d in md.dates if start <= d <= end]
    trades: list[Trade] = []
    open_trade: dict[str, Trade] = {}      # position_id -> trade
    pending_entry: dict[str, Any] | None = None
    pending_close: dict[str, str] = {}     # position_id -> reason
    pending_share_sales: list[SharePosition] = []
    eq_s, exp_s, col_s = {}, {}, {}
    events: list[str] = []
    halted_since: int | None = None
    validated_month: str | None = None

    for i, d in enumerate(dates):
        # 1) splits effective today (raw open already reflects them)
        for pos in p.open_puts():
            f = md.splits[pos.symbol].get(d)
            if f:
                # OCC-style adjustment: per-share quantities scale by f, deliverable by 1/f,
                # so strike x deliverable and premium x deliverable are unchanged.
                pos.strike *= f
                pos.deliverable = pos.shares_per_contract / f
                pos.entry_credit *= f
                if pos.last_mark is not None:
                    pos.last_mark *= f
                if pos.position_id in open_trade:
                    tr = open_trade[pos.position_id]
                    tr.strike, tr.entry_credit, tr.deliverable = pos.strike, pos.entry_credit, pos.deliverable
                events.append(f"{d}: split x{f:g} adjusted open put {pos.symbol}")
        for sp in p.shares:
            f = md.splits[sp.symbol].get(d)
            if f and sp.shares > 0:
                sp.shares /= f
                sp.cost_basis *= f

        # 2) executions at today's open
        for sp in pending_share_sales:
            px = md.o[sp.symbol][d]
            tr = next((t for t in trades if t.outcome == "ASSIGNED" and t.symbol == sp.symbol and t.exit_date and t.share_pnl == 0.0), None)
            pnl = (px - sp.cost_basis) * sp.shares
            p.cash += px * sp.shares
            p.realized_pnl += pnl
            if tr:
                tr.share_pnl = pnl
            sp.shares = 0.0
        pending_share_sales = []
        p.shares = [s for s in p.shares if s.shares > 0]

        for pid, reason in list(pending_close.items()):
            pos = next((x for x in p.open_puts() if x.position_id == pid), None)
            if pos is None:
                continue
            s_open = md.o[pos.symbol][d]
            t = max((date.fromisoformat(pos.expiration) - d).days, 0) / 365.0
            theo, _, _ = opt.theo(s_open, pos.strike, t, md.rv[pos.symbol].get(md.dates[md.idx[d] - 1], float("nan")), pos.symbol)
            px = opt.buy_fill(theo, max(pos.strike - s_open, 0.0))
            n = pos.shares_per_contract * pos.contracts
            p.cash -= px * n + fee * pos.contracts
            p.fees_paid += fee * pos.contracts
            pos.status, pos.close_price, pos.close_date = "CLOSED", px, d.isoformat()
            pos.realized_pnl = (pos.entry_credit - px) * n - pos.entry_fees - fee * pos.contracts
            p.realized_pnl += pos.realized_pnl
            tr = open_trade.pop(pid)
            tr.exit_date, tr.exit_price, tr.outcome = d, px, reason
            tr.option_pnl = (tr.entry_credit - px) * n
            tr.fees += fee * pos.contracts
            tr.spread_cost += (px - theo) * n
        pending_close = {}

        if pending_entry is not None:
            pe = pending_entry
            pending_entry = None
            s_open = md.o[pe["symbol"]][d]
            t = (pe["expiration"] - d).days / 365.0
            theo, dl, sig = opt.theo(s_open, pe["strike"], t, pe["rv"], pe["symbol"])
            credit = opt.sell_fill(theo)
            dec = evaluate_entry(p, pe["symbol"], pe["strike"], 100, d, cfg, contracts=pe["contracts"],
                                 regime_confirmed=True, quote_fresh_for_fill=True,
                                 bars={k: md.adj[k][md.adj[k]["date"] < d] for k in (pe["symbol"],)})
            band = sc["delta_bands"][pe["group"]]
            if credit <= 0.0:
                events.append(f"{d}: entry skipped — synthetic bid not positive")
            elif dec.verdict is Verdict.VETO:
                events.append(f"{d}: entry vetoed at open — {dec.vetoes[0]}")
            elif not (band[0] * 0.75 <= abs(dl) <= band[1] * 1.5):
                events.append(f"{d}: entry skipped — gap moved delta to {abs(dl):.2f}")
            else:
                n = 100 * pe["contracts"]
                p.cash += credit * n - fee * pe["contracts"]
                p.fees_paid += fee * pe["contracts"]
                pos = ShortPut(f"BT-{portfolio_id}-{i}", pe["symbol"], pe["expiration"].isoformat(), pe["strike"],
                               pe["contracts"], 100, credit, d.isoformat(), fee * pe["contracts"], f"BT-ORD-{i}",
                               pair=pe["pair"], group=pe["group"], last_mark=theo)
                p.puts.append(pos)
                tr = Trade(portfolio_id, pe["symbol"], pe["pair"], d, pe["expiration"], pe["strike"], pe["contracts"],
                           100.0, credit, sig, dl, pos.collateral, fees=fee * pe["contracts"], spread_cost=(theo - credit) * n)
                trades.append(tr)
                open_trade[pos.position_id] = tr

        # 3) marks, expiration, early assignment at today's close
        for pos in p.open_puts():
            s_close = md.c[pos.symbol][d]
            exp_d = date.fromisoformat(pos.expiration)
            nxt = dates[i + 1] if i + 1 < len(dates) else None
            t = max((exp_d - d).days, 0) / 365.0
            theo, dl, _ = opt.theo(s_close, pos.strike, t, md.rv[pos.symbol].get(d, float("nan")), pos.symbol)
            pos.last_mark = theo
            settle = exp_d <= d or (nxt is not None and nxt > exp_d)
            early = (s_close < pos.strike and (exp_d - d).days <= 5
                     and theo - (pos.strike - s_close) < mg["early_assignment_extrinsic"])
            if settle or early:
                tr = open_trade.pop(pos.position_id)
                n = pos.shares_per_contract * pos.contracts
                if s_close >= pos.strike and not early:
                    pos.status, pos.close_price, pos.close_date = "EXPIRED", 0.0, d.isoformat()
                    pos.realized_pnl = pos.entry_credit * n - pos.entry_fees
                    p.realized_pnl += pos.realized_pnl
                    tr.exit_date, tr.exit_price, tr.outcome, tr.option_pnl = d, 0.0, "EXPIRED", tr.entry_credit * n
                else:
                    p.cash -= pos.strike * n
                    pos.status, pos.close_date = "ASSIGNED", d.isoformat()
                    pos.realized_pnl = pos.entry_credit * n - pos.entry_fees
                    p.realized_pnl += pos.realized_pnl
                    sp = SharePosition(pos.symbol, n, pos.strike, d.isoformat(), pos.position_id, s_close)
                    p.shares.append(sp)
                    tr.exit_date, tr.exit_price = d, max(pos.strike - s_close, 0.0)
                    tr.outcome = "ASSIGNED"
                    tr.option_pnl = tr.entry_credit * n
                    events.append(f"{d}: {'EARLY ' if early else ''}assignment {pos.symbol} {pos.strike:g}P, {n:g} sh")
                    if mg["assigned_shares_policy"] == "liquidate_next_open":
                        pending_share_sales.append(sp)
        for sp in p.shares:
            sp.last_price = md.c[sp.symbol][d]
            if mg["assigned_shares_policy"] == "hold_until_regime_exit" and sp.shares > 0:
                pr = pair_by_sym[sp.symbol]
                reg, _ = regimes[pr.name].get(d, ("NEUTRAL", 0.0))
                want = pr.bull if reg == "BULLISH" else pr.bear if reg == "BEARISH" else None
                if want != sp.symbol and sp not in pending_share_sales:
                    pending_share_sales.append(sp)

        p.record_equity(d)
        eq = p.equity()
        eq_s[d], exp_s[d], col_s[d] = eq, float(bool(p.open_puts())), p.reserved_collateral(False)

        # breaker halt handling (stand-in for manual review)
        if not p.halted and p.high_water_mark > 0 and (p.high_water_mark - eq) / p.high_water_mark >= cfg["risk"]["peak_drawdown_halt"]:
            p.halted, halted_since = True, i
            events.append(f"{d}: 8% drawdown HALT (equity {eq:,.0f}, high {p.high_water_mark:,.0f})")
        if p.halted and halted_since is not None and i - halted_since >= halt_days:
            p.halted, halted_since = False, None
            p.high_water_mark = eq
            events.append(f"{d}: simulated risk review complete, halt cleared, equity high reset")

        if i + 1 >= len(dates):
            break  # no next open to act on

        # 4) decisions at close for next open
        for pos in p.open_puts():
            pr = pair_by_sym[pos.symbol]
            reg, _ = regimes[pr.name].get(d, ("NEUTRAL", 0.0))
            want = pr.bull if reg == "BULLISH" else pr.bear if reg == "BEARISH" else None
            exp_d = date.fromisoformat(pos.expiration)
            dte = (exp_d - d).days
            retained = (pos.entry_credit - pos.last_mark) / pos.entry_credit if pos.entry_credit > 0 else 0
            reason = None
            if retained >= mg["profit_target_pct"]:
                reason = "PROFIT_TARGET"
            elif dte <= mg["reassess_dte"]:
                reason = "DTE_EXIT"
            elif pos.last_mark >= mg["stop_flag_multiple"] * pos.entry_credit and mg["stop_action"] == "close":
                reason = "STOP_2X"
            elif want != pos.symbol and mg["close_on_regime_loss"]:
                reason = "REGIME_EXIT"
            if reason:
                pending_close[pos.position_id] = reason

        ym = d.strftime("%Y-%m")
        if portfolio_id == "B" and ym != validated_month:
            validated_month = ym
            p.validated_two_contracts = two_contract_validation(p, cfg)[0]

        max_c = pc["max_contracts_if_validated"] if p.validated_two_contracts else pc["max_open_contracts"]
        open_n = sum(x.contracts for x in p.open_puts()) - sum(1 for k in pending_close)
        if p.halted or open_n >= max_c or p.shares:
            continue
        held = {x.symbol for x in p.open_puts()}
        best = None
        for pr in md.pairs:
            reg, strength = regimes[pr.name].get(d, ("NEUTRAL", 0.0))
            if reg == "NEUTRAL":
                continue
            sym = pr.bull if reg == "BULLISH" else pr.bear
            opp = pr.bear if sym == pr.bull else pr.bull
            if sym in held or opp in held:
                continue
            s_close = md.c[sym][d]
            rv = md.rv[sym].get(d, float("nan"))
            if rv != rv:
                continue
            nxt = dates[i + 1]
            exp_d = _expiry(nxt, sc["dte_min"], sc["dte_max"])
            if exp_d is None:
                continue
            band = sc["delta_bands"][pr.group]
            tgt = delta_target if delta_target is not None else (band[0] + band[1]) / 2
            if pr.group == "semis" and delta_target is not None:
                tgt = min(max(delta_target * 0.77, band[0]), band[1])  # scale broad target into semis band
            t = (exp_d - d).days / 365.0
            cap = pc["max_collateral_per_contract_pct"] * p.risk_capital()
            pick = None
            for k in _strike_grid(s_close):
                if k * 100 > cap:
                    continue
                theo, dl, sig = opt.theo(s_close, k, t, rv, sym)
                if band[0] <= abs(dl) <= band[1] and theo > 0:
                    if pick is None or abs(abs(dl) - tgt) < abs(abs(pick[1]) - tgt):
                        pick = (k, dl, theo, sig)
            if pick is None:
                continue
            score = strength + 0.5 * (pick[2] / pick[0]) * 365 / max((exp_d - d).days, 1)
            if best is None or score > best[0]:
                best = (score, {"symbol": sym, "pair": pr.name, "group": pr.group, "strike": float(pick[0]),
                                "expiration": exp_d, "contracts": 1, "rv": rv})
        if best is not None:
            pe = best[1]
            dec = evaluate_entry(p, pe["symbol"], pe["strike"], 100, d, cfg, contracts=1, regime_confirmed=True,
                                 quote_fresh_for_fill=True)
            if dec.verdict is not Verdict.VETO:
                pending_entry = pe

    # mark-to-market liquidation of anything still open at the end
    last = dates[-1] if dates else end
    for pos in p.open_puts():
        tr = open_trade.pop(pos.position_id, None)
        if tr:
            n = pos.shares_per_contract * pos.contracts
            tr.exit_date, tr.exit_price, tr.outcome = last, pos.last_mark, "OPEN_AT_END(marked)"
            tr.option_pnl = (tr.entry_credit - (pos.last_mark or 0)) * n
    for sp in p.shares:
        tr = next((t for t in trades if t.outcome == "ASSIGNED" and t.symbol == sp.symbol and t.share_pnl == 0.0), None)
        if tr and sp.shares > 0:
            tr.share_pnl = (md.c[sp.symbol][last] - sp.cost_basis) * sp.shares

    return BacktestResult(
        portfolio_id,
        {"delta_target": delta_target, **{k: v for k, v in ov.items() if k != "delta_target"},
         "profit_target_pct": mg["profit_target_pct"], "stop_action": mg["stop_action"],
         "require_monthly_rsi": cfg["regime"]["require_monthly_rsi"], "start": str(start), "end": str(end),
         "initial_cash": pc["starting_cash"]},
        pd.Series(eq_s, dtype=float),
        pd.Series(exp_s, dtype=float),
        pd.Series(col_s, dtype=float),
        trades,
        events,
    )
