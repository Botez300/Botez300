"""Full research run -> reports/backtest/BACKTEST_REPORT.md (+ JSON/CSV artefacts)."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.chains import available_symbols
from src.backtest.engine import MODE, MarketData, run_backtest
from src.backtest.metrics import buy_and_hold, equity_metrics, monthly_returns, summarize
from src.backtest.scenarios import returns_by_scenario, tag_months
from src.backtest.walkforward import walk_forward
from src.config import ROOT
from src.reports.projections import projection_table

OUT = ROOT / "reports" / "backtest"
KEYS = ["end_equity", "cagr", "avg_monthly_return", "pct_profitable_months", "pct_months_ge_5pct", "max_drawdown",
        "sharpe", "sortino", "trades", "win_rate", "profit_factor", "avg_winner", "avg_loser", "expectancy",
        "assignment_rate", "max_consecutive_losses", "fees", "modeled_spread_cost", "return_on_collateral_annualized",
        "exposure_pct_days", "avg_collateral_utilization"]


def _fmt(k: str, v: Any) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    if k in {"trades", "max_consecutive_losses"}:
        return f"{int(v)}"
    if k in {"end_equity", "avg_winner", "avg_loser", "expectancy", "fees", "modeled_spread_cost"}:
        return f"${v:,.2f}"
    if k in {"sharpe", "sortino", "profit_factor"}:
        return f"{v:.2f}"
    return f"{v:.2%}"


def _table(rows: dict[str, dict[str, Any]], keys: list[str]) -> str:
    names = list(rows)
    out = ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k in keys:
        out.append(f"| {k} | " + " | ".join(_fmt(k, rows[n].get(k)) for n in names) + " |")
    return "\n".join(out)


def _df_md(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    out = ["| | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        out.append(f"| **{idx}** | " + " | ".join(f"{v:.2f}" for v in row.to_numpy()) + " |")
    return "\n".join(out)


def _variant(cfg: dict[str, Any], path: list[str], value: Any) -> dict[str, Any]:
    c = copy.deepcopy(cfg)
    d = c
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    return c


def run_research(cfg: dict[str, Any], out_dir: Path | None = None, walk: bool = True) -> dict[str, Any]:
    out = out_dir or OUT
    out.mkdir(parents=True, exist_ok=True)
    md = MarketData(cfg)
    start = date.fromisoformat(cfg["backtest"]["start"])
    end = min(date.fromisoformat(cfg["backtest"]["end"]), md.dates[-1])
    spy = md.adj[cfg["universe"]["market_benchmark"]]
    spy = spy[(spy["date"] >= start) & (spy["date"] <= end)]
    results: dict[str, Any] = {"mode": MODE, "period": f"{start}..{end}", "generated": str(date.today())}

    # ---- baseline full period
    base_rows, curves = {}, {}
    for pid in ("A", "B"):
        r = run_backtest(md, cfg, pid, start, end)
        base_rows[f"{pid} baseline"] = summarize(r)
        curves[pid] = r
        pd.DataFrame([t.__dict__ | {"pnl": t.pnl} for t in r.trades]).to_csv(out / f"trades_{pid}.csv", index=False)
    for pid in ("A", "B"):
        init = cfg["portfolios"][pid]["starting_cash"]
        bh = buy_and_hold(pd.Series(spy["close"].to_numpy(), index=spy["date"]), init)
        base_rows[f"SPY B&H ({pid} size)"] = equity_metrics(bh)
    cash_rate = cfg["backtest"]["cash_benchmark_annual"]
    base_rows["Cash"] = {"end_equity": 10000 * (1 + cash_rate) ** ((end - start).days / 365.25), "cagr": cash_rate,
                         "max_drawdown": 0.0, "avg_monthly_return": (1 + cash_rate) ** (1 / 12) - 1}
    eq_df = pd.DataFrame({f"{pid}": curves[pid].equity for pid in curves})
    eq_df.index.name = "date"
    eq_df.to_csv(out / "equity_curves.csv")

    # ---- in-sample / out-of-sample split (fixed provisional params)
    split = date(2022, 1, 1)
    isoos = {}
    for pid in ("A", "B"):
        isoos[f"{pid} IS 2018-21"] = summarize(run_backtest(md, cfg, pid, start, date(2021, 12, 31)))
        isoos[f"{pid} OOS 2022-26"] = summarize(run_backtest(md, cfg, pid, split, end))

    # ---- variants / sensitivity (Portfolio B, where trades exist)
    variants = {
        "B baseline": base_rows["B baseline"],
        "+monthly RSI": summarize(run_backtest(md, cfg, "B", start, end, overrides={"require_monthly_rsi": True})),
        "stop=close@2x": summarize(run_backtest(md, cfg, "B", start, end, overrides={"stop_action": "close"})),
        "PT 70%": summarize(run_backtest(md, cfg, "B", start, end, overrides={"profit_target_pct": 0.70})),
        "no regime exit": summarize(run_backtest(md, cfg, "B", start, end, overrides={"close_on_regime_loss": False})),
        "IV/RV 0.8": summarize(run_backtest(md, _variant(cfg, ["backtest", "iv_model", "iv_rv_ratio"], 0.8), "B", start, end)),
        "IV/RV 1.2": summarize(run_backtest(md, _variant(cfg, ["backtest", "iv_model", "iv_rv_ratio"], 1.2), "B", start, end)),
        "spread 30%": summarize(run_backtest(md, _variant(cfg, ["backtest", "spread_model", "pct_of_mid"], 0.30), "B", start, end)),
        "hold assigned": summarize(run_backtest(md, _variant(cfg, ["management", "assigned_shares_policy"], "hold_until_regime_exit"), "B", start, end)),
    }
    # Unconstrained-capital reference: same rules, $100k, to separate "strategy edge" from "account too small".
    big = _variant(cfg, ["portfolios", "B", "starting_cash"], 100000)
    variants["$100k reference"] = summarize(run_backtest(md, big, "B", start, end))

    # ---- walk-forward
    wf = {}
    if walk:
        for pid in ("A", "B"):
            w = walk_forward(md, cfg, pid, 2021, end.year, end)
            wf[pid] = w
            w["oos_equity"].to_csv(out / f"walkforward_oos_{pid}.csv")

    # ---- scenarios
    tags = tag_months(spy)
    scen = {pid: returns_by_scenario(monthly_returns(curves[pid].equity), tags) for pid in ("A", "B")}

    # ---- correlation of ETF daily returns (last 252 sessions)
    rets = pd.DataFrame({s: np.log(md.adj[s].set_index("date")["close"]).diff() for s in md.symbols}).dropna().tail(252)
    corr = rets.corr().round(2)

    # ---- projections vs actual
    proj = projection_table([5000, 10000], cfg["reports"]["projection_rates"], cfg["reports"]["projection_years"])

    results.update({
        "baseline": base_rows, "is_oos": isoos, "variants": variants,
        "walk_forward": {pid: {"selections": w["selections"], "oos_metrics": w["oos_metrics"]} for pid, w in wf.items()},
        "scenarios": {pid: df.to_dict("records") for pid, df in scen.items()},
        "historical_options_datasets": available_symbols(),
    })
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    (out / "BACKTEST_REPORT.md").write_text(_render(cfg, results, base_rows, isoos, variants, wf, scen, corr, proj, curves, md, start, end))
    return results


def _render(cfg, results, base_rows, isoos, variants, wf, scen, corr, proj, curves, md, start, end) -> str:
    L = []
    L += ["# LEGION — Historical Backtest Report (PAPER research)", "",
          f"**Mode:** {MODE}.  **Period:** {start} → {end}.  **Generated:** {results['generated']}.", "",
          "> **Read this first.** No verified historical option-chain dataset (bid/ask/Greeks/OI) was available, so "
          "**no genuine historical-options backtest was run**. Every option price below is SYNTHETIC "
          "(Black-Scholes on a realized-volatility IV proxy with skew and spread assumptions). Underlying prices are "
          "verified Robinhood daily bars. Treat results as a test of the *rules and risk controls*, not as achievable "
          "historical P&L. Success rates here are model outputs, not observed fill histories.", "",
          "## Datasets and assumptions", "",
          f"- Underlying: Robinhood MCP `get_equity_historicals`, daily, 2017-01-03 → 2026-11-13, split-adjusted (indicators) "
          "and unadjusted (trading/collateral). 9 symbols × 2,481 bars, 0 interpolated bars. [VERIFIED]",
          "- Data repair: SOXS adjusted bar 2022-03-15 was a 10× outlier that reverted next day; rebuilt from raw × "
          "neighbouring factor (see `data/history/data_quality.json`). Split events derived from raw/adjusted ratio "
          "(e.g. SQQQ 1:5 reverse ×4, SOXS ×6, TQQQ 2:1 ×4, SOXL 15:1). [CALC]",
          f"- Synthetic IV = max(floor {cfg['backtest']['iv_model']['iv_floor']:.0%}, RV20 × {cfg['backtest']['iv_model']['iv_rv_ratio']}) with skew "
          f"{cfg['backtest']['iv_model']['skew_bull']} (bull ETFs) / +{cfg['backtest']['iv_model']['skew_bear']} (inverse ETFs) per ln(K/S). "
          "Snapshot 2026-11-13 check: IV/RV 0.57–0.75 during a vol spike; skew −0.4…−2.3 bull, +0.2…+0.9 inverse. [ASSUMPTION]",
          f"- Synthetic spread = {cfg['backtest']['spread_model']['pct_of_mid']:.0%} of theo (min ${cfg['backtest']['spread_model']['min_width']}); "
          "snapshot showed 28–118% median spreads in the delta band at Friday's close, so a 30% stress is reported. [ASSUMPTION]",
          f"- Fills: sell = bid + {cfg['execution']['sell_aggressiveness']}×(mid−bid) − 1 tick; buy = ask − {cfg['execution']['buy_aggressiveness']}×(ask−mid) + 1 tick; "
          f"fees ${cfg['execution']['fee_per_contract']}/contract. Signals at close d, executions at OPEN d+1 (gap risk captured). [ASSUMPTION]",
          "- Early assignment: assumed when ITM, ≤5 DTE and extrinsic < $0.05. Expiration ITM → assignment at strike; "
          "assigned shares liquidated next open (baseline). [ASSUMPTION]",
          "- ETF distributions (small quarterly dividends) are NOT modelled: assigned-share P&L excludes them and put "
          "prices ignore ex-dividend drift. [MISSING]",
          "- Trading halts/untradeable sessions are not observable in daily bars; a missing bar is simply no action. [MISSING]",
          f"- Risk gates identical to live paper engine (`src/risk/engine.py`); after an 8% halt the backtest assumes a review clears it after {cfg['backtest']['halt_review_days']} sessions. [ASSUMPTION]",
          "", "## 1. Baseline — full period, provisional settings", "", _table(base_rows, KEYS), ""]
    for pid in ("A", "B"):
        s = base_rows[f"{pid} baseline"]
        syms: dict[str, int] = {}
        for t in curves[pid].trades:
            syms[t.symbol] = syms.get(t.symbol, 0) + 1
        L.append(f"- **{pid}** traded: {syms or 'nothing'}; outcomes: "
                 + ", ".join(f"{k[8:]} {v}" for k, v in s.items() if k.startswith("outcome_")))
    L += ["", "## 2. In-sample vs out-of-sample (fixed provisional parameters)", "", _table(isoos, KEYS), "",
          "## 3. Walk-forward (3-year training → next calendar year, strictly out-of-sample)", ""]
    for pid, w in wf.items():
        m = w["oos_metrics"]
        L.append(f"**Portfolio {pid}** — OOS CAGR {m.get('cagr', 0):.2%}, avg month {m.get('avg_monthly_return', 0):+.2%}, "
                 f"max DD {m.get('max_drawdown', 0):.2%}, Sharpe {m.get('sharpe', 0):.2f}, profitable months {m.get('pct_profitable_months', 0):.0%}.")
        L += ["", "| Test year | Train window | Chosen params | Train score | Test return | Test trades |", "|---|---|---|---|---|---|"]
        for s in w["selections"]:
            L.append(f"| {s['test_year']} | {s['train']} | {s['params']} | {s['train_score']:.2f} | {s['test_return']:+.2%} | {s['test_trades']} |")
        L.append("")
    L += ["## 4. Variants and sensitivity (Portfolio B rules; '$100k reference' isolates account-size effects)", "",
          _table(variants, KEYS), "", "## 5. Market environments (SPY-tagged months)", ""]
    for pid, df in scen.items():
        L += [f"**Portfolio {pid}**", "", "| Scenario | Months | Avg strategy month | % positive | Worst month | Avg SPY month |", "|---|---|---|---|---|---|"]
        for _, r in df.iterrows():
            f = lambda x: "n/a" if x != x else f"{x:+.2%}"  # noqa: E731
            L.append(f"| {r['scenario']} | {r['months']} | {f(r['avg_strategy_return'])} | "
                     f"{'n/a' if r['pct_positive'] != r['pct_positive'] else format(r['pct_positive'], '.0%')} | {f(r['worst'])} | {f(r['avg_benchmark_return'])} |")
        L.append("")
    L += ["## 6. Correlation of daily returns (last 252 sessions)", "", _df_md(corr), "",
          "Nasdaq-100, S&P 500 and semiconductor 3× ETFs are highly correlated; bull/bear pairs are ≈ −1. "
          "Simultaneous puts on two bull ETFs are close to doubling one position, which is why the risk engine "
          f"vetoes a second position above {cfg['risk']['max_pair_correlation']} correlation.", "",
          "## 7. Compounding: mathematical scenarios vs simulated results", "",
          "> Projections are arithmetic scenarios (Ending = Start × (1+r)^months), NOT forecasts.", "",
          "| Start | Monthly | Annualized | Year 1 | Year 5 | Year 10 | Year 15 |", "|---|---|---|---|---|---|---|"]
    for _, r in proj.iterrows():
        L.append(f"| ${r['start']:,.0f} | {r['monthly_rate']:.0%} | {r['annualized']:.1%} | ${r['year_1']:,.0f} | ${r['year_5']:,.0f} | "
                 f"${r['year_10']:,.0f} | ${r['year_15']:,.0f} |")
    for pid in ("A", "B"):
        s = base_rows[f"{pid} baseline"]
        L.append(f"\nSimulated {pid}: avg monthly {s.get('avg_monthly_return', 0):+.3%} → 15-yr extrapolation "
                 f"${cfg['portfolios'][pid]['starting_cash'] * (1 + s.get('avg_monthly_return', 0)) ** 180:,.0f} "
                 f"(vs ${cfg['portfolios'][pid]['starting_cash'] * 1.05 ** 180:,.0f} at the 5% stretch target).")
    L += ["", "## 8. Findings", ""]
    L += _findings(base_rows, isoos, variants, wf)
    return "\n".join(L)


def _findings(base_rows, isoos, variants, wf) -> list[str]:
    a, b = base_rows["A baseline"], base_rows["B baseline"]
    big = variants["$100k reference"]
    f = [
        f"1. **The 5% monthly target was not approached.** Baseline avg monthly return: A {a.get('avg_monthly_return', 0):+.2%}, "
        f"B {b.get('avg_monthly_return', 0):+.2%}; months ≥5%: A {a.get('pct_months_ge_5pct', 0):.0%}, B {b.get('pct_months_ge_5pct', 0):.0%}. "
        "Under these risk limits, 5%/month is not supported by the simulation.",
        f"2. **Account size dominates.** With 40% max collateral, A can only sell puts with strikes ≤ ~$20 "
        f"(exposure {a.get('exposure_pct_days', 0):.0%} of days); B ≤ ~$40 (exposure {b.get('exposure_pct_days', 0):.0%}). "
        f"The same rules at $100k are in a position {big.get('exposure_pct_days', 0):.0%} of days with return on collateral "
        f"{big.get('return_on_collateral_annualized', 0):.0%}/yr, but because contract counts are capped (1–2), account-level "
        f"CAGR is only {big.get('cagr', 0):.2%}: the caps, not the edge, bound returns at every size tested.",
        f"2b. **Zero simulated assignments** in all variants: positions were closed by the profit target, the 7-DTE rule or "
        "a regime exit before expiry, so 'hold assigned' equals baseline. Daily-close modelling cannot see intraday "
        "early assignment; real assignment risk is under-represented here. [MISSING]",
        f"3. **Risk profile.** Max drawdown A {a.get('max_drawdown', 0):.2%}, B {b.get('max_drawdown', 0):.2%}; "
        f"win rate B {b.get('win_rate', 0):.0%}, profit factor B {b.get('profit_factor', 0):.2f}. "
        "The drawdown halt fired in the sample; breakers limited new risk but did not cap losses on open positions.",
        f"4. **Sensitivity.** B CAGR under IV/RV 0.8: {variants['IV/RV 0.8'].get('cagr', 0):.2%}, 1.2: {variants['IV/RV 1.2'].get('cagr', 0):.2%}; "
        f"30% spreads: {variants['spread 30%'].get('cagr', 0):.2%}. Results are highly sensitive to the unverifiable premium/spread model — "
        "a further reason they cannot be treated as achievable returns.",
        f"5. **Monthly RSI confirmation:** B CAGR {variants['+monthly RSI'].get('cagr', 0):.2%} vs baseline {b.get('cagr', 0):.2%} "
        f"(trades {variants['+monthly RSI'].get('trades', 0)} vs {b.get('trades', 0)}). **2× stop as a close rule:** CAGR "
        f"{variants['stop=close@2x'].get('cagr', 0):.2%}.",
    ]
    if wf:
        f.append("6. **Walk-forward OOS:** " + "; ".join(
            f"{pid} CAGR {w['oos_metrics'].get('cagr', 0):.2%}, max DD {w['oos_metrics'].get('max_drawdown', 0):.2%}" for pid, w in wf.items())
            + ". Parameter choices were unstable across years, which argues against over-fitting the screener.")
    f.append("7. **Screener settings remain PROVISIONAL.** Nothing here validates them for live use; they require a genuine "
             "historical-options dataset and a forward paper-trading record.")
    return f
