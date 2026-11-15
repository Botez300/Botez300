"""Scan engine.

Rules are evaluated on COMPLETED bars only: a forming daily/weekly/monthly bar is dropped
before any indicator is computed, so a result never depends on data that could still change.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from legion_data import BarSet, MarketDataProvider, ProviderError, SymbolInfo, Verification
from legion_data.base import to_timeframe
from legion_indicators import REGISTRY, IndicatorError, compute, resolve_params

from .schema import Condition, Group, Operand, ScanDefinition

ENGINE_VERSION = "scan-1.0.0"


class ScanError(ValueError):
    """The scan definition is invalid (unknown indicator, bad parameter…)."""


def validate(defn: ScanDefinition) -> None:
    operands = [o for c in defn.filter.conditions() for o in (c.left, c.right)]
    if defn.sort_by:
        operands.append(defn.sort_by)
    for o in operands:
        if o.indicator is None:
            continue
        spec = REGISTRY.get(o.indicator)
        if spec is None:
            raise ScanError(f"unknown indicator '{o.indicator}'")
        try:
            resolve_params(spec, o.params)
        except IndicatorError as e:
            raise ScanError(str(e)) from None
        if o.output is not None and o.output not in {x.name for x in spec.outputs}:
            raise ScanError(f"{o.indicator}: unknown output '{o.output}'")


@dataclass
class _SymbolContext:
    bars: dict[str, BarSet]
    cache: dict[tuple, np.ndarray] = field(default_factory=dict)

    def series(self, o: Operand) -> np.ndarray:
        frame = self.bars[o.timeframe].completed()
        if o.field:
            return frame[o.field].to_numpy("float64")
        key = (o.timeframe, o.indicator, tuple(sorted(o.params.items())), o.output)
        if key not in self.cache:
            out = compute(o.indicator, frame, o.params)  # type: ignore[arg-type]
            self.cache[key] = out[o.output or REGISTRY[o.indicator].outputs[0].name]  # type: ignore[index]
        return self.cache[key]

    def at(self, o: Operand, back: int = 0) -> float:
        """Operand value `back` bars before its reference bar; NaN if unavailable."""
        if o.value is not None:
            return o.value * o.multiplier
        s = self.series(o)
        i = len(s) - 1 - o.offset - back
        return float(s[i]) * o.multiplier if 0 <= i < len(s) else math.nan


def _condition(ctx: _SymbolContext, c: Condition) -> bool | None:
    """True/False, or None when a required value does not exist yet (insufficient history)."""
    a, b = ctx.at(c.left), ctx.at(c.right)
    if math.isnan(a) or math.isnan(b):
        return None
    if c.op in ("crosses_above", "crosses_below"):
        pa, pb = ctx.at(c.left, 1), ctx.at(c.right, 1)
        if math.isnan(pa) or math.isnan(pb):
            return None
        return (pa <= pb and a > b) if c.op == "crosses_above" else (pa >= pb and a < b)
    return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[c.op]


def _group(ctx: _SymbolContext, g: Group) -> bool | None:
    results = [_group(ctx, r) if isinstance(r, Group) else _condition(ctx, r) for r in g.rules]
    if g.logic == "and":
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True
    if any(r is True for r in results):
        return True
    return None if any(r is None for r in results) else False


def _clean(x: float) -> float | None:
    return None if math.isnan(x) or math.isinf(x) else round(x, 6)


def run_scan(provider: MarketDataProvider, defn: ScanDefinition, symbols: list[SymbolInfo],
             now: datetime | None = None) -> dict[str, Any]:
    validate(defn)
    now = now or provider.now()
    started = time.perf_counter()
    conditions = defn.filter.conditions()
    shown: dict[str, Operand] = {}
    for c in conditions:
        for o in (c.left, c.right):
            if o.value is None:
                shown.setdefault(o.label(), o)
    if defn.sort_by and defn.sort_by.value is None:
        shown.setdefault(defn.sort_by.label(), defn.sort_by)
    timeframes = {o.timeframe for o in shown.values()} | {"1D"}

    rows: list[dict[str, Any]] = []
    insufficient: list[str] = []
    errors: list[dict[str, str]] = []
    for info in symbols:
        try:
            daily_set = provider.get_bars(info.symbol, "1D", now=now)
            bars = {tf: to_timeframe(daily_set, tf) for tf in timeframes}
        except ProviderError as e:
            errors.append({"symbol": info.symbol, "error": str(e)})
            continue
        daily = bars["1D"].completed()
        if daily.empty:
            insufficient.append(info.symbol)
            continue
        ctx = _SymbolContext(bars)
        verdict = _group(ctx, defn.filter)
        if verdict is None:
            insufficient.append(info.symbol)
            continue
        if not verdict:
            continue
        verification = bars["1D"].verification
        if verification is Verification.PROVISIONAL:
            verification = Verification.VERIFIED  # only completed bars were used
        last_ts: pd.Timestamp = daily.index[-1]
        rows.append({
            "symbol": info.symbol, "name": info.name, "sector": info.sector, "industry": info.industry,
            "asset_type": info.asset_type, "exchange": info.exchange,
            "price": _clean(float(daily["close"].iloc[-1])), "bar_date": last_ts.date().isoformat(),
            "values": {label: _clean(ctx.at(o)) for label, o in shown.items()},
            "sort_value": _clean(ctx.at(defn.sort_by)) if defn.sort_by else None,
            "verification": verification.value, "data_status": bars["1D"].status.value,
            "warnings": bars["1D"].warnings,
        })

    if defn.sort_by:
        sign = -1.0 if defn.sort_desc else 1.0
        rows.sort(key=lambda r: (r["sort_value"] is None, sign * (r["sort_value"] or 0.0), r["symbol"]))
    else:
        rows.sort(key=lambda r: r["symbol"])
    return {
        "engine_version": ENGINE_VERSION, "provider": provider.name, "data_status": provider.status.value,
        "as_of": now.isoformat(), "conditions": [c.label() for c in conditions], "columns": list(shown),
        "scanned": len(symbols), "matched": len(rows), "insufficient": insufficient, "errors": errors,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 1),
        "rows": rows[: defn.limit],
    }
