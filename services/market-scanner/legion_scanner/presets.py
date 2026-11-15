"""Built-in scan templates. Each is plain data in the same schema users edit."""

from __future__ import annotations

from .schema import ScanDefinition


def _ind(indicator: str, **kw) -> dict:
    extra = {k: kw.pop(k) for k in ("output", "timeframe", "offset", "multiplier") if k in kw}
    return {"indicator": indicator, "params": kw, **extra}


_RAW = [
    ("trend-alignment", "Trend alignment",
     "Close above the 50-day SMA, 50-day above the 200-day, and RSI(14) above 50.",
     {"filter": {"logic": "and", "rules": [
         {"left": {"field": "close"}, "op": ">", "right": _ind("sma", length=50)},
         {"left": _ind("sma", length=50), "op": ">", "right": _ind("sma", length=200)},
         {"left": _ind("rsi", length=14), "op": ">", "right": {"value": 50}}]},
      "sort_by": _ind("rsi", length=14)}),
    ("breakout-20", "20-day breakout with volume",
     "Close above the highest high of the prior 20 completed sessions on at least 1.5× the 50-day average volume.",
     {"filter": {"logic": "and", "rules": [
         {"left": {"field": "close"}, "op": ">", "right": _ind("donchian", length=20, output="upper", offset=1)},
         {"left": {"field": "volume"}, "op": ">", "right": _ind("volume_sma", length=50, multiplier=1.5)}]},
      "sort_by": _ind("roc", length=20)}),
    ("oversold-daily", "Oversold watch (daily RSI ≤ 30)",
     "Daily RSI(14) at or below 30. A watch list only: oversold is not a buy signal.",
     {"filter": {"logic": "and", "rules": [
         {"left": _ind("rsi", length=14), "op": "<=", "right": {"value": 30}}]},
      "sort_by": _ind("rsi", length=14), "sort_desc": False}),
    ("macd-cross-up", "MACD bullish cross",
     "MACD line crossed above its signal line on the last completed session, with price above the 200-day SMA.",
     {"filter": {"logic": "and", "rules": [
         {"left": _ind("macd", output="macd"), "op": "crosses_above", "right": _ind("macd", output="signal")},
         {"left": {"field": "close"}, "op": ">", "right": _ind("sma", length=200)}]}}),
    ("mtf-momentum", "Multi-timeframe momentum",
     "RSI(14) above 50 on completed daily, weekly and monthly bars, with ADX(14) above 20.",
     {"filter": {"logic": "and", "rules": [
         {"left": _ind("rsi", length=14), "op": ">", "right": {"value": 50}},
         {"left": _ind("rsi", length=14, timeframe="1W"), "op": ">", "right": {"value": 50}},
         {"left": _ind("rsi", length=14, timeframe="1M"), "op": ">", "right": {"value": 50}},
         {"left": _ind("adx", length=14, output="adx"), "op": ">", "right": {"value": 20}}]},
      "sort_by": _ind("adx", length=14, output="adx")}),
    ("supertrend-flip", "SuperTrend flip up",
     "SuperTrend(10, 3) direction turned positive on the last completed session.",
     {"filter": {"logic": "and", "rules": [
         {"left": _ind("supertrend", length=10, mult=3.0, output="direction"), "op": "crosses_above",
          "right": {"value": 0}}]}}),
]

PRESETS = [
    {"id": i, "name": n, "description": d,
     "definition": ScanDefinition.model_validate(raw).model_dump(exclude_none=True)}
    for i, n, d, raw in _RAW
]
