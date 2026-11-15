"""Provider contract and the provider-independent bar pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from . import calendar, quality
from .models import TIMEFRAMES, Adjustment, BarSet, DataStatus, ProviderError, SymbolInfo
from .resample import period_incomplete, resample

COLUMNS = ["open", "high", "low", "close", "volume"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def daily_frame(rows: list[tuple[date, float, float, float, float, float]]) -> pd.DataFrame:
    """Build the canonical daily frame: index = session date at 00:00 UTC."""
    if not rows:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz="UTC", name="time"), dtype="float64")
    idx = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], tz="UTC", name="time")
    return pd.DataFrame([r[1:] for r in rows], index=idx, columns=COLUMNS, dtype="float64")


class MarketDataProvider(ABC):
    """A source of daily OHLCV bars and symbol reference data for one vendor."""

    name: str
    status: DataStatus
    adjustment: Adjustment
    #: Human-readable licensing note surfaced in the UI and docs.
    license_note: str = ""

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[SymbolInfo]: ...

    @abstractmethod
    def get_symbol(self, symbol: str) -> SymbolInfo: ...

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Daily bars in [start, end], as built by `daily_frame`. May include today's forming bar."""

    def now(self) -> datetime:
        return utcnow()

    def universe(self) -> list[SymbolInfo]:
        """Symbols this provider can enumerate for scanning; empty if it cannot."""
        return []

    # ------------------------------------------------------------------ pipeline

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: date | None = None,
        end: date | None = None,
        now: datetime | None = None,
    ) -> BarSet:
        if timeframe not in TIMEFRAMES:
            raise ProviderError(f"unsupported timeframe '{timeframe}'; supported: {', '.join(TIMEFRAMES)}")
        now = now or self.now()
        info = self.get_symbol(symbol)
        today = now.astimezone(calendar.NY).date()
        end = min(end or today, today)
        start = start or date(end.year - 10, 1, 1)
        raw = self.fetch_daily(info.symbol, start, end)
        frame, warnings = quality.normalize(raw[COLUMNS] if not raw.empty else raw)
        warnings += quality.check_daily(frame, now=now if end >= today else None,
                                        expect_volume=info.asset_type != "index")

        forming = (not frame.empty and self.status is not DataStatus.SIMULATED
                   and calendar.session_forming(frame.index[-1].date(), now))
        daily = BarSet(
            symbol=info.symbol, provider=self.name, exchange=info.exchange, timeframe="1D", frame=frame,
            status=self.status, adjustment=self.adjustment, fetched_at=now, last_bar_forming=forming,
            complete=not any(x.startswith("missing_sessions") for x in warnings), warnings=warnings,
        )
        return to_timeframe(daily, timeframe, up_to_date=end >= today)


def to_timeframe(daily: BarSet, timeframe: str, up_to_date: bool = True) -> BarSet:
    """Derive a weekly/monthly BarSet from a daily one, flagging a period that is still open."""
    if timeframe == "1D" or daily.frame.empty:
        return replace(daily, timeframe=timeframe)
    last = daily.frame.index[-1].date()
    nxt = last + timedelta(days=1)
    while not calendar.is_session(nxt):
        nxt += timedelta(days=1)
    forming = daily.last_bar_forming or (up_to_date and period_incomplete(last, nxt, timeframe))
    return replace(daily, timeframe=timeframe, frame=resample(daily.frame, timeframe), last_bar_forming=forming)
