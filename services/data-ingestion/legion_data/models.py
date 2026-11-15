"""Provider-independent market-data types. Every bar set carries its provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import pandas as pd


class DataStatus(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    HISTORICAL = "HISTORICAL"  # end-of-day / completed sessions only
    SIMULATED = "SIMULATED"  # synthetic demo data, never real quotations


class Verification(StrEnum):
    VERIFIED = "VERIFIED"  # required data present and validated
    PROVISIONAL = "PROVISIONAL"  # latest inputs incomplete or still forming
    UNVERIFIED = "UNVERIFIED"  # required data or validation missing
    SIMULATED = "SIMULATED"  # derived from demo / synthetic data


class Adjustment(StrEnum):
    RAW = "raw"
    SPLIT = "split"
    ALL = "all"  # splits and dividends
    NOT_APPLICABLE = "n/a"


TIMEFRAMES = ("1D", "1W", "1M")


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str
    exchange: str
    asset_type: str  # stock | etf | index
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"
    provider: str = ""

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class BarSet:
    """OHLCV bars plus the metadata needed to judge whether they can be trusted.

    `frame` is indexed by the bar's open time (tz-aware UTC) with columns
    open, high, low, close, volume, ascending and de-duplicated.
    """

    symbol: str
    provider: str
    exchange: str
    timeframe: str
    frame: pd.DataFrame
    status: DataStatus
    adjustment: Adjustment
    timezone: str = "America/New_York"
    fetched_at: datetime | None = None
    last_bar_forming: bool = False
    complete: bool = True  # False when the provider returned less history than requested
    warnings: list[str] = field(default_factory=list)

    @property
    def verification(self) -> Verification:
        if self.status is DataStatus.SIMULATED:
            return Verification.SIMULATED
        if self.frame.empty or any(w.startswith("error:") for w in self.warnings):
            return Verification.UNVERIFIED
        if self.last_bar_forming or not self.complete:
            return Verification.PROVISIONAL
        return Verification.VERIFIED

    def completed(self) -> pd.DataFrame:
        """Bars whose session has closed (drops a forming last bar)."""
        return self.frame.iloc[:-1] if self.last_bar_forming and len(self.frame) else self.frame


class ProviderError(RuntimeError):
    """The provider could not serve the request (outage, auth, bad symbol)."""


class SymbolNotFound(ProviderError):
    pass
