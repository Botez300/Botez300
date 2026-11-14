"""Daily LEGION paper-trading report (one dashboard per simulated portfolio)."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import pairs
from src.data.models import DataLabel as L
from src.paper.session import SessionResult
from src.portfolio.portfolio import Portfolio
from src.regime.classifier import Regime
from src.risk.engine import breaker_state

V, C, S, A, M = L.VERIFIED.tag, L.CALCULATED.tag, L.SIMULATED.tag, L.ASSUMPTION.tag, L.MISSING.tag


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _mtd_return(p: Portfolio, as_of: date) -> float:
    month = as_of.strftime("%Y-%m")
    prior = [r for r in p.equity_history if r["date"] < f"{month}-01"]
    base = (prior[-1]["equity"] - prior[-1].get("net_flows", 0)) if prior else p.starting_cash
    cur = p.equity() - p.net_external_flows()
    return cur / base - 1 if base else 0.0


def _max_dd(p: Portfolio) -> float:
    peak, mdd = p.starting_cash, 0.0
    for r in p.equity_history:
        e = r["equity"] - r.get("net_flows", 0)
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak else 0)
    return mdd


def _risk_quant(p: Portfolio, sess: SessionResult, cfg: dict[str, Any], underlying_px: dict[str, float]) -> list[str]:
    out = []
    pc = cfg["portfolios"][p.portfolio_id]
    cap = pc["max_collateral_per_contract_pct"] * p.risk_capital()
    out.append(f"Max collateral per contract right now: {_money(cap)} -> max strike ≈ ${cap / 100:,.2f} {C}.")
    etfs = [e for pr in pairs(cfg) for e in pr.etfs if e in underlying_px]
    affordable = [e for e in etfs if underlying_px[e] * 0.80 * 100 <= cap]
    if not affordable:
        out.append("No universe ETF is affordable at a typical 0.80x-spot strike: this account would remain in cash "
                   "even in a confirmed regime. This is a capital-size constraint, not a signal.")
    else:
        out.append(f"ETFs affordable at ~0.80x-spot strike: {', '.join(affordable)} {C}.")
    if all(r.regime is Regime.NEUTRAL for r in sess.regimes.values()):
        out.append("All regimes NEUTRAL: correct action is to hold simulated cash. No trade is the trade.")
    wide = [c for c in sess.rejected if any("spread" in x for x in c.rejections)]
    if wide:
        out.append(f"{len(wide)} contracts rejected for spreads beyond the hard limit {V}: end-of-session quotes are wide; "
                   "re-validate during regular hours before any simulated fill.")
    out.append("Structural risks: 3x daily-reset ETFs suffer volatility decay and can gap 15-30% overnight; a short put "
               "is long that gap risk. Drawdown breakers are operational controls, not loss limits.")
    out.append("5% monthly is a stretch research target only; position size is never increased to chase it.")
    return out


def render_portfolio(p: Portfolio, sess: SessionResult, cfg: dict[str, Any], underlying_px: dict[str, float]) -> str:
    as_of = sess.as_of
    bs = breaker_state(p, as_of, cfg)
    eq = p.equity()
    target = cfg["reports"]["monthly_stretch_target"]
    mtd = _mtd_return(p, as_of)
    cum = (eq - p.net_external_flows()) / p.starting_cash - 1
    lines = [
        f"## {p.name}  ·  PAPER",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Starting capital | {_money(p.starting_cash)} {S} |",
        f"| Current simulated equity | {_money(eq)} {S} |",
        f"| Available simulated cash (unencumbered) | {_money(p.unencumbered_cash())} {S} |",
        f"| Reserved collateral (incl. pending) | {_money(p.reserved_collateral())} {S} |",
        f"| Realized P&L | {_money(p.realized_pnl)} {S} |",
        f"| Unrealized option P&L | {_money(p.unrealized_option_pnl())} {S} |",
        f"| Month-to-date net return | {mtd:+.2%} {C} |",
        f"| Progress vs {target:.0%} monthly stretch objective | {mtd / target:.0%} of target {C} |",
        f"| Cumulative compounded return | {cum:+.2%} {C} |",
        f"| Maximum drawdown (paper history) | {_max_dd(p):.2%} {C} |",
        f"| Breakers: daily / weekly / from high | {bs.daily_dd:.2%} / {bs.weekly_dd:.2%} / {bs.peak_dd:.2%} {C} |",
        f"| Halted / review required | {p.halted} / {p.review_required} |",
        "",
        "### Open PAPER put positions",
    ]
    ops = p.open_puts()
    if not ops:
        lines.append("_None — 100% simulated cash._")
    else:
        lines += ["| Contract | Qty | Credit | Mark | Unrealized | Collateral | Flags |", "|---|---|---|---|---|---|---|"]
        for x in ops:
            lines.append(f"| {x.symbol} {x.expiration} {x.strike:g}P | {x.contracts} | {x.entry_credit:.2f} | "
                         f"{(x.last_mark or 0):.2f} | {_money(x.unrealized_pnl())} | {_money(x.collateral)} | {'; '.join(x.flags[-2:])} |")
    lines += ["", "### Assigned underlying shares"]
    sh = [s for s in p.shares if s.shares > 0]
    lines.append("_None._" if not sh else "\n".join(
        f"- {s.symbol}: {s.shares:g} sh, basis {s.cost_basis:.2f}, last {s.last_price} {S}" for s in sh))
    lines += ["", "### Simulated orders and fills (latest 5)"]
    od = p.orders[-5:]
    lines.append("_None._" if not od else "\n".join(
        f"- `{o.order_id}` {o.action} {o.symbol} {o.strike or ''} {o.expiration or ''} x{o.contracts} — {o.status}"
        f" {('@ ' + format(o.fill_price, '.2f')) if o.fill_price else ''} ({o.reason}) {S}" for o in od))
    lines += ["", "### Proposed PAPER positions (top 3) and risk-gate verdicts"]
    props = sess.proposals.get(p.portfolio_id, [])
    if not props:
        lines.append("**NO QUALIFIED TRADE** — no contract satisfied every mandatory screening requirement.")
    for pr in props:
        c, d = pr.candidate, pr.decision
        q = c.quote
        lines.append(f"- **{d.verdict.value}** · {c.label} · Δ {q.delta:+.3f} · bid {q.bid:.2f} / ask {q.ask:.2f} · "
                     f"mid credit {c.credit_mid:.2f} · collateral {_money(c.collateral_per_contract)} · OI {q.open_interest} {V}")
        for v in d.vetoes:
            lines.append(f"    - VETO: {v}")
        for cnd in d.conditions:
            lines.append(f"    - CONDITION: {cnd}")
        if pr.order_id:
            lines.append(f"    - Order `{pr.order_id}`: {pr.fill_status} {S}")
    sh = sess.shadow.get(p.portfolio_id, [])
    if sh:
        lines += ["", "### Shadow proposals — ILLUSTRATIVE ONLY (regime gate waived; not actionable, never submitted)"]
        for pr in sh:
            c, d = pr.candidate, pr.decision
            lines.append(f"- would be **{d.verdict.value}** · {c.label} · collateral {_money(c.collateral_per_contract)} vs "
                         f"max {_money(d.metrics.get('max_collateral_per_contract', 0))} {C}")
            for v in d.vetoes:
                lines.append(f"    - VETO: {v}")
            for cnd in d.conditions:
                lines.append(f"    - CONDITION: {cnd}")
    lines += ["", "### Management log"]
    ml = sess.management.get(p.portfolio_id, [])
    lines.append("_No open positions to manage._" if not ml else "\n".join(f"- {m}" for m in ml))
    lines += ["", "### Independent Risk Quant assessment"]
    lines += [f"- {x}" for x in _risk_quant(p, sess, cfg, underlying_px)]
    return "\n".join(lines)


def render_daily(portfolios: dict[str, Portfolio], sess: SessionResult, cfg: dict[str, Any],
                 underlying_px: dict[str, float]) -> str:
    out = [
        f"# LEGION QUANT CAPITAL — Daily PAPER Report · {sess.as_of.isoformat()}",
        "",
        "> **PAPER TRADING ONLY.** No live orders exist or can be created by this system. "
        f"Labels: {V} Verified market data · {C} Calculated indicator · {S} Simulated execution · "
        f"{A} Research assumption · {M} Missing/unverified data.",
        "",
        f"**Headline:** {sess.headline}",
        "",
    ]
    if sess.data_problems:
        out += ["**Data/system problems (new entries suspended):**"] + [f"- {M} {x}" for x in sess.data_problems] + [""]
    out += ["## Market regime (completed daily/weekly candles)", "",
            "| Pair | Regime | Trade ETF | Last bar | Bench vs SMA200 | SMA50>SMA200 | RSI d/w/m | Bull ETF trend | Bear ETF trend | RS bull/bear | Vol ratio | Notes |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pr in pairs(cfg):
        r = sess.regimes[pr.name]
        ck = r.checks
        if not ck:
            out.append(f"| {pr.name} | {r.regime.value} | — | — |  |  |  |  |  |  |  | {M} {'; '.join(r.reasons)} |")
            continue
        out.append(
            f"| {pr.name} ({pr.benchmark}) | **{r.regime.value}** {C} | {r.trade_symbol or '—'} | {r.bar_date} | "
            f"{ck['benchmark_close']:.2f} vs {ck['sma200']:.2f} | {ck['sma50_above_sma200']} | "
            f"{ck['rsi_daily']:.1f}/{ck['rsi_weekly']:.1f}/{ck['rsi_monthly'] if ck['rsi_monthly'] is not None else 'n/a'} | "
            f"{ck['bull_etf_uptrend']} | {ck['bear_etf_uptrend']} | {'+' if ck['rs_bull_vs_bear_above_sma'] else '-'} ({ck['rs_roc']:+.1%}) | "
            f"{ck['vol_ratio_vs_1y_median']:.2f} | {'; '.join(r.reasons)} |")
    out += ["", "## Underlying prices (last regular-session trade)", "",
            " · ".join(f"{s} {px:,.2f}" for s, px in underlying_px.items()) + f" {V}", ""]
    out += ["## Top eligible CSP opportunities (all portfolios)", ""]
    if not sess.eligible:
        out.append("**NO QUALIFIED TRADE.**")
        if sess.misses:
            out += ["", "Closest contracts that failed ONLY the regime gate (for transparency, NOT proposals):", "",
                    "| Contract | Δ | Bid | Ask | Spread % | OI | Collateral | Ann. yield (mid) |", "|---|---|---|---|---|---|---|---|"]
            for c in sess.misses:
                q = c.quote
                out.append(f"| {c.label} | {q.delta:+.3f} | {q.bid:.2f} | {q.ask:.2f} | {q.spread_pct:.0%} | {q.open_interest} | "
                           f"{_money(c.collateral_per_contract)} | {c.annualized_yield:.0%} |")
    else:
        out += ["| Rank | Contract | Score | Δ | Bid | Ask | Mid credit | OI | Collateral | Flags |", "|---|---|---|---|---|---|---|---|---|---|"]
        for i, c in enumerate(sess.eligible[: cfg["screener"]["top_n"]], 1):
            q = c.quote
            out.append(f"| {i} | {c.label} | {c.score:.3f} | {q.delta:+.3f} | {q.bid:.2f} | {q.ask:.2f} | {c.credit_mid:.2f} | "
                       f"{q.open_interest} | {_money(c.collateral_per_contract)} | {'; '.join(c.preference_flags) or '—'} |")
    reasons: dict[str, int] = {}
    cats = [("regime", "regime not confirmed"), ("DTE", "DTE outside window"), ("|delta|", "delta outside band"),
            ("spread", "spread > hard max"), ("OI ", "OI < hard floor"), ("bid", "no positive bid"),
            ("Greeks", "Greeks/IV missing"), ("ask", "invalid ask")]
    for c in sess.rejected:
        for r in c.rejections:
            key = next((lab for kw, lab in cats if kw in r), "other")
            reasons[key] = reasons.get(key, 0) + 1
    out += ["", f"Screened {len(sess.eligible) + len(sess.rejected)} verified put quotes; rejection reasons (count): "
            + ", ".join(f"{k.strip()} ×{v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])), ""]
    for pid, p in portfolios.items():
        out += [render_portfolio(p, sess, cfg, underlying_px), ""]
    return "\n".join(out)
