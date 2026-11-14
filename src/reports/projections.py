"""Hypothetical compounding scenarios (mathematical, NOT forecasts).

Ending Equity = Starting Equity x (1 + monthly net return) ^ months
"""

from __future__ import annotations

import pandas as pd


def project(start: float, monthly_rate: float, years: int) -> pd.Series:
    months = years * 12
    return pd.Series([start * (1 + monthly_rate) ** m for m in range(months + 1)], name=f"{monthly_rate:.0%}/mo")


def projection_table(starts: list[float], rates: list[float], years: int) -> pd.DataFrame:
    rows = []
    for s in starts:
        for r in rates:
            ser = project(s, r, years)
            rows.append({
                "start": s, "monthly_rate": r, "annualized": (1 + r) ** 12 - 1,
                "year_1": ser.iloc[12], "year_5": ser.iloc[60], "year_10": ser.iloc[120], f"year_{years}": ser.iloc[-1],
            })
    return pd.DataFrame(rows)


def required_vs_actual(actual_monthly: float, target: float = 0.05) -> str:
    gap = target - actual_monthly
    return (f"actual avg monthly {actual_monthly:+.2%} vs stretch {target:.0%}: "
            f"{'meets' if gap <= 0 else f'short by {gap:.2%}/month'}")
