"""Simulated (PAPER) portfolio: balances, positions, orders, equity history.

Fully independent of any real Robinhood balance or position.
Equity = cash - short-option liabilities (marked) + assigned shares (marked).
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.config import ROOT
from src.safety import EXECUTION_LABEL, assert_paper_mode

STATE_DIR = ROOT / "state"
ARCHIVE_DIR = ROOT / "archive"


@dataclass
class ShortPut:
    position_id: str
    symbol: str
    expiration: str
    strike: float
    contracts: int
    multiplier: int
    entry_credit: float           # per share
    entry_date: str
    entry_fees: float
    order_id: str
    instrument_id: str | None = None
    pair: str = ""
    group: str = ""
    deliverable: float | None = None   # shares per contract (adjusted after splits)
    last_mark: float | None = None
    last_mark_time: str | None = None
    status: str = "OPEN"          # OPEN | CLOSED | EXPIRED | ASSIGNED
    close_price: float | None = None
    close_date: str | None = None
    close_fees: float = 0.0
    realized_pnl: float | None = None
    flags: list[str] = field(default_factory=list)
    label: str = EXECUTION_LABEL

    @property
    def shares_per_contract(self) -> float:
        return self.deliverable if self.deliverable is not None else float(self.multiplier)

    @property
    def collateral(self) -> float:
        return self.strike * self.shares_per_contract * self.contracts

    def liability(self) -> float:
        mark = self.last_mark if self.last_mark is not None else self.entry_credit
        return mark * self.shares_per_contract * self.contracts

    def unrealized_pnl(self) -> float:
        mark = self.last_mark if self.last_mark is not None else self.entry_credit
        return (self.entry_credit - mark) * self.shares_per_contract * self.contracts


@dataclass
class SharePosition:
    symbol: str
    shares: float
    cost_basis: float              # per share, incl. assignment at strike
    acquired_date: str
    source_position_id: str
    last_price: float | None = None
    label: str = EXECUTION_LABEL

    def market_value(self) -> float:
        px = self.last_price if self.last_price is not None else self.cost_basis
        return px * self.shares


@dataclass
class PaperOrder:
    order_id: str
    idempotency_key: str
    portfolio_id: str
    created_at: str
    action: str                    # STO | BTC | SELL_SHARES
    symbol: str
    contracts: int
    limit_price: float
    instrument_id: str | None = None
    expiration: str | None = None
    strike: float | None = None
    multiplier: int = 100
    status: str = "PENDING"        # PENDING | FILLED | UNFILLED | CANCELLED | EXPIRED
    collateral_reserved: float = 0.0
    fill_price: float | None = None
    fill_time: str | None = None
    fees: float = 0.0
    reason: str = ""
    session_date: str | None = None
    pair: str = ""
    group: str = ""
    position_id: str | None = None
    verdict: str = ""
    label: str = EXECUTION_LABEL


@dataclass
class Portfolio:
    portfolio_id: str
    name: str
    starting_cash: float
    cash: float
    created_at: str
    puts: list[ShortPut] = field(default_factory=list)
    shares: list[SharePosition] = field(default_factory=list)
    orders: list[PaperOrder] = field(default_factory=list)
    equity_history: list[dict[str, Any]] = field(default_factory=list)
    external_flows: list[dict[str, Any]] = field(default_factory=list)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    high_water_mark: float = 0.0
    halted: bool = False
    review_required: bool = False
    validated_two_contracts: bool = False
    risk_log: list[dict[str, Any]] = field(default_factory=list)
    label: str = EXECUTION_LABEL

    # ------------------------------------------------------------- queries
    def open_puts(self) -> list[ShortPut]:
        return [p for p in self.puts if p.status == "OPEN"]

    def pending_orders(self) -> list[PaperOrder]:
        return [o for o in self.orders if o.status == "PENDING"]

    def reserved_collateral(self, include_pending: bool = True) -> float:
        r = sum(p.collateral for p in self.open_puts())
        if include_pending:
            r += sum(o.collateral_reserved for o in self.pending_orders() if o.action == "STO")
        return r

    def option_liability(self) -> float:
        return sum(p.liability() for p in self.open_puts())

    def shares_value(self) -> float:
        return sum(s.market_value() for s in self.shares if s.shares > 0)

    def equity(self) -> float:
        return self.cash - self.option_liability() + self.shares_value()

    def unrealized_option_pnl(self) -> float:
        return sum(p.unrealized_pnl() for p in self.open_puts())

    def risk_capital(self) -> float:
        """Equity excluding unrealized gains on short options (never extra risk capacity)."""
        return self.equity() - max(0.0, self.unrealized_option_pnl())

    def unencumbered_cash(self) -> float:
        return self.cash - self.reserved_collateral(include_pending=True)

    def open_contracts(self, include_pending: bool = True) -> int:
        n = sum(p.contracts for p in self.open_puts())
        if include_pending:
            n += sum(o.contracts for o in self.pending_orders() if o.action == "STO")
        return n

    def net_external_flows(self) -> float:
        return sum(f["amount"] for f in self.external_flows)

    def find_order_by_key(self, key: str) -> PaperOrder | None:
        for o in self.orders:
            if o.idempotency_key == key:
                return o
        return None

    # ------------------------------------------------------------- mutation
    def record_equity(self, when: date, note: str = "") -> dict[str, Any]:
        eq = self.equity()
        self.high_water_mark = max(self.high_water_mark, eq)
        row = {
            "date": when.isoformat(),
            "equity": round(eq, 2),
            "cash": round(self.cash, 2),
            "reserved": round(self.reserved_collateral(), 2),
            "liability": round(self.option_liability(), 2),
            "shares_value": round(self.shares_value(), 2),
            "net_flows": round(self.net_external_flows(), 2),
            "note": note,
        }
        # one row per date (last write wins)
        self.equity_history = [r for r in self.equity_history if r["date"] != row["date"]] + [row]
        self.equity_history.sort(key=lambda r: r["date"])
        return row

    def add_flow(self, when: date, amount: float, note: str) -> None:
        assert_paper_mode()
        self.cash += amount
        self.external_flows.append({"date": when.isoformat(), "amount": amount, "note": note, "label": EXECUTION_LABEL})


def new_portfolio(pid: str, pcfg: dict[str, Any]) -> Portfolio:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p = Portfolio(pid, pcfg["name"], float(pcfg["starting_cash"]), float(pcfg["starting_cash"]), now)
    p.high_water_mark = p.starting_cash
    return p


# ------------------------------------------------------------------ storage
def _from_dict(d: dict[str, Any]) -> Portfolio:
    d = dict(d)
    d["puts"] = [ShortPut(**x) for x in d.get("puts", [])]
    d["shares"] = [SharePosition(**x) for x in d.get("shares", [])]
    d["orders"] = [PaperOrder(**x) for x in d.get("orders", [])]
    return Portfolio(**d)


def state_path(pid: str, base: Path | None = None) -> Path:
    return (base or STATE_DIR) / "portfolios" / f"{pid}.json"


def save(p: Portfolio, base: Path | None = None) -> Path:
    path = state_path(p.portfolio_id, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(p), indent=1, sort_keys=False))
    os.replace(tmp, path)  # atomic
    return path


def load(pid: str, cfg: dict[str, Any], base: Path | None = None) -> Portfolio:
    path = state_path(pid, base)
    if not path.exists():
        p = new_portfolio(pid, cfg["portfolios"][pid])
        save(p, base)
        return p
    return _from_dict(json.loads(path.read_text()))


def reset(pid: str, cfg: dict[str, Any], confirm: str, base: Path | None = None, reports_dir: Path | None = None) -> Path:
    """Archive current state + reports, then restore original simulated balance.

    ``confirm`` must equal f"RESET {pid}" exactly.
    """
    if confirm != f"RESET {pid}":
        raise PermissionError(f"reset requires confirmation string 'RESET {pid}'")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (base or STATE_DIR).parent
    arch = (root / "archive" if base else ARCHIVE_DIR) / f"{pid}_{stamp}"
    arch.mkdir(parents=True, exist_ok=True)
    sp = state_path(pid, base)
    if sp.exists():
        shutil.copy2(sp, arch / sp.name)
    rd = reports_dir or (root / "reports")
    if rd.exists():
        shutil.copytree(rd, arch / "reports", dirs_exist_ok=True)
    p = new_portfolio(pid, cfg["portfolios"][pid])
    save(p, base)
    return arch
