"""Configuration loading. Contains no execution-mode settings by design."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"

_FORBIDDEN_KEYS = {"live_trading", "live", "enable_live", "paper_trading", "broker_orders"}


@dataclass(frozen=True)
class Pair:
    name: str
    benchmark: str
    bull: str
    bear: str
    group: str
    tier: str

    @property
    def etfs(self) -> tuple[str, str]:
        return (self.bull, self.bear)


def _walk_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k).lower())
            keys.extend(_walk_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            keys.extend(_walk_keys(v))
    return keys


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    bad = _FORBIDDEN_KEYS.intersection(_walk_keys(cfg))
    if bad:
        raise ValueError(
            f"config contains forbidden execution-mode keys {sorted(bad)}; "
            "execution mode is hard-coded PAPER and cannot be configured."
        )
    return cfg


def pairs(cfg: dict[str, Any]) -> list[Pair]:
    return [Pair(**p) for p in cfg["universe"]["pairs"]]


def pair_for_symbol(cfg: dict[str, Any], symbol: str) -> Pair | None:
    for p in pairs(cfg):
        if symbol in (p.bull, p.bear):
            return p
    return None


def all_symbols(cfg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for p in pairs(cfg):
        for s in (p.benchmark, p.bull, p.bear):
            if s not in out:
                out.append(s)
    mb = cfg["universe"]["market_benchmark"]
    if mb not in out:
        out.append(mb)
    return out
