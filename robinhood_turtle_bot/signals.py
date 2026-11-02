"""Turtle System 1 signal engine (long-only, daily bars, RSI(14) >= 50 filter).

Pure functions, no brokerage access. Feed it daily bars from the Robinhood
`get_equity_historicals` tool (interval="day", bounds="regular") and it returns
breakout levels, N, the prior-breakout winner filter, exits and pyramid levels.

Only COMPLETED daily bars are used for every rule. If the newest bar is today's
forming bar, pass last_bar_complete=False (the default) and it is dropped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Iterable, List, Optional

CONFIG_PATH = Path(__file__).with_name("strategy_config.json")


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float


def parse_bars(raw: Iterable[Any]) -> List[Bar]:
    """Accept Robinhood bar dicts (begins_at/open_price/...) or plain OHLC dicts."""
    bars = []
    for b in raw:
        if b.get("interpolated"):
            continue
        date = str(b.get("begins_at") or b.get("date"))[:10]
        bars.append(Bar(
            date=date,
            open=float(b.get("open_price", b.get("open"))),
            high=float(b.get("high_price", b.get("high"))),
            low=float(b.get("low_price", b.get("low"))),
            close=float(b.get("close_price", b.get("close"))),
        ))
    bars.sort(key=lambda x: x.date)
    dedup: List[Bar] = []
    for b in bars:
        if dedup and dedup[-1].date == b.date:
            dedup[-1] = b
        else:
            dedup.append(b)
    return dedup


def wilder_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_g, avg_l = gains / period, losses / period

    def rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / l)

    out[period] = rsi(avg_g, avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
        out[i] = rsi(avg_g, avg_l)
    return out


def turtle_n(bars: List[Bar], period: int = 20) -> List[Optional[float]]:
    """Original Turtle N: N = (19 * prior N + TR) / 20, seeded with a 20-day TR mean."""
    out: List[Optional[float]] = [None] * len(bars)
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
        trs.append(max(h - l, h - pc, pc - l))
    if len(trs) < period:
        return out
    n = sum(trs[:period]) / period
    out[period] = n
    for i in range(period + 1, len(bars)):
        n = ((period - 1) * n + trs[i - 1]) / period
        out[i] = n
    return out


@dataclass
class TheoreticalTrade:
    entry_date: str
    entry_price: float
    stop: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.exit_date is None

    @property
    def winner(self) -> Optional[bool]:
        if self.exit_price is None:
            return None
        return self.exit_price > self.entry_price


def theoretical_20_day_ledger(bars: List[Bar], n: List[Optional[float]], cfg: dict) -> List[TheoreticalTrade]:
    """Independent ledger of every theoretical System 1 20-day breakout (one unit,
    no pyramiding, no RSI filter), used only for the 'skip after a winner' rule."""
    t = cfg["turtle_system_1"]
    entry_d, exit_d, stop_mult = t["entry_breakout_days"], t["primary_exit_days"], t["initial_stop_multiple_N"]
    trades: List[TheoreticalTrade] = []
    cur: Optional[TheoreticalTrade] = None
    for i in range(entry_d, len(bars)):
        b = bars[i]
        if cur is None:
            level = max(x.high for x in bars[i - entry_d:i])
            if b.high > level and n[i - 1] is not None:
                px = max(b.open, level)
                cur = TheoreticalTrade(b.date, px, px - stop_mult * n[i - 1])
                trades.append(cur)
                # Same-bar stop-out is possible.
                if b.low <= cur.stop:
                    cur.exit_date, cur.exit_price, cur.exit_reason = b.date, cur.stop, "2N stop"
                    cur = None
            continue
        exit_level = min(x.low for x in bars[i - exit_d:i])
        if b.low <= cur.stop:
            cur.exit_date, cur.exit_price, cur.exit_reason = b.date, min(b.open, cur.stop), "2N stop"
            cur = None
        elif b.low < exit_level:
            cur.exit_date, cur.exit_price, cur.exit_reason = b.date, min(b.open, exit_level), "10-day low"
            cur = None
    return trades


def _completed(bars: List[Bar], last_bar_complete: bool) -> List[Bar]:
    return bars if last_bar_complete else bars[:-1]


@dataclass
class EntryEvaluation:
    symbol: str
    as_of_completed_bar: str
    live_price: Optional[float]
    rsi14_completed: Optional[float]
    rsi_ok: bool
    N: Optional[float]
    breakout_20_level: float
    breakout_55_level: float
    exit_10_level: float
    last_theoretical_20_breakout: Optional[dict]
    skip_20_day_due_to_prior_winner: bool
    signal: str  # "ENTER_20", "ENTER_55_FAILSAFE", "NONE"
    entry_trigger_price: Optional[float]
    initial_stop: Optional[float]
    pyramid_add_levels: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_entry(symbol: str, raw_bars: Iterable[Any], live_price: Optional[float] = None,
                   last_bar_complete: bool = False, cfg: Optional[dict] = None) -> EntryEvaluation:
    cfg = cfg or load_config()
    t = cfg["turtle_system_1"]
    rsi_cfg = cfg["daily_rsi"]
    bars = _completed(parse_bars(raw_bars), last_bar_complete)
    need = max(t["fallback_entry_breakout_days"], t["volatility_N_period"] + 1, rsi_cfg["period"] * 5) + 1
    if len(bars) < need:
        raise ValueError(f"Need at least {need} completed daily bars, got {len(bars)}; request ~1 year of history")

    closes = [b.close for b in bars]
    rsi = wilder_rsi(closes, rsi_cfg["period"])[-1]
    n_series = turtle_n(bars, t["volatility_N_period"])
    N = n_series[-1]
    hi20 = max(b.high for b in bars[-t["entry_breakout_days"]:])
    hi55 = max(b.high for b in bars[-t["fallback_entry_breakout_days"]:])
    lo10 = min(b.low for b in bars[-t["primary_exit_days"]:])

    ledger = theoretical_20_day_ledger(bars, n_series, cfg)
    last = ledger[-1] if ledger else None
    notes: List[str] = []
    skip20 = False
    if last and t["skip_20_day_breakout_if_previous_theoretical_20_day_breakout_was_a_winner"]:
        if last.is_open:
            # The last breakout is still running, so a new 20-day high is not a fresh
            # breakout. Fail closed: only the 55-day failsafe may enter.
            skip20 = True
            notes.append("Last theoretical 20-day breakout is still open; 20-day entry blocked, 55-day failsafe only")
        elif last.winner:
            skip20 = True
            notes.append("Last theoretical 20-day breakout was a winner; 20-day entry skipped")

    rsi_ok = rsi is not None and rsi >= rsi_cfg["minimum"]
    if not rsi_ok:
        notes.append(f"Completed-bar RSI(14) {rsi:.2f} < {rsi_cfg['minimum']}; no entries" if rsi is not None else "RSI unavailable")

    signal, trigger = "NONE", None
    if live_price is not None and rsi_ok and N:
        if live_price > hi55:
            signal, trigger = "ENTER_55_FAILSAFE", hi55
        if live_price > hi20 and not skip20:
            signal, trigger = "ENTER_20", hi20
    elif live_price is None:
        notes.append("No live price given: levels only. Breakout needs live price > level")

    stop = adds = None
    if trigger is not None and N:
        ref = max(trigger, live_price or trigger)
        stop = round(ref - t["initial_stop_multiple_N"] * N, 4)
        adds = [round(ref + k * t["pyramid_spacing_multiple_N"] * N, 4) for k in range(1, t["maximum_units_per_symbol"])]
        notes.append("Stop/adds are estimates from expected fill; recompute from the ACTUAL fill price")

    return EntryEvaluation(
        symbol=symbol.upper(), as_of_completed_bar=bars[-1].date, live_price=live_price,
        rsi14_completed=None if rsi is None else round(rsi, 2), rsi_ok=rsi_ok,
        N=None if N is None else round(N, 4),
        breakout_20_level=hi20, breakout_55_level=hi55, exit_10_level=lo10,
        last_theoretical_20_breakout=None if last is None else {**asdict(last), "winner": last.winner},
        skip_20_day_due_to_prior_winner=skip20, signal=signal, entry_trigger_price=trigger,
        initial_stop=stop, pyramid_add_levels=adds or [], notes=notes,
    )


def evaluate_position(symbol: str, raw_bars: Iterable[Any], live_price: float,
                      unit_fill_prices: List[float], entry_N: float,
                      last_bar_complete: bool = False, cfg: Optional[dict] = None) -> dict:
    """Exit + pyramid check for an open Turtle position. Exits ignore RSI.

    unit_fill_prices: actual fill price of each unit in order (first = initial entry).
    entry_N: N on the completed bar before the initial entry (original rules keep it fixed).
    """
    cfg = cfg or load_config()
    t = cfg["turtle_system_1"]
    if not unit_fill_prices or entry_N <= 0:
        raise ValueError("unit_fill_prices and positive entry_N required")
    bars = _completed(parse_bars(raw_bars), last_bar_complete)
    if len(bars) < t["primary_exit_days"]:
        raise ValueError("Not enough completed bars for the 10-day exit")
    lo10 = min(b.low for b in bars[-t["primary_exit_days"]:])
    # Original Turtle: all units share one stop, 2N below the most recent unit.
    stop = unit_fill_prices[-1] - t["initial_stop_multiple_N"] * entry_N
    units = len(unit_fill_prices)
    actions = []
    if live_price <= stop:
        actions.append("EXIT_ALL_2N_STOP")
    if live_price < lo10:
        actions.append("EXIT_ALL_10_DAY_LOW")
    next_add = None
    if units < t["maximum_units_per_symbol"]:
        next_add = round(unit_fill_prices[-1] + t["pyramid_spacing_multiple_N"] * entry_N, 4)
        if not actions and live_price >= next_add:
            actions.append("ADD_UNIT_SUBJECT_TO_RISK_GATE")
    return {
        "symbol": symbol.upper(), "as_of_completed_bar": bars[-1].date, "live_price": live_price,
        "units": units, "entry_N": entry_N, "stop_all_units": round(stop, 4),
        "exit_10_level": lo10, "next_add_level": next_add,
        "actions": actions or ["HOLD"],
        "risk_at_stop_per_share": round(max(0.0, live_price - stop), 4),
    }
