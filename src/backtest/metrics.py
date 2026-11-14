"""Performance metrics for simulated equity curves and trade lists."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, Trade


def _ann_factor() -> float:
    return 252.0


def equity_metrics(eq: pd.Series, cash_rate: float = 0.0) -> dict[str, float]:
    eq = eq.dropna()
    if len(eq) < 2:
        return {}
    idx = pd.to_datetime(pd.Index(eq.index))
    s = pd.Series(eq.to_numpy(), index=idx)
    years = max((idx[-1] - idx[0]).days / 365.25, 1e-9)
    total = s.iloc[-1] / s.iloc[0] - 1.0
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1.0 if s.iloc[-1] > 0 else -1.0
    r = s.pct_change().dropna()
    ex = r - cash_rate / 252
    sd = ex.std()
    sharpe = float(ex.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0
    dn = ex[ex < 0]
    dsd = math.sqrt((dn**2).sum() / len(ex)) if len(ex) else 0.0
    sortino = float(ex.mean() / dsd * math.sqrt(252)) if dsd > 0 else 0.0
    peak = s.cummax()
    mdd = float(((s - peak) / peak).min())
    m = s.resample("ME").last()
    m = pd.concat([pd.Series([s.iloc[0]], index=[idx[0] - pd.Timedelta(days=1)]), m])
    mr = m.pct_change().dropna()
    return {
        "start_equity": float(s.iloc[0]),
        "end_equity": float(s.iloc[-1]),
        "total_return": float(total),
        "cagr": float(cagr),
        "avg_monthly_return": float(mr.mean()) if len(mr) else 0.0,
        "median_monthly_return": float(mr.median()) if len(mr) else 0.0,
        "pct_profitable_months": float((mr > 0).mean()) if len(mr) else 0.0,
        "pct_months_ge_5pct": float((mr >= 0.05).mean()) if len(mr) else 0.0,
        "worst_month": float(mr.min()) if len(mr) else 0.0,
        "best_month": float(mr.max()) if len(mr) else 0.0,
        "max_drawdown": mdd,
        "sharpe": sharpe,
        "sortino": sortino,
        "months": int(len(mr)),
        "years": float(years),
    }


def monthly_returns(eq: pd.Series) -> pd.Series:
    s = pd.Series(eq.to_numpy(), index=pd.to_datetime(pd.Index(eq.index)))
    m = s.resample("ME").last()
    m = pd.concat([pd.Series([s.iloc[0]], index=[s.index[0] - pd.Timedelta(days=1)]), m])
    return m.pct_change().dropna()


def trade_metrics(trades: list[Trade]) -> dict[str, float]:
    closed = [t for t in trades if t.exit_date is not None]
    if not closed:
        return {"trades": 0}
    pnl = np.array([t.pnl for t in closed])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    streak = mx = 0
    for v in pnl:
        streak = streak + 1 if v <= 0 else 0
        mx = max(mx, streak)
    outcomes: dict[str, int] = {}
    for t in closed:
        outcomes[t.outcome] = outcomes.get(t.outcome, 0) + 1
    coll_days = sum(t.collateral * max(t.days, 1) for t in closed)
    return {
        "trades": len(closed),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "avg_winner": float(wins.mean()) if len(wins) else 0.0,
        "avg_loser": float(losses.mean()) if len(losses) else 0.0,
        "expectancy": float(pnl.mean()),
        "net_pnl": float(pnl.sum()),
        "largest_loss": float(pnl.min()),
        "max_consecutive_losses": int(mx),
        "assignment_rate": outcomes.get("ASSIGNED", 0) / len(closed),
        "fees": float(sum(t.fees for t in closed)),
        "modeled_spread_cost": float(sum(t.spread_cost for t in closed)),
        "return_on_collateral_annualized": float(pnl.sum() / coll_days * 365) if coll_days > 0 else 0.0,
        "avg_days_held": float(np.mean([t.days for t in closed])),
        **{f"outcome_{k}": v for k, v in sorted(outcomes.items())},
    }


def summarize(res: BacktestResult, cash_rate: float = 0.0) -> dict[str, Any]:
    out = {"portfolio": res.portfolio_id, "mode": res.mode, **res.params}
    out.update(equity_metrics(res.equity, cash_rate))
    out.update(trade_metrics(res.trades))
    out["exposure_pct_days"] = float(res.exposure.mean()) if len(res.exposure) else 0.0
    # Invariant: sum of trade P&L must equal the equity change (no hidden P&L).
    eq_chg = float(res.equity.iloc[-1] - res.equity.iloc[0]) if len(res.equity) else 0.0
    out["pnl_reconciliation_gap"] = round(sum(t.pnl for t in res.trades) - eq_chg, 6)
    out["avg_collateral_utilization"] = float((res.collateral / res.equity).mean()) if len(res.equity) else 0.0
    return out


def buy_and_hold(close: pd.Series, start_equity: float) -> pd.Series:
    return close / close.iloc[0] * start_equity
