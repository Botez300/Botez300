"""PAPER broker: simulated order intents, fills, closes, expirations, assignments.

No method here can reach a real broker. Every order and position is labelled
PAPER and carries a unique id plus an idempotency key.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from typing import Any

from src.data.models import OptionQuote
from src.paper.fills import FillResult, simulate_buy, simulate_sell
from src.portfolio.portfolio import PaperOrder, Portfolio, SharePosition, ShortPut
from src.safety import EXECUTION_LABEL, assert_paper_mode


def idempotency_key(portfolio_id: str, action: str, contract_key: str, session: str) -> str:
    raw = f"{portfolio_id}|{action}|{contract_key}|{session}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def contract_key(symbol: str, expiration: str, strike: float) -> str:
    return f"{symbol}:{expiration}:{strike:g}P"


class PaperBroker:
    """Mutates a ``Portfolio`` only. Caller persists it."""

    def __init__(self, cfg: dict[str, Any]):
        assert_paper_mode()
        self.cfg = cfg
        self.ecfg = cfg["execution"]
        self.scfg = cfg["screener"]

    # ------------------------------------------------------------ intents
    def create_sell_intent(self, p: Portfolio, q: OptionQuote, contracts: int, session: date, now: datetime,
                           limit_price: float, verdict: str, pair: str = "", group: str = "") -> PaperOrder:
        assert_paper_mode()
        exp = q.expiration.isoformat()
        key = idempotency_key(p.portfolio_id, "STO", contract_key(q.symbol, exp, q.strike), session.isoformat())
        existing = p.find_order_by_key(key)
        if existing is not None:
            return existing  # idempotent: never duplicate an intent
        o = PaperOrder(
            order_id=f"PAPER-{uuid.uuid4()}",
            idempotency_key=key,
            portfolio_id=p.portfolio_id,
            created_at=now.isoformat(timespec="seconds"),
            action="STO",
            symbol=q.symbol,
            contracts=contracts,
            limit_price=limit_price,
            instrument_id=q.instrument_id,
            expiration=exp,
            strike=q.strike,
            multiplier=q.multiplier,
            collateral_reserved=q.strike * q.multiplier * contracts,
            session_date=session.isoformat(),
            pair=pair,
            group=group,
            verdict=verdict,
        )
        p.orders.append(o)
        return o

    def try_fill_sell(self, p: Portfolio, o: PaperOrder, q: OptionQuote, now: datetime,
                      chain: dict[str, Any] | None = None) -> FillResult:
        assert_paper_mode()
        if o.status != "PENDING":
            return FillResult(o.status == "FILLED", o.fill_price, f"order already {o.status}")
        res = simulate_sell(q, o.contracts, now, self.ecfg, self.scfg, chain)
        if res.filled and res.price is not None and res.price + 1e-9 < o.limit_price:
            res = FillResult(False, None, f"UNFILLED: model price {res.price} below limit {o.limit_price}")
        if not res.filled:
            o.reason = res.reason
            return res
        fees = self.ecfg["fee_per_contract"] * o.contracts
        o.status, o.fill_price, o.fill_time, o.fees, o.reason = "FILLED", res.price, now.isoformat(timespec="seconds"), fees, res.reason
        p.cash += res.price * o.multiplier * o.contracts - fees
        p.fees_paid += fees
        pos = ShortPut(
            position_id=f"PAPER-POS-{uuid.uuid4()}",
            symbol=o.symbol,
            expiration=o.expiration or "",
            strike=float(o.strike or 0),
            contracts=o.contracts,
            multiplier=o.multiplier,
            entry_credit=res.price,
            entry_date=now.date().isoformat(),
            entry_fees=fees,
            order_id=o.order_id,
            instrument_id=o.instrument_id,
            pair=o.pair,
            group=o.group,
            last_mark=q.mark,
            last_mark_time=q.updated_at.isoformat(),
        )
        o.position_id = pos.position_id
        p.puts.append(pos)
        return res

    def expire_unfilled(self, p: Portfolio, session: date) -> list[PaperOrder]:
        out = []
        for o in p.pending_orders():
            if o.session_date and date.fromisoformat(o.session_date) < session:
                o.status, o.reason = "EXPIRED", "day order not filled in its session"
                out.append(o)
        return out

    def cancel(self, p: Portfolio, order_id: str, reason: str) -> None:
        for o in p.pending_orders():
            if o.order_id == order_id:
                o.status, o.reason = "CANCELLED", reason

    # ------------------------------------------------------------ lifecycle
    def mark(self, pos: ShortPut, q: OptionQuote) -> None:
        pos.last_mark = q.mark
        pos.last_mark_time = q.updated_at.isoformat()

    def close(self, p: Portfolio, pos: ShortPut, q: OptionQuote, now: datetime, reason: str,
              chain: dict[str, Any] | None = None) -> FillResult:
        assert_paper_mode()
        res = simulate_buy(q, pos.contracts, now, self.ecfg, self.scfg, chain)
        if not res.filled or res.price is None:
            pos.flags.append(f"{now.date()}: close attempt UNFILLED ({res.reason})")
            return res
        fees = self.ecfg["fee_per_contract"] * pos.contracts
        cost = res.price * pos.shares_per_contract * pos.contracts
        p.cash -= cost + fees
        p.fees_paid += fees
        pos.status, pos.close_price, pos.close_date, pos.close_fees = "CLOSED", res.price, now.date().isoformat(), fees
        pos.realized_pnl = (pos.entry_credit - res.price) * pos.shares_per_contract * pos.contracts - pos.entry_fees - fees
        pos.flags.append(f"{now.date()}: closed — {reason}")
        p.realized_pnl += pos.realized_pnl
        p.orders.append(PaperOrder(
            order_id=f"PAPER-{uuid.uuid4()}",
            idempotency_key=idempotency_key(p.portfolio_id, "BTC", pos.position_id, now.date().isoformat()),
            portfolio_id=p.portfolio_id, created_at=now.isoformat(timespec="seconds"), action="BTC",
            symbol=pos.symbol, contracts=pos.contracts, limit_price=res.price, instrument_id=pos.instrument_id,
            expiration=pos.expiration, strike=pos.strike, multiplier=pos.multiplier, status="FILLED",
            fill_price=res.price, fill_time=now.isoformat(timespec="seconds"), fees=fees, reason=reason,
            position_id=pos.position_id,
        ))
        return res

    def settle_expiration(self, p: Portfolio, pos: ShortPut, underlying_close: float, when: date) -> str:
        """Expiration: OTM -> expires worthless; ITM -> assignment at strike."""
        assert_paper_mode()
        if underlying_close >= pos.strike:
            pos.status, pos.close_price, pos.close_date = "EXPIRED", 0.0, when.isoformat()
            pos.realized_pnl = pos.entry_credit * pos.shares_per_contract * pos.contracts - pos.entry_fees
            p.realized_pnl += pos.realized_pnl
            pos.flags.append(f"{when}: expired worthless")
            return "EXPIRED"
        self.assign(p, pos, underlying_close, when, early=False)
        return "ASSIGNED"

    def assign(self, p: Portfolio, pos: ShortPut, underlying_px: float, when: date, early: bool) -> SharePosition:
        """Buy shares at strike with the reserved collateral; option P&L realised into share basis."""
        assert_paper_mode()
        n_shares = pos.shares_per_contract * pos.contracts
        p.cash -= pos.strike * n_shares
        pos.status, pos.close_date = "ASSIGNED", when.isoformat()
        pos.close_price = max(pos.strike - underlying_px, 0.0)
        # Premium kept; the option leg realises credit; share leg starts at strike.
        pos.realized_pnl = pos.entry_credit * n_shares - pos.entry_fees
        p.realized_pnl += pos.realized_pnl
        pos.flags.append(f"{when}: {'EARLY ' if early else ''}ASSIGNED {n_shares:g} sh @ {pos.strike}")
        sp = SharePosition(pos.symbol, n_shares, pos.strike, when.isoformat(), pos.position_id, underlying_px)
        p.shares.append(sp)
        return sp

    def sell_shares(self, p: Portfolio, sp: SharePosition, price: float, when: date, reason: str) -> float:
        assert_paper_mode()
        fee = self.ecfg["fee_per_share_sale"] * sp.shares
        proceeds = price * sp.shares - fee
        pnl = (price - sp.cost_basis) * sp.shares - fee
        p.cash += proceeds
        p.realized_pnl += pnl
        p.fees_paid += fee
        p.orders.append(PaperOrder(
            order_id=f"PAPER-{uuid.uuid4()}",
            idempotency_key=idempotency_key(p.portfolio_id, "SELL_SHARES", sp.source_position_id, when.isoformat()),
            portfolio_id=p.portfolio_id, created_at=when.isoformat(), action="SELL_SHARES", symbol=sp.symbol,
            contracts=0, limit_price=price, status="FILLED", fill_price=price, fill_time=when.isoformat(),
            fees=fee, reason=reason, label=EXECUTION_LABEL,
        ))
        sp.shares = 0.0
        return pnl
