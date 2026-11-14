"""Simulated trade-management rules for open PAPER short puts.

Never rolls automatically. Any adjustment would re-enter through the risk engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ManagementAction:
    action: str      # HOLD | CLOSE | FLAG
    reason: str


def evaluate_position(
    entry_credit: float,
    mark: float,
    expiration: date,
    as_of: date,
    strike: float,
    underlying: float,
    regime_still_valid: bool,
    mcfg: dict[str, Any],
) -> list[ManagementAction]:
    acts: list[ManagementAction] = []
    dte = (expiration - as_of).days
    retained = (entry_credit - mark) / entry_credit if entry_credit > 0 else 0.0
    if retained >= mcfg["profit_target_pct"]:
        acts.append(ManagementAction("CLOSE", f"profit target: {retained:.0%} of credit retained"))
    if dte <= mcfg["reassess_dte"]:
        acts.append(ManagementAction("CLOSE", f"{dte} DTE <= {mcfg['reassess_dte']}: close before expiration"))
    if mark >= mcfg["stop_flag_multiple"] * entry_credit:
        kind = "CLOSE" if mcfg["stop_action"] == "close" else "FLAG"
        acts.append(ManagementAction(kind, f"close cost {mark:.2f} >= {mcfg['stop_flag_multiple']}x credit {entry_credit:.2f}"))
    if not regime_still_valid:
        kind = "CLOSE" if mcfg["close_on_regime_loss"] else "FLAG"
        acts.append(ManagementAction(kind, "market regime deteriorated: immediate reassessment"))
    extrinsic = mark - max(strike - underlying, 0.0)
    if underlying < strike and extrinsic < mcfg["early_assignment_extrinsic"] and dte <= 5:
        acts.append(ManagementAction("FLAG", f"early-assignment risk: ITM with extrinsic {extrinsic:.2f}"))
    if not acts:
        acts.append(ManagementAction("HOLD", "no management trigger"))
    return acts
