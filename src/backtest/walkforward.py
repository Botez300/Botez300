"""Walk-forward parameter selection with strictly out-of-sample test years."""

from __future__ import annotations

import itertools
from datetime import date
from typing import Any

import pandas as pd

from src.backtest.engine import MarketData, run_backtest
from src.backtest.metrics import equity_metrics


def grid(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    g = cfg["backtest"]["walk_forward"]["grid"]
    keys = list(g)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(g[k] for k in keys))]


def _score(eq: pd.Series) -> float:
    m = equity_metrics(eq)
    if not m:
        return float("-inf")
    # risk-adjusted: return per unit drawdown, penalise tiny samples
    mdd = abs(m["max_drawdown"]) or 0.01
    return m["cagr"] / max(mdd, 0.02)


def walk_forward(md: MarketData, cfg: dict[str, Any], portfolio_id: str, first_test_year: int, last_test_year: int,
                 final_date: date) -> dict[str, Any]:
    train_years = cfg["backtest"]["walk_forward"]["train_years"]
    params = grid(cfg)
    equity = float(cfg["portfolios"][portfolio_id]["starting_cash"])
    segments, chosen = [], []
    for y in range(first_test_year, last_test_year + 1):
        tr_start, tr_end = date(y - train_years, 1, 1), date(y - 1, 12, 31)
        scored = []
        for pr in params:
            r = run_backtest(md, cfg, portfolio_id, tr_start, tr_end, overrides=pr)
            scored.append((_score(r.equity), pr))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        te_end = min(date(y, 12, 31), final_date)
        test = run_backtest(md, cfg, portfolio_id, date(y, 1, 1), te_end, initial_cash=equity, overrides=best)
        if len(test.equity):
            equity = float(test.equity.iloc[-1])
            segments.append(test.equity)
        chosen.append({"test_year": y, "train": f"{tr_start}..{tr_end}", "params": best, "train_score": scored[0][0],
                       "test_return": float(test.equity.iloc[-1] / test.equity.iloc[0] - 1) if len(test.equity) else 0.0,
                       "test_trades": len([t for t in test.trades if t.exit_date])})
    oos = pd.concat(segments) if segments else pd.Series(dtype=float)
    oos = oos[~oos.index.duplicated(keep="last")]
    return {"oos_equity": oos, "selections": chosen, "oos_metrics": equity_metrics(oos)}
