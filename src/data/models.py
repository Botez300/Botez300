"""Typed market-data models and data-provenance labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class DataLabel(str, Enum):
    VERIFIED = "Verified market data"
    CALCULATED = "Calculated indicator"
    SIMULATED = "Simulated execution"
    ASSUMPTION = "Research assumption"
    MISSING = "Missing or unverified data"

    @property
    def tag(self) -> str:
        return {
            "Verified market data": "[VERIFIED]",
            "Calculated indicator": "[CALC]",
            "Simulated execution": "[SIM]",
            "Research assumption": "[ASSUMPTION]",
            "Missing or unverified data": "[MISSING]",
        }[self.value]


@dataclass(frozen=True)
class EquityQuote:
    symbol: str
    last: float
    last_time: datetime
    bid: float | None
    ask: float | None
    quote_time: datetime | None
    previous_close: float | None
    state: str = "active"


@dataclass(frozen=True)
class OptionQuote:
    instrument_id: str
    symbol: str
    expiration: date
    strike: float
    option_type: str
    multiplier: int
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    mark: float
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    open_interest: int
    volume: int
    updated_at: datetime
    high_fill_rate_sell_price: float | None = None
    high_fill_rate_buy_price: float | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        m = self.mid
        return self.spread / m if m > 0 else float("inf")

    def dte(self, as_of: date) -> int:
        return (self.expiration - as_of).days


@dataclass
class Snapshot:
    """A validated market-data snapshot captured from the Robinhood MCP."""

    as_of: date
    captured_at: datetime
    equity_quotes: dict[str, EquityQuote] = field(default_factory=dict)
    option_quotes: list[OptionQuote] = field(default_factory=list)
    chains: dict[str, dict] = field(default_factory=dict)
    source_tools: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
