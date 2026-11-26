"""Risk limits (from the owner's Phase 2 instructions) and system parameters.
Items marked ASSUMPTION were NOT specified by the owner and need confirmation."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Limits:
    stock_risk_pct: float = 0.005
    option_max_loss_pct: float = 0.005
    daily_halt_pct: float = 0.01
    weekly_halt_pct: float = 0.02
    max_stock_alloc_pct: float = 0.10
    max_open_risk_pct: float = 0.03
    stock_ceiling_pct: float = 0.60
    options_ceiling_pct: float = 0.20
    min_cash_pct: float = 0.20
@dataclass(frozen=True)
class OptionRules:
    directional_dte: tuple = (45, 90); vertical_dte: tuple = (30, 60); csp_dte: tuple = (30, 45); leaps_dte: tuple = (365, 730)
    directional_delta: tuple = (0.60, 0.80); csp_delta: tuple = (0.15, 0.30)
    min_oi: int = 500; min_volume: int = 100; max_spread_pct: float = 0.10
    # ASSUMPTION: owner gave no bands for these; reuse the closest stated band. Confirm.
    credit_spread_short_delta: tuple = (0.15, 0.30)   # short leg of bull-put / bear-call
    covered_call_dte: tuple = (30, 45); covered_call_delta: tuple = (0.15, 0.30)
    leaps_delta: tuple = (0.60, 0.80)
    quote_max_age_s: int = 60
@dataclass(frozen=True)
class SystemParams:   # all ASSUMPTIONS, confirm
    quote_max_age_s: int = 60
    max_price_drift_pct: float = 0.01        # live price vs report current_price
    min_avg_volume: float = 500_000
    min_dollar_volume: float = 10_000_000
    earnings_blackout_days: int = 7
    rs_lookback_days: int = 63               # definition of relative strength = excess return vs SPY
