"""Weekly / monthly PAPER performance reports from recorded equity history."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.portfolio.portfolio import Portfolio


def flow_adjusted_series(p: Portfolio) -> pd.Series:
    if not p.equity_history:
        return pd.Series(dtype=float)
    df = pd.DataFrame(p.equity_history)
    # Time-weighted: remove cumulative external flows from equity.
    s = pd.Series((df["equity"] - df["net_flows"]).to_numpy(), index=pd.to_datetime(df["date"]))
    return s


def period_table(p: Portfolio, rule: str) -> pd.DataFrame:
    s = flow_adjusted_series(p)
    if s.empty:
        return pd.DataFrame(columns=["period_end", "equity", "return"])
    base = pd.Series([p.starting_cash], index=[s.index[0] - pd.Timedelta(days=1)])
    per = pd.concat([base, s.resample(rule).last().dropna()])
    out = pd.DataFrame({"period_end": per.index.date, "equity": per.to_numpy()})
    out["return"] = out["equity"].pct_change()
    return out.iloc[1:].reset_index(drop=True)


def render_periodic(portfolios: dict[str, Portfolio], rule: str, cfg: dict[str, Any]) -> str:
    title = {"W-FRI": "Weekly", "ME": "Monthly"}[rule]
    target = cfg["reports"]["monthly_stretch_target"]
    lines = [f"# LEGION — {title} PAPER Performance", "", "> PAPER TRADING ONLY. Simulated results.", ""]
    for pid, p in portfolios.items():
        t = period_table(p, rule)
        closed = [x for x in p.puts if x.status != "OPEN"]
        lines += [f"## {p.name}", "", f"Trades closed: {len(closed)} · realized P&L ${p.realized_pnl:,.2f} · fees ${p.fees_paid:,.2f}", ""]
        if t.empty:
            lines.append("_No recorded equity history yet._")
        else:
            lines += ["| Period end | Equity (flow-adj.) | Return |" + (" vs 5% target |" if rule == "ME" else ""),
                      "|---|---|---|" + ("---|" if rule == "ME" else "")]
            for _, r in t.iterrows():
                extra = f" {'✓' if r['return'] >= target else '✗'} |" if rule == "ME" else ""
                lines.append(f"| {r['period_end']} | ${r['equity']:,.2f} | {r['return']:+.2%} |{extra}")
        lines.append("")
    return "\n".join(lines)
