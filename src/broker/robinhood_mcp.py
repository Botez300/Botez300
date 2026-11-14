"""Read-only Robinhood MCP integration (snapshot adapter).

Standalone Python cannot invoke Claude Code's authenticated MCP session, and the
system must not use unofficial Robinhood APIs or credentials. Therefore Claude
Code is the integration layer:

  1. Claude Code calls READ-ONLY tools on the official Robinhood Trading MCP
     (https://agent.robinhood.com/mcp/trading).
  2. Tool results are saved to disk (Claude Code writes large results to a
     tool-results file automatically; small ones are written verbatim).
  3. This module imports, validates and normalises those files.

This module contains no network code and no order pathway. Every imported file
must declare which MCP tool produced it; non-allowlisted tools are refused.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import ROOT
from src.data.history import HISTORY_DIR, validate_bars
from src.data.models import EquityQuote, OptionQuote, Snapshot
from src.safety import assert_tool_allowed

SNAPSHOT_DIR = ROOT / "data" / "snapshots"


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    # trim nanoseconds to microseconds
    if "." in s:
        head, tail = s.split(".", 1)
        frac, _, tz = tail.partition("+")
        s = f"{head}.{frac[:6]}+{tz}" if tz else f"{head}.{frac[:6]}"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _f(x: Any) -> float | None:
    if x is None or x == "":
        return None
    return float(x)


# ----------------------------------------------------------------- historicals
def import_equity_historicals(raw_files: list[Path], kind: str, out_dir: Path | None = None) -> dict[str, int]:
    """Merge one or more get_equity_historicals results into per-symbol CSVs.

    ``kind`` is 'adjusted' (adjustment_type=split) or 'raw' (adjustment_type=none).
    Interpolated (gap-fill) bars are dropped. Returns bar counts per symbol.
    """
    assert_tool_allowed("get_equity_historicals")
    if kind not in {"adjusted", "raw"}:
        raise ValueError("kind must be 'adjusted' or 'raw'")
    frames: dict[str, list[dict]] = {}
    for f in raw_files:
        payload = json.loads(Path(f).read_text())
        for res in payload["data"]["results"]:
            sym = res["symbol"]
            if res.get("interval") not in (None, "day"):
                raise ValueError(f"{sym}: expected daily bars, got {res.get('interval')}")
            rows = frames.setdefault(sym, [])
            for b in res["bars"]:
                if b.get("interpolated"):
                    continue
                rows.append(
                    {
                        "date": b["begins_at"][:10],
                        "open": float(b["open_price"]),
                        "high": float(b["high_price"]),
                        "low": float(b["low_price"]),
                        "close": float(b["close_price"]),
                        "volume": int(b["volume"]),
                    }
                )
    out = (out_dir or HISTORY_DIR) / kind
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for sym, rows in frames.items():
        df = pd.DataFrame(rows).drop_duplicates("date", keep="last")
        df = validate_bars(df, sym)
        df.to_csv(out / f"{sym}.csv", index=False)
        counts[sym] = len(df)
    return counts


# ------------------------------------------------------------------- snapshot
def load_instruments(path: Path) -> dict[str, dict]:
    with open(path, newline="") as fh:
        return {r["instrument_id"]: r for r in csv.DictReader(fh)}


def parse_option_quotes(payload: dict, instruments: dict[str, dict]) -> tuple[list[OptionQuote], list[str]]:
    quotes: list[OptionQuote] = []
    problems: list[str] = []
    for res in payload["data"]["results"]:
        q = res["quote"]
        iid = q["instrument_id"]
        meta = instruments.get(iid)
        if meta is None:
            problems.append(f"quote {iid}: no instrument metadata; skipped")
            continue
        try:
            quotes.append(
                OptionQuote(
                    instrument_id=iid,
                    symbol=meta["symbol"],
                    expiration=date.fromisoformat(meta["expiration"]),
                    strike=float(meta["strike"]),
                    option_type=meta["type"],
                    multiplier=int(float(meta["multiplier"])),
                    bid=float(q["bid_price"] or 0),
                    ask=float(q["ask_price"] or 0),
                    bid_size=int(q.get("bid_size") or 0),
                    ask_size=int(q.get("ask_size") or 0),
                    mark=float(q["mark_price"] or 0),
                    iv=_f(q.get("implied_volatility")),
                    delta=_f(q.get("delta")),
                    gamma=_f(q.get("gamma")),
                    theta=_f(q.get("theta")),
                    vega=_f(q.get("vega")),
                    open_interest=int(q.get("open_interest") or 0),
                    volume=int(q.get("volume") or 0),
                    updated_at=_ts(q["updated_at"]),  # type: ignore[arg-type]
                    high_fill_rate_sell_price=_f(q.get("high_fill_rate_sell_price")),
                    high_fill_rate_buy_price=_f(q.get("high_fill_rate_buy_price")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"quote {iid}: malformed ({exc}); skipped")
    return quotes, problems


def load_snapshot(snapshot_dir: Path) -> Snapshot:
    """Load a snapshot directory produced via the Claude Code MCP runbook."""
    manifest = json.loads((snapshot_dir / "manifest.json").read_text())
    for tool in manifest["source_tools"]:
        assert_tool_allowed(tool)
    snap = Snapshot(
        as_of=date.fromisoformat(manifest["as_of"]),
        captured_at=_ts(manifest["captured_at"]),  # type: ignore[arg-type]
        source_tools=list(manifest["source_tools"]),
    )
    eq = json.loads((snapshot_dir / "equity_quotes.json").read_text())
    assert_tool_allowed(eq["source_tool"])
    for q in eq["quotes"]:
        snap.equity_quotes[q["symbol"]] = EquityQuote(
            symbol=q["symbol"],
            last=float(q["last_trade_price"]),
            last_time=_ts(q["last_trade_time"]),  # type: ignore[arg-type]
            bid=_f(q.get("bid")),
            ask=_f(q.get("ask")),
            quote_time=_ts(q.get("quote_time")),
            previous_close=_f(q.get("previous_close")),
            state=q.get("state", "active"),
        )
    chains_path = snapshot_dir / "chains.json"
    if chains_path.exists():
        ch = json.loads(chains_path.read_text())
        assert_tool_allowed(ch["source_tool"])
        snap.chains = ch["chains"]
    oq_path = snapshot_dir / "option_quotes.json"
    if oq_path.exists():
        instruments = load_instruments(snapshot_dir / "instruments.csv")
        quotes, problems = parse_option_quotes(json.loads(oq_path.read_text()), instruments)
        snap.option_quotes = quotes
        snap.problems.extend(problems)
    else:
        snap.problems.append("option_quotes.json missing: no option data in snapshot")
    return snap


def latest_snapshot_dir(base: Path | None = None) -> Path | None:
    b = base or SNAPSHOT_DIR
    dirs = sorted(d for d in b.glob("*") if (d / "manifest.json").exists())
    return dirs[-1] if dirs else None
