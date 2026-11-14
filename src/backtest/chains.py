"""Historical-options data adapter (GENUINE historical backtests).

STATUS: No verified historical option-chain dataset is available in this
environment. Robinhood's MCP exposes ``get_option_historicals`` (OHLC trade
bars per contract, including expired contracts via get_option_instruments
state='expired'), but NOT historical bid/ask, Greeks or open interest, and
pulling every contract for a multi-year chain through MCP is impractical.
Therefore the engine does not claim any genuine historical options result.

To run a genuine historical backtest, supply a CSV per underlying in
``data/options_history/<SYMBOL>.csv`` with columns:

    date,expiration,strike,type,bid,ask,delta,iv,open_interest,volume,source

from a documented vendor (e.g. OPRA-derived end-of-day data). This adapter
validates the schema and exposes per-day chains; the engine's option model can
then be swapped from ``SyntheticOptions`` to these quotes. Rows with missing
bid/ask/delta are treated as unavailable (never filled or interpolated).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.config import ROOT

OPTIONS_HISTORY_DIR = ROOT / "data" / "options_history"
REQUIRED = ["date", "expiration", "strike", "type", "bid", "ask", "delta", "iv", "open_interest", "volume", "source"]


class HistoricalOptionsUnavailable(RuntimeError):
    pass


def available_symbols(base: Path | None = None) -> list[str]:
    d = base or OPTIONS_HISTORY_DIR
    return sorted(p.stem for p in d.glob("*.csv")) if d.exists() else []


def load_chain_history(symbol: str, base: Path | None = None) -> pd.DataFrame:
    path = (base or OPTIONS_HISTORY_DIR) / f"{symbol}.csv"
    if not path.exists():
        raise HistoricalOptionsUnavailable(
            f"No verified historical option quotes for {symbol} ({path}). "
            "Genuine historical options backtest NOT RUN; only the HYPOTHETICAL simulation is available."
        )
    df = pd.read_csv(path)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["expiration"] = pd.to_datetime(df["expiration"]).dt.date
    valid = df[["bid", "ask", "delta"]].notna().all(axis=1) & (df["ask"] >= df["bid"]) & (df["bid"] >= 0)
    return df[valid].reset_index(drop=True)


def chain_on(df: pd.DataFrame, d: date) -> pd.DataFrame:
    return df[df["date"] == d]
