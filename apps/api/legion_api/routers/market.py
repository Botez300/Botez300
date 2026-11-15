from __future__ import annotations

import math
from datetime import date
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from legion_data import BarSet, ProviderError, SymbolNotFound
from legion_indicators import IndicatorError, catalog, compute

from ..deps import CachedBars, Principal, current_principal, get_market

router = APIRouter(tags=["market"], dependencies=[Depends(current_principal)])
Timeframe = Literal["1D", "1W", "1M"]


def load_bars(market: CachedBars, symbol: str, timeframe: str, start: date | None = None,
              end: date | None = None) -> BarSet:
    try:
        return market.get(symbol, timeframe, start, end)
    except SymbolNotFound as e:
        raise HTTPException(404, str(e)) from None
    except ProviderError as e:
        raise HTTPException(502, f"Market-data provider error: {e}") from None


def provenance(bars: BarSet) -> dict[str, Any]:
    return {
        "symbol": bars.symbol, "provider": bars.provider, "exchange": bars.exchange, "timeframe": bars.timeframe,
        "timezone": bars.timezone, "adjustment": bars.adjustment.value, "data_status": bars.status.value,
        "verification": bars.verification.value, "last_bar_forming": bars.last_bar_forming,
        "complete": bars.complete, "warnings": bars.warnings,
        "fetched_at": bars.fetched_at.isoformat() if bars.fetched_at else None,
        "first_bar": bars.frame.index[0].date().isoformat() if len(bars.frame) else None,
        "last_bar": bars.frame.index[-1].date().isoformat() if len(bars.frame) else None,
    }


def _ms(frame) -> list[int]:
    return (frame.index.asi8 // 1_000_000).tolist() if frame.index.unit == "ns" else \
        [int(t.timestamp() * 1000) for t in frame.index]


@router.get("/provider")
def provider_info(market: CachedBars = Depends(get_market)) -> dict:
    p = market.provider
    return {"name": p.name, "data_status": p.status.value, "adjustment": p.adjustment.value,
            "license_note": p.license_note, "timeframes": ["1D", "1W", "1M"],
            "can_enumerate_universe": bool(p.universe())}


@router.get("/symbols/search")
def search_symbols(q: str = Query("", max_length=40), limit: int = Query(20, ge=1, le=100),
                   market: CachedBars = Depends(get_market)) -> dict:
    try:
        return {"provider": market.name, "results": [s.as_dict() for s in market.provider.search(q, limit)]}
    except ProviderError as e:
        raise HTTPException(502, f"Market-data provider error: {e}") from None


@router.get("/symbols/{symbol}")
def get_symbol(symbol: str, market: CachedBars = Depends(get_market)) -> dict:
    try:
        return market.provider.get_symbol(symbol).as_dict()
    except SymbolNotFound as e:
        raise HTTPException(404, str(e)) from None
    except ProviderError as e:
        raise HTTPException(502, f"Market-data provider error: {e}") from None


@router.get("/bars/{symbol}")
def get_bars(symbol: str, timeframe: Timeframe = "1D", start: date | None = None, end: date | None = None,
             limit: int = Query(5000, ge=1, le=20000), market: CachedBars = Depends(get_market)) -> dict:
    """OHLCV bars, oldest first. `t` is the bar's open time in epoch milliseconds (00:00 UTC of its first session)."""
    bars = load_bars(market, symbol, timeframe, start, end)
    frame = bars.frame.iloc[-limit:]
    cols = [frame[c].to_numpy() for c in ("open", "high", "low", "close", "volume")]
    rows = [{"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}
            for t, o, h, l, c, v in zip(_ms(frame), *(c.tolist() for c in cols))]
    return {**provenance(bars), "bars": rows}


@router.get("/indicators")
def list_indicators() -> dict:
    return {"indicators": catalog()}


class ComputeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Timeframe = "1D"
    indicator: str = Field(min_length=1, max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(5000, ge=1, le=20000)


@router.post("/indicators/compute")
def compute_indicator(body: ComputeIn, market: CachedBars = Depends(get_market),
                      _: Principal = Depends(current_principal)) -> dict:
    """Indicator values aligned to the bars of `GET /bars`. Warm-up values are null."""
    bars = load_bars(market, body.symbol, body.timeframe)
    try:
        out = compute(body.indicator, bars.frame, body.params)
    except IndicatorError as e:
        raise HTTPException(422, str(e)) from None
    frame = bars.frame.iloc[-body.limit:]
    n = len(frame)

    def clean(a: np.ndarray) -> list[float | None]:
        return [None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x for x in a[-n:].tolist()]

    return {**provenance(bars), "indicator": body.indicator, "params": body.params, "t": _ms(frame),
            "outputs": {k: clean(v) for k, v in out.items()}}
