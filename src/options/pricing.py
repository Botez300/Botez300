"""Black-Scholes put pricing utilities.

Used ONLY for (a) the clearly-labelled HYPOTHETICAL backtest and (b) sanity
checks. Live screening uses Robinhood-supplied Greeks; if a live Greek is
missing, the contract is rejected rather than having a Greek invented.
"""

from __future__ import annotations

import math


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1d2(s: float, k: float, t: float, r: float, sigma: float) -> tuple[float, float]:
    vs = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / vs
    return d1, d1 - vs


def bs_put(s: float, k: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0:
        return max(k - s, 0.0)
    d1, d2 = _d1d2(s, k, t, r, sigma)
    return k * math.exp(-r * t) * _ncdf(-d2) - s * _ncdf(-d1)


def bs_put_delta(s: float, k: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0:
        return -1.0 if s < k else 0.0
    d1, _ = _d1d2(s, k, t, r, sigma)
    return _ncdf(d1) - 1.0


def implied_vol_put(price: float, s: float, k: float, t: float, r: float) -> float | None:
    intrinsic = max(k * math.exp(-r * t) - s, 0.0)
    if price <= intrinsic + 1e-9 or t <= 0:
        return None
    lo, hi = 1e-4, 8.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if bs_put(s, k, t, r, mid) > price:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def tick_for(price: float, tick_below_3: float = 0.01, tick_above_3: float = 0.05) -> float:
    return tick_below_3 if price < 3.0 else tick_above_3


def round_down_tick(price: float, tick: float) -> float:
    return math.floor(price / tick + 1e-9) * tick


def round_up_tick(price: float, tick: float) -> float:
    return math.ceil(price / tick - 1e-9) * tick
