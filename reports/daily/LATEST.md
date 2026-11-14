# LEGION QUANT CAPITAL — Daily PAPER Report · 2026-11-14

> **PAPER TRADING ONLY.** No live orders exist or can be created by this system. Labels: [VERIFIED] Verified market data · [CALC] Calculated indicator · [SIM] Simulated execution · [ASSUMPTION] Research assumption · [MISSING] Missing/unverified data.

**Headline:** NO QUALIFIED TRADE — all regimes NEUTRAL; remaining in simulated cash

## Market regime (completed daily/weekly candles)

| Pair | Regime | Trade ETF | Last bar | Bench vs SMA200 | SMA50>SMA200 | RSI d/w/m | Bull ETF trend | Bear ETF trend | RS bull/bear | Vol ratio | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NASDAQ100 (QQQ) | **NEUTRAL** [CALC] | — | 2026-11-13 | 679.89 vs 682.24 | True | 42.8/45.8/62.53 | False | True | - (-22.5%) | 2.00 | unstable: SMA200 crosses=3 in window, vol ratio=2.00 |
| SP500 (SPY) | **NEUTRAL** [CALC] | — | 2026-11-13 | 754.37 vs 731.92 | True | 47.1/52.6/71.26 | False | True | - (-7.8%) | 1.83 | conflicting technical signals |
| SEMIS (SOXX) | **NEUTRAL** [CALC] | — | 2026-11-13 | 149.30 vs 160.39 | True | 42.1/43.4/59.6 | False | True | - (-39.6%) | 2.01 | unstable: SMA200 crosses=1 in window, vol ratio=2.01 |

## Underlying prices (last regular-session trade)

TQQQ 57.67 · SQQQ 42.47 · UPRO 138.51 · SPXU 35.80 · SOXL 58.35 · SOXS 50.78 · QQQ 679.90 · SPY 754.25 · SOXX 149.34 [VERIFIED]

## Top eligible CSP opportunities (all portfolios)

**NO QUALIFIED TRADE.**

Closest contracts that failed ONLY the regime gate (for transparency, NOT proposals):

| Contract | Δ | Bid | Ask | Spread % | OI | Collateral | Ann. yield (mid) |
|---|---|---|---|---|---|---|---|
| TQQQ 2026-12-18 42P | -0.113 | 1.05 | 1.12 | 6% | 1137 | $4,200.00 | 28% |
| TQQQ 2026-12-18 45P | -0.151 | 1.42 | 1.50 | 5% | 7903 | $4,500.00 | 35% |
| TQQQ 2026-12-11 45P | -0.137 | 1.08 | 1.28 | 17% | 1040 | $4,500.00 | 35% |

Screened 117 verified put quotes; rejection reasons (count): regime not confirmed ×117, delta outside band ×87, spread > hard max ×63, OI < hard floor ×32, no positive bid ×7

## Portfolio A — $5,000  ·  PAPER

| Item | Value |
|---|---|
| Starting capital | $5,000.00 [SIM] |
| Current simulated equity | $5,000.00 [SIM] |
| Available simulated cash (unencumbered) | $5,000.00 [SIM] |
| Reserved collateral (incl. pending) | $0.00 [SIM] |
| Realized P&L | $0.00 [SIM] |
| Unrealized option P&L | $0.00 [SIM] |
| Month-to-date net return | +0.00% [CALC] |
| Progress vs 5% monthly stretch objective | 0% of target [CALC] |
| Cumulative compounded return | +0.00% [CALC] |
| Maximum drawdown (paper history) | 0.00% [CALC] |
| Breakers: daily / weekly / from high | 0.00% / 0.00% / 0.00% [CALC] |
| Halted / review required | False / False |

### Open PAPER put positions
_None — 100% simulated cash._

### Assigned underlying shares
_None._

### Simulated orders and fills (latest 5)
_None._

### Proposed PAPER positions (top 3) and risk-gate verdicts
**NO QUALIFIED TRADE** — no contract satisfied every mandatory screening requirement.

### Shadow proposals — ILLUSTRATIVE ONLY (regime gate waived; not actionable, never submitted)
- would be **VETO** · TQQQ 2026-12-18 42P · collateral $4,200.00 vs max $2,000.00 [CALC]
    - VETO: collateral/contract $4,200 > 40% of risk capital $5,000 ($2,000)
    - VETO: total collateral $4,200 > 40% of risk capital
    - VETO: unencumbered cash after entry $800 < 60% of equity
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill
- would be **VETO** · TQQQ 2026-12-18 45P · collateral $4,500.00 vs max $2,000.00 [CALC]
    - VETO: collateral/contract $4,500 > 40% of risk capital $5,000 ($2,000)
    - VETO: total collateral $4,500 > 40% of risk capital
    - VETO: unencumbered cash after entry $500 < 60% of equity
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill
- would be **VETO** · TQQQ 2026-12-11 45P · collateral $4,500.00 vs max $2,000.00 [CALC]
    - VETO: collateral/contract $4,500 > 40% of risk capital $5,000 ($2,000)
    - VETO: total collateral $4,500 > 40% of risk capital
    - VETO: unencumbered cash after entry $500 < 60% of equity
    - CONDITION: spread 16.9% > preferred 10%
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill

### Management log
_No open positions to manage._

### Independent Risk Quant assessment
- Max collateral per contract right now: $2,000.00 -> max strike ≈ $20.00 [CALC].
- No universe ETF is affordable at a typical 0.80x-spot strike: this account would remain in cash even in a confirmed regime. This is a capital-size constraint, not a signal.
- All regimes NEUTRAL: correct action is to hold simulated cash. No trade is the trade.
- 63 contracts rejected for spreads beyond the hard limit [VERIFIED]: end-of-session quotes are wide; re-validate during regular hours before any simulated fill.
- Structural risks: 3x daily-reset ETFs suffer volatility decay and can gap 15-30% overnight; a short put is long that gap risk. Drawdown breakers are operational controls, not loss limits.
- 5% monthly is a stretch research target only; position size is never increased to chase it.

## Portfolio B — $10,000  ·  PAPER

| Item | Value |
|---|---|
| Starting capital | $10,000.00 [SIM] |
| Current simulated equity | $10,000.00 [SIM] |
| Available simulated cash (unencumbered) | $10,000.00 [SIM] |
| Reserved collateral (incl. pending) | $0.00 [SIM] |
| Realized P&L | $0.00 [SIM] |
| Unrealized option P&L | $0.00 [SIM] |
| Month-to-date net return | +0.00% [CALC] |
| Progress vs 5% monthly stretch objective | 0% of target [CALC] |
| Cumulative compounded return | +0.00% [CALC] |
| Maximum drawdown (paper history) | 0.00% [CALC] |
| Breakers: daily / weekly / from high | 0.00% / 0.00% / 0.00% [CALC] |
| Halted / review required | False / False |

### Open PAPER put positions
_None — 100% simulated cash._

### Assigned underlying shares
_None._

### Simulated orders and fills (latest 5)
_None._

### Proposed PAPER positions (top 3) and risk-gate verdicts
**NO QUALIFIED TRADE** — no contract satisfied every mandatory screening requirement.

### Shadow proposals — ILLUSTRATIVE ONLY (regime gate waived; not actionable, never submitted)
- would be **VETO** · TQQQ 2026-12-18 42P · collateral $4,200.00 vs max $4,000.00 [CALC]
    - VETO: collateral/contract $4,200 > 40% of risk capital $10,000 ($4,000)
    - VETO: total collateral $4,200 > 40% of risk capital
    - VETO: unencumbered cash after entry $5,800 < 60% of equity
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill
- would be **VETO** · TQQQ 2026-12-18 45P · collateral $4,500.00 vs max $4,000.00 [CALC]
    - VETO: collateral/contract $4,500 > 40% of risk capital $10,000 ($4,000)
    - VETO: total collateral $4,500 > 40% of risk capital
    - VETO: unencumbered cash after entry $5,500 < 60% of equity
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill
- would be **VETO** · TQQQ 2026-12-11 45P · collateral $4,500.00 vs max $4,000.00 [CALC]
    - VETO: collateral/contract $4,500 > 40% of risk capital $10,000 ($4,000)
    - VETO: total collateral $4,500 > 40% of risk capital
    - VETO: unencumbered cash after entry $5,500 < 60% of equity
    - CONDITION: spread 16.9% > preferred 10%
    - CONDITION: quote is from last completed session: must be re-validated with a fresh RTH quote before any simulated fill

### Management log
_No open positions to manage._

### Independent Risk Quant assessment
- Max collateral per contract right now: $4,000.00 -> max strike ≈ $40.00 [CALC].
- ETFs affordable at ~0.80x-spot strike: SQQQ, SPXU [CALC].
- All regimes NEUTRAL: correct action is to hold simulated cash. No trade is the trade.
- 63 contracts rejected for spreads beyond the hard limit [VERIFIED]: end-of-session quotes are wide; re-validate during regular hours before any simulated fill.
- Structural risks: 3x daily-reset ETFs suffer volatility decay and can gap 15-30% overnight; a short put is long that gap risk. Drawdown breakers are operational controls, not loss limits.
- 5% monthly is a stretch research target only; position size is never increased to chase it.
