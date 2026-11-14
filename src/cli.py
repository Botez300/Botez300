"""LEGION CSP Engine command line (PAPER ONLY).

    python -m src.cli <command> [options]

Commands: status, regime, scan, rank, order, fill, manage, run-daily, backtest,
project, risk-audit, report, reset, import-history, validate-b, safety-check.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from src import safety
from src.broker.robinhood_mcp import import_equity_historicals, latest_snapshot_dir, load_snapshot
from src.config import ROOT, all_symbols, load_config, pairs
from src.data.history import load_bars
from src.paper.broker import PaperBroker
from src.paper.session import run_session
from src.portfolio import portfolio as store
from src.reports.daily import render_daily
from src.reports.performance import render_periodic
from src.reports.projections import projection_table
from src.regime.classifier import classify
from src.risk.engine import breaker_state, evaluate_entry, two_contract_validation

REPORTS = ROOT / "reports"
PIDS = ("A", "B")


def _now(args: argparse.Namespace) -> datetime:
    if getattr(args, "now", None):
        return datetime.fromisoformat(args.now).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _snap(args: argparse.Namespace):
    d = Path(args.snapshot) if getattr(args, "snapshot", None) else latest_snapshot_dir()
    if d is None:
        sys.exit("No snapshot found. Capture one via Claude Code (see README 'Daily runbook').")
    return load_snapshot(d)


def _portfolios(cfg, which: str | None = None):
    ids = [which] if which else list(PIDS)
    return {pid: store.load(pid, cfg) for pid in ids}


def cmd_status(args, cfg):
    for pid, p in _portfolios(cfg, args.portfolio).items():
        print(f"[{p.label}] {p.name}")
        print(f"  equity ${p.equity():,.2f} | cash ${p.cash:,.2f} | unencumbered ${p.unencumbered_cash():,.2f} | "
              f"reserved ${p.reserved_collateral():,.2f} | realized ${p.realized_pnl:,.2f}")
        print(f"  open puts {len(p.open_puts())} | pending orders {len(p.pending_orders())} | shares "
              f"{[(s.symbol, s.shares) for s in p.shares if s.shares > 0]} | halted {p.halted} | review {p.review_required}")


def cmd_regime(args, cfg):
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    bars = {s: load_bars(s) for s in all_symbols(cfg)}
    for pr in pairs(cfg):
        r = classify(pr, bars, cfg["regime"], as_of)
        print(f"{pr.name:10s} {r.regime.value:8s} trade={r.trade_symbol} bar={r.bar_date} strength={r.strength:.2f} "
              f"reasons={r.reasons}")
        if args.verbose:
            print("   ", json.dumps(r.checks))


def _session(args, cfg, auto_submit: bool):
    snap = _snap(args)
    pfs = _portfolios(cfg)
    res = run_session(pfs, snap, cfg, _now(args), auto_submit=auto_submit)
    return snap, pfs, res


def cmd_scan(args, cfg):
    snap = _snap(args)
    pfs = {pid: store.load(pid, cfg) for pid in PIDS}
    res = run_session({k: v for k, v in pfs.items()}, snap, cfg, _now(args), auto_submit=False)
    print(res.headline)
    for c in res.eligible[: args.top]:
        print(f"  ELIGIBLE {c.label} score={c.score:.3f} delta={c.quote.delta:+.3f} bid={c.quote.bid} ask={c.quote.ask} "
              f"OI={c.quote.open_interest} flags={c.preference_flags}")
    if not res.eligible:
        for c in res.misses:
            print(f"  (regime-only miss) {c.label} delta={c.quote.delta:+.3f} bid={c.quote.bid} ask={c.quote.ask}")
    # scan is read-only: do NOT persist session side effects
    return res


def cmd_rank(args, cfg):
    _, _, res = _session(args, cfg, auto_submit=False)
    for pid, props in res.proposals.items():
        print(f"Portfolio {pid}:")
        if not props:
            print("  NO QUALIFIED TRADE")
        for pr in props:
            print(f"  {pr.decision.verdict.value:11s} {pr.candidate.label} score={pr.candidate.score:.3f} "
                  f"vetoes={pr.decision.vetoes} conditions={pr.decision.conditions}")


def cmd_order(args, cfg):
    """Create a PAPER sell-to-open intent for one instrument after the full risk gate."""
    safety.assert_paper_mode()
    snap = _snap(args)
    p = store.load(args.portfolio, cfg)
    q = next((x for x in snap.option_quotes if x.instrument_id == args.instrument), None)
    if q is None:
        sys.exit("instrument not in snapshot")
    bars = {s: load_bars(s) for s in all_symbols(cfg)}
    pair = next(pr for pr in pairs(cfg) if q.symbol in pr.etfs)
    rr = classify(pair, bars, cfg["regime"], snap.as_of)
    from src.paper.fills import quote_is_fresh
    fresh, why = quote_is_fresh(q, _now(args), cfg["screener"]["max_quote_age_minutes"])
    dec = evaluate_entry(p, q.symbol, q.strike, q.multiplier, snap.as_of, cfg, contracts=args.contracts,
                         regime_confirmed=rr.trade_symbol == q.symbol, quote_fresh_for_fill=fresh, bars=bars)
    print(f"verdict={dec.verdict.value} vetoes={dec.vetoes} conditions={dec.conditions}")
    if dec.verdict.value == "VETO":
        sys.exit(2)
    o = PaperBroker(cfg).create_sell_intent(p, q, args.contracts, snap.as_of, _now(args), args.limit or q.bid,
                                            dec.verdict.value, pair.name, pair.group)
    store.save(p)
    print(f"[PAPER] intent {o.order_id} status={o.status} (fill requires a fresh RTH quote: {why})")


def cmd_fill(args, cfg):
    snap = _snap(args)
    qidx = {q.instrument_id: q for q in snap.option_quotes}
    br = PaperBroker(cfg)
    for pid, p in _portfolios(cfg).items():
        for o in p.pending_orders():
            q = qidx.get(o.instrument_id or "")
            if q is None:
                print(f"{pid} {o.order_id}: no quote in snapshot")
                continue
            r = br.try_fill_sell(p, o, q, _now(args), snap.chains.get(q.symbol))
            print(f"[PAPER] {pid} {o.order_id}: {r.reason}")
        store.save(p)


def cmd_run_daily(args, cfg):
    snap, pfs, res = _session(args, cfg, auto_submit=not args.no_submit)
    for p in pfs.values():
        store.save(p)
    px = {s: q.last for s, q in snap.equity_quotes.items()}
    md = render_daily(pfs, res, cfg, px)
    out = REPORTS / "daily" / f"{snap.as_of.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    (REPORTS / "daily" / "LATEST.md").write_text(md)
    print(res.headline)
    print(f"report: {out}")


def cmd_manage(args, cfg):
    # Management runs inside the session (marks, rules, closes, expirations) without new entries.
    snap, pfs, res = _session(args, cfg, auto_submit=False)
    for pid, log in res.management.items():
        print(f"Portfolio {pid}:")
        for m in log or ["no open positions"]:
            print("  " + m)
        store.save(pfs[pid])


def cmd_backtest(args, cfg):
    from src.backtest.research import run_research
    res = run_research(cfg, walk=not args.no_walk)
    for k, v in res["baseline"].items():
        if "baseline" in k:
            print(k, {m: round(v.get(m, 0), 4) for m in ("cagr", "avg_monthly_return", "max_drawdown", "sharpe", "trades")})
    print("report: reports/backtest/BACKTEST_REPORT.md")


def cmd_project(args, cfg):
    t = projection_table([5000, 10000], cfg["reports"]["projection_rates"], cfg["reports"]["projection_years"])
    print("MATHEMATICAL SCENARIOS, NOT FORECASTS")
    print(t.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


def cmd_risk_audit(args, cfg):
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    ok = cmd_safety_check(args, cfg, quiet=True)
    for pid, p in _portfolios(cfg).items():
        bs = breaker_state(p, as_of, cfg)
        pc = cfg["portfolios"][pid]
        print(f"{p.name}: equity ${p.equity():,.2f} risk-capital ${p.risk_capital():,.2f}")
        print(f"  reserved ${p.reserved_collateral():,.2f} ({p.reserved_collateral() / max(p.equity(), 1):.1%}, limit "
              f"{pc['max_total_collateral_pct']:.0%}) | unencumbered {p.unencumbered_cash() / max(p.equity(), 1):.1%} "
              f"(min {pc['min_unencumbered_cash_pct']:.0%})")
        print(f"  drawdown daily {bs.daily_dd:.2%} weekly {bs.weekly_dd:.2%} from-high {bs.peak_dd:.2%} | {bs.notes or 'no breaker tripped'}")
        for x in p.open_puts():
            if p.cash < x.collateral:
                print(f"  !! {x.symbol} put not fully cash-secured")
        if pid == "B":
            v, msgs = two_contract_validation(p, cfg)
            print(f"  two-contract unlock: {v} {msgs}")
    print(f"safety checks: {'PASS' if ok else 'FAIL'}")


def cmd_safety_check(args, cfg, quiet: bool = False) -> bool:
    import re
    problems = []
    if safety.PAPER_TRADING is not True or safety.LIVE_TRADING is not False:
        problems.append("execution constants altered")
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    deny = set(settings.get("permissions", {}).get("deny", []))
    for t in ("place_option_order", "place_equity_order", "cancel_option_order", "exercise_option"):
        if f"mcp__Robinhood_Agentic_Trading__{t}" not in deny:
            problems.append(f"Claude Code deny-list missing {t}")
    pat = re.compile(r"\b(place|cancel|review|exercise|decline)_(option|equity|crypto|advanced)_?\w*\(")
    for f in (ROOT / "src").rglob("*.py"):
        if f.name == "safety.py":
            continue
        if pat.search(f.read_text()):
            problems.append(f"possible order-tool call in {f}")
    if not quiet:
        print("PAPER_TRADING =", safety.PAPER_TRADING, "| LIVE_TRADING =", safety.LIVE_TRADING)
        print("problems:", problems or "none")
    return not problems


def cmd_report(args, cfg):
    pfs = _portfolios(cfg)
    if args.kind == "daily":
        p = REPORTS / "daily" / "LATEST.md"
        print(p.read_text() if p.exists() else "No daily report yet; run `run-daily`.")
        return
    rule = {"weekly": "W-FRI", "monthly": "ME"}[args.kind]
    md = render_periodic(pfs, rule, cfg)
    out = REPORTS / args.kind / f"{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(md)


def cmd_reset(args, cfg):
    expected = f"RESET {args.portfolio}"
    confirm = args.confirm or input(f"Type '{expected}' to archive and reset paper portfolio {args.portfolio}: ")
    arch = store.reset(args.portfolio, cfg, confirm)
    print(f"[PAPER] portfolio {args.portfolio} reset to ${cfg['portfolios'][args.portfolio]['starting_cash']:,.0f}; archive: {arch}")


def cmd_import_history(args, cfg):
    counts = import_equity_historicals([Path(f) for f in args.files], args.kind)
    print(counts)


def cmd_validate_b(args, cfg):
    p = store.load("B", cfg)
    ok, msgs = two_contract_validation(p, cfg)
    print("validated" if ok else "NOT validated", msgs)
    if ok and args.apply:
        p.validated_two_contracts = True
        store.save(p)


def main(argv: list[str] | None = None) -> None:
    safety.assert_paper_mode()
    ap = argparse.ArgumentParser(prog="legion", description="LEGION leveraged-ETF CSP engine — PAPER ONLY")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        sp = sub.add_parser(name, **kw)
        sp.set_defaults(fn=fn)
        return sp

    s = add("status", cmd_status); s.add_argument("--portfolio", choices=PIDS)
    s = add("regime", cmd_regime); s.add_argument("--as-of"); s.add_argument("-v", "--verbose", action="store_true")
    for name, fn in (("scan", cmd_scan), ("rank", cmd_rank), ("manage", cmd_manage), ("fill", cmd_fill)):
        s = add(name, fn); s.add_argument("--snapshot"); s.add_argument("--now"); s.add_argument("--top", type=int, default=10)
    s = add("run-daily", cmd_run_daily); s.add_argument("--snapshot"); s.add_argument("--now"); s.add_argument("--no-submit", action="store_true")
    s = add("order", cmd_order); s.add_argument("--portfolio", choices=PIDS, required=True); s.add_argument("--instrument", required=True)
    s.add_argument("--contracts", type=int, default=1); s.add_argument("--limit", type=float); s.add_argument("--snapshot"); s.add_argument("--now")
    s = add("backtest", cmd_backtest); s.add_argument("--no-walk", action="store_true")
    add("project", cmd_project)
    s = add("risk-audit", cmd_risk_audit); s.add_argument("--as-of")
    add("safety-check", cmd_safety_check)
    s = add("report", cmd_report); s.add_argument("kind", choices=["daily", "weekly", "monthly"])
    s = add("reset", cmd_reset); s.add_argument("--portfolio", choices=PIDS, required=True); s.add_argument("--confirm")
    s = add("import-history", cmd_import_history); s.add_argument("--kind", choices=["adjusted", "raw"], required=True); s.add_argument("files", nargs="+")
    s = add("validate-b", cmd_validate_b); s.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    args.fn(args, cfg)


if __name__ == "__main__":
    main()
