"""Flush Reversal signal engine for Robinhood MCP data.

Reads raw JSON responses saved from these Robinhood MCP tools:
  - get_equity_historicals (interval=minute): the underlying (SPY or QQQ) + breadth basket
  - get_equity_historicals (interval=day): prior closes for the basket
  - get_index_historicals (interval=minute): VIX

Robinhood has no NYSE TICK, ADD or TRIN, so this builds stand-ins from a
basket of mega-cap stocks:
  TICK proxy = (# basket names up on the minute - # down) / N * 1000
  ADD  proxy = (# names above prior close - # below) / N * 1000
  TRIN proxy = (adv / dec) / (adv volume / dec volume), rolling 5 minutes

Usage:
  python signals.py <cache_dir> [--underlying SPY] [--blackout 10:00,14:00]
Prints every rule event for the session and the current state as JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Thresholds on the proxy scale (+/-1000). Calibrate against your own replays.
TICK_SETUP = -700      # card: TICK <= -900 on real NYSE TICK
TICK_EXIT = 800        # card: TICK >= +800 (with ~20 names: 18 up, 2 down)
TRIN_APLUS = 1.5
CONFIRM_BARS = 3
ENTRY_WINDOW_BARS = 10
OPEN_SKIP_MIN = 5
BLACKOUT_MIN = 15
TRIN_WINDOW = 5
ADD_FULL_PCT = 1.0     # a name down 1% vs prior close counts as a full decliner


@dataclass
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


def _bar(raw: dict) -> Bar | None:
    if raw.get("interpolated"):
        return None
    g = lambda k: float(raw.get(f"{k}_price", raw.get(f"{k}_value", 0)) or 0)
    t = datetime.fromisoformat(raw["begins_at"].replace("Z", "+00:00")).astimezone(ET)
    return Bar(t, g("open"), g("high"), g("low"), g("close"), float(raw.get("volume", 0) or 0))


def load_cache(cache_dir: Path):
    """Merge every saved MCP response in cache_dir. Later files win on duplicates."""
    minute: dict[str, dict[datetime, Bar]] = {}
    daily: dict[str, list[Bar]] = {}
    for f in sorted(cache_dir.glob("*.json")):
        doc = json.loads(f.read_text())
        for res in doc.get("data", doc).get("results", []):
            sym = res["symbol"]
            bars = [b for b in map(_bar, res.get("bars", [])) if b]
            if res.get("interval") == "day":
                daily.setdefault(sym, []).extend(bars)
            else:
                d = minute.setdefault(sym, {})
                for b in bars:
                    d[b.t] = b
    minute_sorted = {s: [d[k] for k in sorted(d)] for s, d in minute.items()}
    return minute_sorted, daily


def prior_closes(daily: dict[str, list[Bar]], session_day) -> dict[str, float]:
    out = {}
    for sym, bars in daily.items():
        before = [b for b in sorted(bars, key=lambda b: b.t) if b.t.date() < session_day]
        if before:
            out[sym] = before[-1].c
    return out


def internals(basket: dict[str, list[Bar]], prev: dict[str, float]) -> dict[datetime, dict]:
    """Per-minute TICK / ADD / TRIN proxies."""
    by_t: dict[datetime, list[tuple[str, Bar, Bar | None]]] = {}
    for sym, bars in basket.items():
        for i, b in enumerate(bars):
            by_t.setdefault(b.t, []).append((sym, b, bars[i - 1] if i else None))
    out, hist = {}, []
    for t in sorted(by_t):
        rows = by_t[t]
        n = len(rows)
        up = sum(1 for _, b, p in rows if p and b.c > p.c)
        dn = sum(1 for _, b, p in rows if p and b.c < p.c)
        # TRIN uses this minute's up/down names and volume, summed over a rolling window
        adv = [b for _, b, p in rows if p and b.c > p.c]
        dec = [b for _, b, p in rows if p and b.c < p.c]
        hist.append((len(adv), len(dec), sum(b.v for b in adv), sum(b.v for b in dec)))
        a, d, av, dv = (sum(x[i] for x in hist[-TRIN_WINDOW:]) for i in range(4))
        trin = (a / d) / (av / dv) if a and d and av and dv else None
        # ADD: with only ~20 names a pure count is too lumpy, so each name scores
        # -1..+1 by its % change vs prior close (+/-ADD_FULL_PCT = full advancer/decliner)
        scores = [max(-1.0, min(1.0, (b.c / prev[s] - 1) * 100 / ADD_FULL_PCT))
                  for s, b, _ in rows if s in prev]
        out[t] = {
            "tick": round((up - dn) / n * 1000),
            "add": round(sum(scores) / len(scores) * 1000) if scores else None,
            "trin": round(trin, 2) if trin else None,
        }
    return out


@dataclass
class State:
    phase: str = "WAIT"            # WAIT -> SETUP -> CONFIRMED -> IN_TRADE
    setup_i: int | None = None
    entry_i: int | None = None
    flush_high: float = 0.0
    flush_low: float = 0.0
    a_plus: bool = False
    vix_peak: float = 0.0
    add_low: float = 0.0
    partial_taken: bool = False
    tightened: bool = False
    events: list = field(default_factory=list)


def _blocked(t: datetime, blackouts: list[time]) -> str | None:
    open_ = t.replace(hour=9, minute=30, second=0)
    if t < open_ + timedelta(minutes=OPEN_SKIP_MIN):
        return "first 5 min of the open"
    if t.time() >= time(15, 45):
        return "closing auction window"
    for bt in blackouts:
        ev = t.replace(hour=bt.hour, minute=bt.minute, second=0)
        if abs((t - ev).total_seconds()) <= BLACKOUT_MIN * 60:
            return f"within {BLACKOUT_MIN} min of {bt:%H:%M} release"
    return None


def run(underlying: list[Bar], vix: list[Bar], ints: dict, blackouts: list[time]) -> State:
    s = State()
    vix_at = {b.t: b for b in vix}
    cum_pv = cum_v = 0.0
    day_low = float("inf")

    def log(i, kind, msg, **kw):
        s.events.append({"time": underlying[i].t.strftime("%H:%M"), "rule": kind, "msg": msg, **kw})

    for i, b in enumerate(underlying):
        cum_pv += (b.h + b.l + b.c) / 3 * b.v
        cum_v += b.v
        vwap = cum_pv / cum_v if cum_v else b.c
        it = ints.get(b.t, {})
        tick, add, trin = it.get("tick"), it.get("add"), it.get("trin")
        vx = vix_at.get(b.t)
        new_low = b.l < day_low
        day_low = min(day_low, b.l)

        if s.phase == "IN_TRADE":
            # Rule 4: stop
            if b.l < s.flush_low or (vx and vx.h > s.vix_peak):
                why = "flush low broke" if b.l < s.flush_low else f"VIX new high {vx.h}"
                log(i, "4 STOP", f"Exit all: {why}", price=b.c)
                s = State(events=s.events)
                continue
            # Rule 5: exits
            if not s.partial_taken and (b.h >= vwap or (tick is not None and tick >= TICK_EXIT)):
                s.partial_taken = True
                log(i, "5 EXIT", "Take partial (VWAP touch or TICK proxy high)", price=b.c, vwap=round(vwap, 2), tick=tick)
            # TRIN window still holds flush volume right after entry, so wait it out
            settled = i - s.entry_i >= TRIN_WINDOW
            if not s.tightened and settled and trin and trin > 1 and b.c > underlying[i - 1].c:
                s.tightened = True
                log(i, "5 EXIT", "TRIN > 1 while price rises: tighten stop to this bar's low", stop=b.l, trin=trin)
            if s.tightened and b.c < underlying[i - 1].l:
                log(i, "5 EXIT", "Tightened stop hit: exit remainder", price=b.c)
                s = State(events=s.events)
            continue

        # A fresh low below the tracked flush resets any pending setup (Rule 6).
        # If the setup was still unconfirmed, it just rolls to the new low quietly.
        rolling = False
        if s.phase in ("SETUP", "CONFIRMED") and b.l < s.flush_low:
            rolling = s.phase == "SETUP"
            if s.phase == "CONFIRMED":
                log(i, "6 NO TRADE", "New low after confirmation: wait for steps 1-3 to reset")
            s = State(events=s.events)

        if s.phase == "WAIT":
            if new_low and i > 0 and tick is not None and tick <= TICK_SETUP:
                blocked = _blocked(b.t, blackouts)
                if blocked:
                    log(i, "6 NO TRADE", f"Flush ignored: {blocked}", tick=tick)
                    continue
                s.phase, s.setup_i = "SETUP", i
                s.flush_high, s.flush_low = b.h, b.l
                s.a_plus = bool(trin and trin >= TRIN_APLUS)
                s.vix_peak = vx.h if vx else 0.0
                s.add_low = add if add is not None else 0
                if not rolling:
                    log(i, "1 SETUP", "New intraday low on heavy selling"
                        + (" (A+: TRIN spike)" if s.a_plus else ""), tick=tick, trin=trin, low=b.l)
            continue

        bars_since = i - s.setup_i
        vix_new_high = False
        if vx and s.phase == "SETUP":  # peak keeps rising until VIX rolls over
            vix_new_high = vx.h > s.vix_peak
            s.vix_peak = max(s.vix_peak, vx.h)
        if add is not None and add < s.add_low:
            s.add_low = add

        if s.phase == "SETUP":
            if bars_since > CONFIRM_BARS:
                log(i, "2 CONFIRM", "Not confirmed within 3 bars: setup dropped")
                s = State(events=s.events)
                continue
            vix_ok = vx is not None and not vix_new_high and vx.c < s.vix_peak
            add_ok = add is not None and add > s.add_low
            trin_ok = trin is None or trin < 1 or trin < (ints.get(underlying[s.setup_i].t, {}).get("trin") or 99)
            if vix_ok and add_ok and trin_ok:
                s.phase = "CONFIRMED"
                log(i, "2 CONFIRM", "VIX rolled over, ADD turned up, TRIN easing",
                    flush_bar=underlying[s.setup_i].t.strftime("%H:%M"), flush_low=s.flush_low, vix=vx.c, vix_peak=s.vix_peak, add=add, trin=trin)
            continue

        if s.phase == "CONFIRMED":
            if bars_since > ENTRY_WINDOW_BARS:
                log(i, "3 ENTRY", "No breakout within the entry window: setup dropped")
                s = State(events=s.events)
                continue
            if add is not None and add <= s.add_low:
                log(i, "6 NO TRADE", "ADD still making new lows", add=add)
                continue
            if b.c > s.flush_high and not _blocked(b.t, blackouts):
                s.phase, s.entry_i = "IN_TRADE", i
                log(i, "3 ENTRY", "Close above flush-bar high: buy ATM/1-OTM calls at the mid",
                    price=b.c, stop_underlying=s.flush_low, vix_stop=s.vix_peak, a_plus=s.a_plus)
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir", type=Path)
    ap.add_argument("--underlying", default="SPY")
    ap.add_argument("--blackout", default="", help="ET times of scheduled releases, e.g. 10:00,14:00")
    a = ap.parse_args(argv)

    minute, daily = load_cache(a.cache_dir)
    if a.underlying not in minute or "VIX" not in minute:
        sys.exit(f"cache needs minute bars for {a.underlying} and VIX")
    und = minute.pop(a.underlying)
    vix = minute.pop("VIX")
    day = und[-1].t.date()
    und = [b for b in und if b.t.date() == day]
    basket = {k: [b for b in v if b.t.date() == day] for k, v in minute.items()}
    prev = prior_closes(daily, day)
    missing = sorted(set(basket) - set(prev))
    blackouts = [time.fromisoformat(x) for x in a.blackout.split(",") if x]

    ints = internals(basket, prev)
    st = run(und, vix, ints, blackouts)
    last = ints.get(und[-1].t, {})
    print(json.dumps({
        "session": str(day),
        "basket_size": len(basket),
        "basket_missing_prior_close": missing,
        "last_bar": und[-1].t.strftime("%H:%M ET"),
        "internals_now": last,
        "phase": st.phase,
        "events": st.events,
    }, indent=2))


if __name__ == "__main__":
    main()
