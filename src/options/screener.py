"""Cash-secured-put screener and ranking.

Mandatory gates (any failure -> contract rejected):
  DTE window, delta band, positive bid & valid quote, confirmed regime for the
  ETF, Greeks present (never invented), hard liquidity floor.
Preferences (failure -> CONDITIONAL, not rejected):
  open interest >= preferred, spread <= preferred % of mid.
Portfolio-specific gates (collateral, conflicts, drawdown) live in src/risk.
Returns an empty list -> "NO QUALIFIED TRADE".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.config import Pair, pair_for_symbol
from src.data.models import OptionQuote
from src.regime.classifier import Regime, RegimeResult

NO_QUALIFIED_TRADE = "NO QUALIFIED TRADE"


@dataclass
class Candidate:
    quote: OptionQuote
    pair: str
    group: str
    regime: str
    dte: int
    abs_delta: float
    credit_mid: float
    collateral_per_contract: float
    premium_yield: float           # mid credit / collateral
    annualized_yield: float
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    preference_flags: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return not self.rejections

    @property
    def label(self) -> str:
        q = self.quote
        return f"{q.symbol} {q.expiration.isoformat()} {q.strike:g}P"


def _band(scfg: dict[str, Any], group: str) -> tuple[float, float]:
    lo, hi = scfg["delta_bands"][group]
    return float(lo), float(hi)


def evaluate_contract(
    q: OptionQuote,
    as_of: date,
    regimes: dict[str, RegimeResult],
    cfg: dict[str, Any],
    iv_rv: dict[str, float] | None = None,
) -> Candidate:
    scfg = cfg["screener"]
    pair: Pair | None = pair_for_symbol(cfg, q.symbol)
    group = pair.group if pair else "unknown"
    dte = q.dte(as_of)
    abs_delta = abs(q.delta) if q.delta is not None else float("nan")
    mid = q.mid if q.bid > 0 and q.ask > 0 else 0.0
    coll = q.strike * q.multiplier
    py = mid * q.multiplier / coll if coll > 0 else 0.0
    ann = py * 365.0 / dte if dte > 0 else 0.0
    c = Candidate(q, pair.name if pair else "?", group, "?", dte, abs_delta, mid, coll, py, ann)

    if pair is None:
        c.rejections.append("symbol not in configured universe")
        return c
    if q.option_type != "put":
        c.rejections.append("not a put")
    rr = regimes.get(pair.name)
    c.regime = rr.regime.value if rr else "MISSING"
    if rr is None or rr.regime is Regime.NEUTRAL:
        c.rejections.append("regime NEUTRAL/unconfirmed: no new positions")
    elif rr.trade_symbol != q.symbol:
        c.rejections.append(f"regime {rr.regime.value} selects {rr.trade_symbol}, not {q.symbol}")
    if not (scfg["dte_min"] <= dte <= scfg["dte_max"]):
        c.rejections.append(f"DTE {dte} outside {scfg['dte_min']}-{scfg['dte_max']}")
    if q.delta is None or q.iv is None:
        c.rejections.append("Greeks/IV missing from verified quote (not invented)")
    else:
        lo, hi = _band(scfg, group)
        if not (lo <= abs_delta <= hi):
            c.rejections.append(f"|delta| {abs_delta:.3f} outside {lo:.2f}-{hi:.2f}")
    if q.bid <= 0:
        c.rejections.append("no positive bid")
    if q.ask <= 0 or q.ask < q.bid:
        c.rejections.append("invalid ask")
    if q.open_interest < scfg["hard_min_open_interest"]:
        c.rejections.append(f"OI {q.open_interest} below hard floor {scfg['hard_min_open_interest']}")
    if mid > 0 and q.spread_pct > scfg["hard_max_spread_pct"]:
        c.rejections.append(f"spread {q.spread_pct:.0%} of mid above hard max {scfg['hard_max_spread_pct']:.0%}")
    if q.open_interest < scfg["preferred_min_open_interest"]:
        c.preference_flags.append(f"OI {q.open_interest} < preferred {scfg['preferred_min_open_interest']}")
    if mid > 0 and q.spread_pct > scfg["preferred_max_spread_pct"]:
        c.preference_flags.append(f"spread {q.spread_pct:.1%} > preferred {scfg['preferred_max_spread_pct']:.0%}")

    # ---- ranking components in [0,1]
    lo, hi = _band(scfg, group)
    w = scfg["weights"]
    trend = rr.strength if rr else 0.0
    liq = 0.5 * min(q.open_interest / 2000.0, 1.0) + 0.5 * max(0.0, 1.0 - (q.spread_pct if mid else 1.0) / scfg["hard_max_spread_pct"])
    prem = min(ann / 0.60, 1.0)
    dlt = 1.0 - min(max((abs_delta - lo) / (hi - lo), 0.0), 1.0) if hi > lo and abs_delta == abs_delta else 0.0
    corr = 1.0  # adjusted per-portfolio in the risk engine
    ev = 1.0
    if iv_rv and q.iv is not None and q.symbol in iv_rv and iv_rv[q.symbol] > 0:
        ratio = q.iv / iv_rv[q.symbol]
        ev = 1.0 if 0.9 <= ratio <= 1.6 else 0.5  # extreme IV/RV gaps flag event/vol risk
    c.components = {"trend": trend, "liquidity": liq, "premium": prem, "delta": dlt, "correlation": corr, "event_vol": ev}
    c.score = sum(w[k] * v for k, v in c.components.items())
    return c


def screen(
    quotes: list[OptionQuote],
    as_of: date,
    regimes: dict[str, RegimeResult],
    cfg: dict[str, Any],
    iv_rv: dict[str, float] | None = None,
) -> tuple[list[Candidate], list[Candidate]]:
    """Return (eligible ranked desc, rejected). Highest premium is never auto-selected."""
    evaluated = [evaluate_contract(q, as_of, regimes, cfg, iv_rv) for q in quotes]
    eligible = sorted((c for c in evaluated if c.eligible), key=lambda c: c.score, reverse=True)
    rejected = [c for c in evaluated if not c.eligible]
    return eligible, rejected


def nearest_misses(rejected: list[Candidate], cfg: dict[str, Any], n: int = 3) -> list[Candidate]:
    """Contracts that pass all contract-level gates except regime (for transparency)."""
    def only_regime(c: Candidate) -> bool:
        return all("regime" in r for r in c.rejections)
    misses = [c for c in rejected if only_regime(c)]
    return sorted(misses, key=lambda c: c.score, reverse=True)[:n]
