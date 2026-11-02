"""Fail-closed proposed BUY sizing guard for Robinhood stock/ETF Turtle System 1.

This module does not connect to a brokerage or place orders. Give it a fresh
account-level snapshot; include *all* stock/ETF holdings and open buy orders in
the designated agentic account, not just strategy-tagged holdings.

"Cash" means actual unencumbered cash before reserving pending buys, NOT margin
buying power. Holdings can drift above limits after execution; this guard does
not liquidate them automatically. Recompute immediately before submitting any
proposed order and still require explicit user review/approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from typing import Tuple

D = Decimal

@dataclass(frozen=True)
class Position:
    symbol: str
    market_value: Decimal
    risk_at_stop: Decimal = D("0")

@dataclass(frozen=True)
class PendingBuy:
    symbol: str
    estimated_cost: Decimal
    reserved_risk_at_stop: Decimal = D("0")

@dataclass(frozen=True)
class Snapshot:
    net_liquidation_value: Decimal
    unencumbered_cash_before_open_buy_reservations: Decimal
    positions: Tuple[Position, ...]
    pending_buys: Tuple[PendingBuy, ...]

@dataclass(frozen=True)
class Decision:
    permitted_shares: int
    reason: str
    remaining_cash_after_proposed_purchase: Decimal
    required_cash_floor: Decimal
    distinct_symbols_after_proposed_purchase: int


def max_buy_shares(
    snapshot: Snapshot,
    symbol: str,
    expected_fill_price: Decimal,
    N: Decimal,
    *,
    order_fee_estimate: Decimal = D("0"),
    execution_buffer_bps: Decimal = D("25"),
    max_symbols: int = 5,
    min_cash_fraction: Decimal = D("0.05"),
    max_symbol_fraction: Decimal = D("0.19"),
    max_symbol_stop_risk_fraction: Decimal = D("0.005"),
) -> Decision:
    """Return upper bound on *additional whole shares* for a BUY proposal.

    The cash reserve is 5% of current NAV, calculated post-execution, with a
    modest optional fill-price buffer. Risk uses 2N per new share; overnight
    gaps can produce losses larger than the assumed stop loss.
    """
    symbol = symbol.upper().strip()
    if not symbol or snapshot.net_liquidation_value <= 0 or expected_fill_price <= 0 or N <= 0:
        raise ValueError("Valid symbol, positive NAV, price and N required")
    if order_fee_estimate < 0 or execution_buffer_bps < 0:
        raise ValueError("Fees and execution buffer cannot be negative")
    nav = snapshot.net_liquidation_value
    cash_floor = nav * min_cash_fraction
    pending_cost = sum((o.estimated_cost for o in snapshot.pending_buys), D("0"))
    cash_after_existing_orders = snapshot.unencumbered_cash_before_open_buy_reservations - pending_cost
    occupied = {p.symbol.upper() for p in snapshot.positions if p.market_value > 0}
    occupied |= {o.symbol.upper() for o in snapshot.pending_buys if o.estimated_cost > 0}
    new_symbol = symbol not in occupied
    slot_count = len(occupied) + (1 if new_symbol else 0)
    def deny(msg: str) -> Decision:
        return Decision(0, msg, cash_after_existing_orders, cash_floor, slot_count)
    if len(occupied) > max_symbols:
        return deny("Account already exceeds position cap; block all new buys")
    if new_symbol and len(occupied) >= max_symbols:
        return deny("Maximum five occupied symbols including pending buys")
    if cash_after_existing_orders <= cash_floor:
        return deny("Cash reserve at or below 5% of account NAV")
    symbol_market_value = sum((p.market_value for p in snapshot.positions if p.symbol.upper() == symbol), D("0"))
    symbol_pending_cost = sum((o.estimated_cost for o in snapshot.pending_buys if o.symbol.upper() == symbol), D("0"))
    existing_risk = sum((p.risk_at_stop for p in snapshot.positions if p.symbol.upper() == symbol), D("0"))
    existing_risk += sum((o.reserved_risk_at_stop for o in snapshot.pending_buys if o.symbol.upper() == symbol), D("0"))
    buffered_price = expected_fill_price * (D("1") + execution_buffer_bps / D("10000"))
    cash_spendable = max(D("0"), cash_after_existing_orders - cash_floor - order_fee_estimate)
    symbol_spendable = max(D("0"), nav * max_symbol_fraction - symbol_market_value - symbol_pending_cost)
    symbol_risk_left = max(D("0"), nav * max_symbol_stop_risk_fraction - existing_risk)
    risk_per_share = D("2") * N
    cash_shares = int((cash_spendable / buffered_price).to_integral_value(rounding=ROUND_FLOOR))
    allocation_shares = int((symbol_spendable / buffered_price).to_integral_value(rounding=ROUND_FLOOR))
    risk_shares = int((symbol_risk_left / risk_per_share).to_integral_value(rounding=ROUND_FLOOR))
    shares = max(0, min(cash_shares, allocation_shares, risk_shares))
    if shares == 0:
        return deny("Cash, 19% symbol allocation, or 0.5% symbol risk gate prevents purchase")
    remainder = cash_after_existing_orders - shares * buffered_price - order_fee_estimate
    return Decision(shares, "Eligible for proposal only — not an authorization to trade", remainder, cash_floor, slot_count)

if __name__ == "__main__":
    s = Snapshot(D("10000"), D("4000"), tuple(), tuple())
    d = max_buy_shares(s, "SPY", D("100"), D("2"))
    print(d)
