"""Explicit, conservative simulated fill model (never assumes a midpoint fill).

SELL (short put open):  px = bid + a * (mid - bid), capped at Robinhood's
                        high_fill_rate_sell_price when supplied, minus
                        slippage ticks, rounded DOWN to the contract tick.
BUY  (close):           px = ask - a * (ask - mid), floored at
                        high_fill_rate_buy_price, plus slippage, rounded UP.
No fill when: quote stale, outside regular hours, no bid (sell), spread
beyond hard max, or displayed size smaller than the order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.data.models import OptionQuote
from src.options.pricing import round_down_tick, round_up_tick, tick_for

ET = ZoneInfo("America/New_York")
RTH_OPEN, RTH_CLOSE = time(9, 30), time(16, 0)


@dataclass(frozen=True)
class FillResult:
    filled: bool
    price: float | None
    reason: str


def in_regular_hours(ts: datetime) -> bool:
    et = ts.astimezone(ET)
    return et.weekday() < 5 and RTH_OPEN <= et.time() <= RTH_CLOSE


def quote_is_fresh(q: OptionQuote, now: datetime, max_age_minutes: float) -> tuple[bool, str]:
    age = now - q.updated_at
    if age < timedelta(0):
        return False, "quote timestamp in the future"
    if age > timedelta(minutes=max_age_minutes):
        return False, f"quote age {age} > {max_age_minutes} min"
    if not in_regular_hours(now):
        return False, "outside regular trading hours"
    return True, "fresh"


def _ticks(q: OptionQuote, price: float, chain: dict[str, Any] | None) -> float:
    lo = (chain or {}).get("tick_below_3", 0.01)
    hi = (chain or {}).get("tick_above_3", 0.05)
    return tick_for(price, lo, hi)


def simulate_sell(q: OptionQuote, contracts: int, now: datetime, ecfg: dict[str, Any], scfg: dict[str, Any],
                  chain: dict[str, Any] | None = None) -> FillResult:
    ok, why = quote_is_fresh(q, now, scfg["max_quote_age_minutes"])
    if not ok:
        return FillResult(False, None, f"UNFILLED: {why}")
    if q.bid <= 0 or q.ask <= 0:
        return FillResult(False, None, "UNFILLED: no two-sided market")
    if q.spread_pct > scfg["hard_max_spread_pct"]:
        return FillResult(False, None, f"UNFILLED: spread {q.spread_pct:.0%} too wide")
    if q.bid_size < contracts * ecfg["min_bid_size_multiple"]:
        return FillResult(False, None, f"UNFILLED: bid size {q.bid_size} < {contracts}")
    px = q.bid + ecfg["sell_aggressiveness"] * (q.mid - q.bid)
    if q.high_fill_rate_sell_price:
        px = min(px, q.high_fill_rate_sell_price)
    tick = _ticks(q, px, chain)
    px = round_down_tick(px - ecfg["slippage_ticks"] * tick, tick)
    px = max(px, round_down_tick(q.bid, tick)) if px < q.bid else px
    if px <= 0:
        return FillResult(False, None, "UNFILLED: non-positive simulated price")
    return FillResult(True, round(px, 4), "FILLED (conservative model)")


def simulate_buy(q: OptionQuote, contracts: int, now: datetime, ecfg: dict[str, Any], scfg: dict[str, Any],
                 chain: dict[str, Any] | None = None) -> FillResult:
    ok, why = quote_is_fresh(q, now, scfg["max_quote_age_minutes"])
    if not ok:
        return FillResult(False, None, f"UNFILLED: {why}")
    if q.ask <= 0:
        return FillResult(False, None, "UNFILLED: no ask")
    if q.ask_size < contracts:
        return FillResult(False, None, f"UNFILLED: ask size {q.ask_size} < {contracts}")
    mid = q.mid if q.bid > 0 else q.ask
    px = q.ask - ecfg["buy_aggressiveness"] * (q.ask - mid)
    if q.high_fill_rate_buy_price:
        px = max(px, q.high_fill_rate_buy_price)
    tick = _ticks(q, px, chain)
    px = round_up_tick(min(px + ecfg["slippage_ticks"] * tick, q.ask), tick)
    return FillResult(True, round(px, 4), "FILLED (conservative model)")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
