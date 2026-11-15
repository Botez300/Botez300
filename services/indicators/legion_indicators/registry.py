"""Indicator registry: the single source of truth for indicator definitions.

The API serves this catalog; the web chart, the scanner and (later) the strategy schema
all refer to indicators by the ids, parameters and outputs declared here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

import numpy as np
import pandas as pd

from . import core

Frame: TypeAlias = pd.DataFrame
Outputs: TypeAlias = dict[str, np.ndarray]


@dataclass(frozen=True)
class Param:
    name: str
    kind: Literal["int", "float", "source"]
    default: Any
    min: float | None = None
    max: float | None = None
    title: str | None = None


@dataclass(frozen=True)
class Output:
    name: str
    title: str
    style: Literal["line", "histogram", "dots"] = "line"


@dataclass(frozen=True)
class IndicatorSpec:
    id: str
    name: str
    category: Literal["average", "momentum", "volatility", "trend", "volume"]
    overlay: bool  # True = drawn on the price pane
    params: tuple[Param, ...]
    outputs: tuple[Output, ...]
    compute: Callable[..., Outputs] = field(repr=False, compare=False)
    version: str = "1.0.0"
    reference: str = ""  # how the implementation is validated
    levels: tuple[float, ...] = ()  # horizontal guide levels for the pane

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "overlay": self.overlay,
            "version": self.version,
            "reference": self.reference,
            "levels": list(self.levels),
            "params": [
                {"name": p.name, "kind": p.kind, "default": p.default, "min": p.min, "max": p.max,
                 "title": p.title or p.name.replace("_", " ").title()}
                for p in self.params
            ],
            "outputs": [{"name": o.name, "title": o.title, "style": o.style} for o in self.outputs],
        }


class IndicatorError(ValueError):
    pass


SOURCES = ("close", "open", "high", "low", "hl2", "hlc3", "ohlc4")


def price_source(df: Frame, name: str) -> np.ndarray:
    if name in ("open", "high", "low", "close"):
        return df[name].to_numpy("float64")
    if name == "hl2":
        return ((df["high"] + df["low"]) / 2.0).to_numpy("float64")
    if name == "hlc3":
        return ((df["high"] + df["low"] + df["close"]) / 3.0).to_numpy("float64")
    if name == "ohlc4":
        return ((df["open"] + df["high"] + df["low"] + df["close"]) / 4.0).to_numpy("float64")
    raise IndicatorError(f"unknown source '{name}'")


def _hlc(df: Frame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return df["high"].to_numpy("float64"), df["low"].to_numpy("float64"), df["close"].to_numpy("float64")


def _vol(df: Frame) -> np.ndarray:
    return df["volume"].to_numpy("float64")


_LEN = lambda d, lo=1: Param("length", "int", d, lo, 1000)  # noqa: E731
_SRC = Param("source", "source", "close")
TALIB = "Golden-tested against TA-Lib {} (tests/python/test_indicators_golden.py)"
PROPS = "Property-tested against a from-definition calculation (tests/python/test_indicators_props.py)"

_SPECS: list[IndicatorSpec] = [
    IndicatorSpec("sma", "Simple Moving Average", "average", True, (_LEN(20), _SRC), (Output("sma", "SMA"),),
                  lambda df, length, source: {"sma": core.sma(price_source(df, source), length)},
                  reference=TALIB.format("SMA")),
    IndicatorSpec("ema", "Exponential Moving Average", "average", True, (_LEN(20), _SRC), (Output("ema", "EMA"),),
                  lambda df, length, source: {"ema": core.ema(price_source(df, source), length)},
                  reference=TALIB.format("EMA")),
    IndicatorSpec("wma", "Weighted Moving Average", "average", True, (_LEN(20), _SRC), (Output("wma", "WMA"),),
                  lambda df, length, source: {"wma": core.wma(price_source(df, source), length)},
                  reference=TALIB.format("WMA")),
    IndicatorSpec("vwma", "Volume-Weighted Moving Average", "average", True, (_LEN(20),), (Output("vwma", "VWMA"),),
                  lambda df, length: {"vwma": core.vwma(df["close"].to_numpy("float64"), _vol(df), length)},
                  reference=PROPS),
    IndicatorSpec("rsi", "Relative Strength Index", "momentum", False, (_LEN(14, 2), _SRC), (Output("rsi", "RSI"),),
                  lambda df, length, source: {"rsi": core.rsi(price_source(df, source), length)},
                  reference=TALIB.format("RSI"), levels=(30.0, 50.0, 70.0)),
    IndicatorSpec("macd", "MACD", "momentum", False,
                  (Param("fast", "int", 12, 1, 500), Param("slow", "int", 26, 2, 1000), Param("signal", "int", 9, 1, 500)),
                  (Output("macd", "MACD"), Output("signal", "Signal"), Output("histogram", "Histogram", "histogram")),
                  lambda df, fast, slow, signal: dict(zip(("macd", "signal", "histogram"),
                                                          core.macd(df["close"].to_numpy("float64"), fast, slow, signal))),
                  reference=TALIB.format("MACD"), levels=(0.0,)),
    IndicatorSpec("stoch", "Stochastic Oscillator", "momentum", False,
                  (Param("k_length", "int", 14, 1, 500), Param("k_smooth", "int", 3, 1, 100), Param("d_smooth", "int", 3, 1, 100)),
                  (Output("k", "%K"), Output("d", "%D")),
                  lambda df, k_length, k_smooth, d_smooth: dict(zip(("k", "d"),
                                                                    core.stochastic(*_hlc(df), k_length, k_smooth, d_smooth))),
                  reference=TALIB.format("STOCH"), levels=(20.0, 80.0)),
    IndicatorSpec("stochrsi", "Stochastic RSI", "momentum", False,
                  (Param("rsi_length", "int", 14, 2, 500), Param("stoch_length", "int", 14, 1, 500),
                   Param("k_smooth", "int", 3, 1, 100), Param("d_smooth", "int", 3, 1, 100)),
                  (Output("k", "%K"), Output("d", "%D")),
                  lambda df, rsi_length, stoch_length, k_smooth, d_smooth: dict(zip(("k", "d"), core.stoch_rsi(
                      df["close"].to_numpy("float64"), rsi_length, stoch_length, k_smooth, d_smooth))),
                  reference=TALIB.format("RSI + STOCH composition"), levels=(20.0, 80.0)),
    IndicatorSpec("roc", "Rate of Change", "momentum", False, (_LEN(10), _SRC), (Output("roc", "ROC %"),),
                  lambda df, length, source: {"roc": core.roc(price_source(df, source), length)},
                  reference=TALIB.format("ROC"), levels=(0.0,)),
    IndicatorSpec("willr", "Williams %R", "momentum", False, (_LEN(14),), (Output("willr", "%R"),),
                  lambda df, length: {"willr": core.williams_r(*_hlc(df), length)},
                  reference=TALIB.format("WILLR"), levels=(-80.0, -20.0)),
    IndicatorSpec("cci", "Commodity Channel Index", "momentum", False, (_LEN(20, 2),), (Output("cci", "CCI"),),
                  lambda df, length: {"cci": core.cci(*_hlc(df), length)},
                  reference=TALIB.format("CCI"), levels=(-100.0, 100.0)),
    IndicatorSpec("mfi", "Money Flow Index", "volume", False, (_LEN(14, 2),), (Output("mfi", "MFI"),),
                  lambda df, length: {"mfi": core.mfi(*_hlc(df), _vol(df), length)},
                  reference=TALIB.format("MFI"), levels=(20.0, 80.0)),
    IndicatorSpec("bbands", "Bollinger Bands", "volatility", True,
                  (_LEN(20, 2), Param("mult", "float", 2.0, 0.1, 10.0), _SRC),
                  (Output("upper", "Upper"), Output("middle", "Basis"), Output("lower", "Lower")),
                  lambda df, length, mult, source: dict(zip(("upper", "middle", "lower"),
                                                            core.bollinger(price_source(df, source), length, mult))),
                  reference=TALIB.format("BBANDS")),
    IndicatorSpec("keltner", "Keltner Channels", "volatility", True,
                  (_LEN(20), Param("atr_length", "int", 10, 1, 500), Param("mult", "float", 2.0, 0.1, 10.0)),
                  (Output("upper", "Upper"), Output("middle", "Basis"), Output("lower", "Lower")),
                  lambda df, length, atr_length, mult: dict(zip(("upper", "middle", "lower"),
                                                                core.keltner(*_hlc(df), length, atr_length, mult))),
                  reference=PROPS),
    IndicatorSpec("donchian", "Donchian Channels", "volatility", True, (_LEN(20),),
                  (Output("upper", "Upper"), Output("middle", "Middle"), Output("lower", "Lower")),
                  lambda df, length: dict(zip(("upper", "middle", "lower"),
                                              core.donchian(df["high"].to_numpy("float64"), df["low"].to_numpy("float64"), length))),
                  reference=TALIB.format("MAX/MIN")),
    IndicatorSpec("atr", "Average True Range", "volatility", False, (_LEN(14),), (Output("atr", "ATR"),),
                  lambda df, length: {"atr": core.atr(*_hlc(df), length)},
                  reference=TALIB.format("ATR")),
    IndicatorSpec("hv", "Historical Volatility", "volatility", False,
                  (_LEN(20, 2), Param("periods_per_year", "int", 252, 1, 100000)), (Output("hv", "HV %"),),
                  lambda df, length, periods_per_year: {"hv": core.historical_volatility(
                      df["close"].to_numpy("float64"), length, periods_per_year)},
                  reference=PROPS),
    IndicatorSpec("adx", "ADX / DMI", "trend", False, (_LEN(14, 2),),
                  (Output("adx", "ADX"), Output("plus_di", "+DI"), Output("minus_di", "-DI")),
                  lambda df, length: dict(zip(("adx", "plus_di", "minus_di"), core.adx(*_hlc(df), length))),
                  reference=TALIB.format("ADX/PLUS_DI/MINUS_DI (after warm-up; TA-Lib seeds its Wilder sums one bar short)"),
                  levels=(20.0,)),
    IndicatorSpec("supertrend", "SuperTrend", "trend", True,
                  (_LEN(10), Param("mult", "float", 3.0, 0.1, 20.0)),
                  (Output("supertrend", "SuperTrend"), Output("direction", "Direction", "dots")),
                  lambda df, length, mult: dict(zip(("supertrend", "direction"), core.supertrend(*_hlc(df), length, mult))),
                  reference=PROPS),
    IndicatorSpec("psar", "Parabolic SAR", "trend", True,
                  (Param("step", "float", 0.02, 0.001, 1.0), Param("max_step", "float", 0.2, 0.01, 1.0)),
                  (Output("psar", "SAR", "dots"),),
                  lambda df, step, max_step: {"psar": core.parabolic_sar(
                      df["high"].to_numpy("float64"), df["low"].to_numpy("float64"), step, max_step)},
                  reference=TALIB.format("SAR")),
    IndicatorSpec("obv", "On-Balance Volume", "volume", False, (), (Output("obv", "OBV"),),
                  lambda df: {"obv": core.obv(df["close"].to_numpy("float64"), _vol(df))},
                  reference=TALIB.format("OBV")),
    IndicatorSpec("ad", "Accumulation/Distribution", "volume", False, (), (Output("ad", "A/D"),),
                  lambda df: {"ad": core.accumulation_distribution(*_hlc(df), _vol(df))},
                  reference=TALIB.format("AD")),
    IndicatorSpec("cmf", "Chaikin Money Flow", "volume", False, (_LEN(20),), (Output("cmf", "CMF"),),
                  lambda df, length: {"cmf": core.cmf(*_hlc(df), _vol(df), length)},
                  reference=PROPS, levels=(0.0,)),
    IndicatorSpec("volume_sma", "Volume Moving Average", "volume", False, (_LEN(50),), (Output("volume_sma", "Vol MA"),),
                  lambda df, length: {"volume_sma": core.sma(_vol(df), length)},
                  reference=TALIB.format("SMA")),
    IndicatorSpec("avwap", "Anchored VWAP", "volume", True,
                  (Param("anchor", "int", 0, 0, 10_000_000, "Anchor (bar index)"),), (Output("avwap", "AVWAP"),),
                  lambda df, anchor: {"avwap": core.anchored_vwap(*_hlc(df), _vol(df), anchor)},
                  reference=PROPS),
]

REGISTRY: dict[str, IndicatorSpec] = {s.id: s for s in _SPECS}


def catalog() -> list[dict[str, Any]]:
    return [s.describe() for s in _SPECS]


def resolve_params(spec: IndicatorSpec, params: dict[str, Any] | None) -> dict[str, Any]:
    """Validate user params against the spec and fill defaults."""
    given = dict(params or {})
    out: dict[str, Any] = {}
    for p in spec.params:
        v = given.pop(p.name, p.default)
        if p.kind == "source":
            if v not in SOURCES:
                raise IndicatorError(f"{spec.id}.{p.name}: must be one of {', '.join(SOURCES)}")
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise IndicatorError(f"{spec.id}.{p.name}: must be a number")
            if p.kind == "int":
                if float(v) != int(v):
                    raise IndicatorError(f"{spec.id}.{p.name}: must be an integer")
                v = int(v)
            else:
                v = float(v)
            if p.min is not None and v < p.min or p.max is not None and v > p.max:
                raise IndicatorError(f"{spec.id}.{p.name}: must be between {p.min} and {p.max}")
        out[p.name] = v
    if given:
        raise IndicatorError(f"{spec.id}: unknown parameter(s) {', '.join(sorted(given))}")
    return out


def compute(indicator_id: str, df: Frame, params: dict[str, Any] | None = None) -> Outputs:
    """Compute an indicator over an OHLCV frame (columns open, high, low, close, volume)."""
    spec = REGISTRY.get(indicator_id)
    if spec is None:
        raise IndicatorError(f"unknown indicator '{indicator_id}'")
    missing = {"open", "high", "low", "close", "volume"} - set(df.columns)
    if missing:
        raise IndicatorError(f"frame is missing columns: {', '.join(sorted(missing))}")
    resolved = resolve_params(spec, params)
    if indicator_id == "macd" and resolved["fast"] >= resolved["slow"]:
        raise IndicatorError("macd: fast must be less than slow")
    return spec.compute(df, **resolved)
