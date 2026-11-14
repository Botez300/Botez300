# LEGION — Historical Backtest Report (PAPER research)

**Mode:** HYPOTHETICAL (synthetic option prices on verified underlying bars).  **Period:** 2018-01-01 → 2026-11-13.  **Generated:** 2026-11-14.

> **Read this first.** No verified historical option-chain dataset (bid/ask/Greeks/OI) was available, so **no genuine historical-options backtest was run**. Every option price below is SYNTHETIC (Black-Scholes on a realized-volatility IV proxy with skew and spread assumptions). Underlying prices are verified Robinhood daily bars. Treat results as a test of the *rules and risk controls*, not as achievable historical P&L. Success rates here are model outputs, not observed fill histories.

## Datasets and assumptions

- Underlying: Robinhood MCP `get_equity_historicals`, daily, 2017-01-03 → 2026-11-13, split-adjusted (indicators) and unadjusted (trading/collateral). 9 symbols × 2,481 bars, 0 interpolated bars. [VERIFIED]
- Data repair: SOXS adjusted bar 2022-03-15 was a 10× outlier that reverted next day; rebuilt from raw × neighbouring factor (see `data/history/data_quality.json`). Split events derived from raw/adjusted ratio (e.g. SQQQ 1:5 reverse ×4, SOXS ×6, TQQQ 2:1 ×4, SOXL 15:1). [CALC]
- Synthetic IV = max(floor 20%, RV20 × 1.0) with skew -1.2 (bull ETFs) / +0.4 (inverse ETFs) per ln(K/S). Snapshot 2026-11-13 check: IV/RV 0.57–0.75 during a vol spike; skew −0.4…−2.3 bull, +0.2…+0.9 inverse. [ASSUMPTION]
- Synthetic spread = 15% of theo (min $0.05); snapshot showed 28–118% median spreads in the delta band at Friday's close, so a 30% stress is reported. [ASSUMPTION]
- Fills: sell = bid + 0.25×(mid−bid) − 1 tick; buy = ask − 0.25×(ask−mid) + 1 tick; fees $0.03/contract. Signals at close d, executions at OPEN d+1 (gap risk captured). [ASSUMPTION]
- Early assignment: assumed when ITM, ≤5 DTE and extrinsic < $0.05. Expiration ITM → assignment at strike; assigned shares liquidated next open (baseline). [ASSUMPTION]
- ETF distributions (small quarterly dividends) are NOT modelled: assigned-share P&L excludes them and put prices ignore ex-dividend drift. [MISSING]
- Trading halts/untradeable sessions are not observable in daily bars; a missing bar is simply no action. [MISSING]
- Risk gates identical to live paper engine (`src/risk/engine.py`); after an 8% halt the backtest assumes a review clears it after 20 sessions. [ASSUMPTION]

## 1. Baseline — full period, provisional settings

| Metric | A baseline | B baseline | SPY B&H (A size) | SPY B&H (B size) | Cash |
|---|---|---|---|---|---|
| end_equity | $5,146.88 | $11,916.20 | $14,033.75 | $28,067.49 | $10,000.00 |
| cagr | 0.33% | 2.00% | 12.35% | 12.35% | 0.00% |
| avg_monthly_return | 0.03% | 0.18% | 1.08% | 1.08% | 0.00% |
| pct_profitable_months | 14.02% | 32.71% | 64.49% | 64.49% | n/a |
| pct_months_ge_5pct | 0.00% | 0.93% | 18.69% | 18.69% | n/a |
| max_drawdown | -8.05% | -10.98% | -34.10% | -34.10% | 0.00% |
| sharpe | 0.17 | 0.43 | 0.71 | 0.71 | n/a |
| sortino | 0.24 | 0.77 | 0.99 | 0.99 | n/a |
| trades | 52 | 130 | n/a | n/a | n/a |
| win_rate | 55.77% | 62.31% | n/a | n/a | n/a |
| profit_factor | 1.19 | 1.55 | n/a | n/a | n/a |
| avg_winner | $32.11 | $66.46 | n/a | n/a | n/a |
| avg_loser | $-34.10 | $-70.75 | n/a | n/a | n/a |
| expectancy | $2.82 | $14.74 | n/a | n/a | n/a |
| assignment_rate | 0.00% | 0.00% | n/a | n/a | n/a |
| max_consecutive_losses | 7 | 4 | n/a | n/a | n/a |
| fees | $3.12 | $7.80 | n/a | n/a | n/a |
| modeled_spread_cost | $591.66 | $1,933.30 | n/a | n/a | n/a |
| return_on_collateral_annualized | 11.00% | 30.58% | n/a | n/a | n/a |
| exposure_pct_days | 9.69% | 24.89% | n/a | n/a | n/a |
| avg_collateral_utilization | 3.14% | 6.51% | n/a | n/a | n/a |

- **A** traded: {'SOXS': 10, 'SQQQ': 3, 'SOXL': 27, 'SPXU': 12}; outcomes: PROFIT_TARGET 25, REGIME_EXIT 27
- **B** traded: {'SOXS': 20, 'SQQQ': 11, 'UPRO': 2, 'SOXL': 77, 'SPXU': 6, 'TQQQ': 14}; outcomes: DTE_EXIT 1, PROFIT_TARGET 66, REGIME_EXIT 63

## 2. In-sample vs out-of-sample (fixed provisional parameters)

| Metric | A IS 2018-21 | A OOS 2022-26 | B IS 2018-21 | B OOS 2022-26 |
|---|---|---|---|---|
| end_equity | $4,809.34 | $6,188.64 | $10,040.42 | $11,838.12 |
| cagr | -0.97% | 4.49% | 0.10% | 3.53% |
| avg_monthly_return | -0.08% | 0.39% | 0.01% | 0.32% |
| pct_profitable_months | 0.00% | 28.81% | 16.67% | 45.76% |
| pct_months_ge_5pct | 0.00% | 1.69% | 0.00% | 1.69% |
| max_drawdown | -4.06% | -4.27% | -1.87% | -10.90% |
| sharpe | -1.26 | 0.81 | 0.10 | 0.57 |
| sortino | -1.31 | 2.36 | 0.13 | 1.04 |
| trades | 11 | 56 | 33 | 98 |
| win_rate | 27.27% | 69.64% | 48.48% | 65.31% |
| profit_factor | 0.12 | 2.51 | 1.08 | 1.62 |
| avg_winner | $8.94 | $50.61 | $34.25 | $74.80 |
| avg_loser | $-27.18 | $-46.18 | $-29.86 | $-86.74 |
| expectancy | $-17.33 | $21.23 | $1.22 | $18.76 |
| assignment_rate | 0.00% | 0.00% | 0.00% | 0.00% |
| max_consecutive_losses | 5 | 2 | 3 | 4 |
| fees | $0.66 | $3.36 | $1.95 | $5.88 |
| modeled_spread_cost | $113.95 | $683.44 | $377.39 | $1,562.20 |
| return_on_collateral_annualized | -181.94% | 60.07% | 3.54% | 36.22% |
| exposure_pct_days | 2.18% | 22.59% | 10.22% | 36.82% |
| avg_collateral_utilization | 0.52% | 7.24% | 2.98% | 9.42% |

## 3. Walk-forward (3-year training → next calendar year, strictly out-of-sample)

**Portfolio A** — OOS CAGR 3.61%, avg month +0.31%, max DD -5.38%, Sharpe 0.72, profitable months 23%.

| Test year | Train window | Chosen params | Train score | Test return | Test trades |
|---|---|---|---|---|---|
| 2021 | 2018-01-01..2020-12-31 | {'delta_target': 0.15, 'profit_target_pct': 0.7, 'stop_action': 'close'} | -0.30 | -1.54% | 2 |
| 2022 | 2019-01-01..2021-12-31 | {'delta_target': 0.12, 'profit_target_pct': 0.5, 'stop_action': 'flag'} | -0.34 | +12.25% | 14 |
| 2023 | 2020-01-01..2022-12-31 | {'delta_target': 0.12, 'profit_target_pct': 0.7, 'stop_action': 'flag'} | 1.00 | +4.45% | 16 |
| 2024 | 2021-01-01..2023-12-31 | {'delta_target': 0.12, 'profit_target_pct': 0.7, 'stop_action': 'flag'} | 1.28 | +0.41% | 6 |
| 2025 | 2022-01-01..2024-12-31 | {'delta_target': 0.12, 'profit_target_pct': 0.7, 'stop_action': 'flag'} | 2.09 | +6.17% | 15 |
| 2026 | 2023-01-01..2025-12-31 | {'delta_target': 0.18, 'profit_target_pct': 0.7, 'stop_action': 'close'} | 2.32 | +0.00% | 0 |

**Portfolio B** — OOS CAGR 3.11%, avg month +0.28%, max DD -8.87%, Sharpe 0.52, profitable months 45%.

| Test year | Train window | Chosen params | Train score | Test return | Test trades |
|---|---|---|---|---|---|
| 2021 | 2018-01-01..2020-12-31 | {'delta_target': 0.18, 'profit_target_pct': 0.7, 'stop_action': 'close'} | -0.08 | +0.87% | 20 |
| 2022 | 2019-01-01..2021-12-31 | {'delta_target': 0.15, 'profit_target_pct': 0.7, 'stop_action': 'flag'} | 0.20 | +9.04% | 22 |
| 2023 | 2020-01-01..2022-12-31 | {'delta_target': 0.18, 'profit_target_pct': 0.5, 'stop_action': 'flag'} | 0.42 | +3.46% | 27 |
| 2024 | 2021-01-01..2023-12-31 | {'delta_target': 0.15, 'profit_target_pct': 0.5, 'stop_action': 'close'} | 0.63 | -0.36% | 18 |
| 2025 | 2022-01-01..2024-12-31 | {'delta_target': 0.15, 'profit_target_pct': 0.7, 'stop_action': 'close'} | 0.61 | +1.83% | 21 |
| 2026 | 2023-01-01..2025-12-31 | {'delta_target': 0.15, 'profit_target_pct': 0.5, 'stop_action': 'flag'} | 1.03 | +3.63% | 6 |

## 4. Variants and sensitivity (Portfolio B rules; '$100k reference' isolates account-size effects)

| Metric | B baseline | +monthly RSI | stop=close@2x | PT 70% | no regime exit | IV/RV 0.8 | IV/RV 1.2 | spread 30% | hold assigned | $100k reference |
|---|---|---|---|---|---|---|---|---|---|---|
| end_equity | $11,916.20 | $11,055.64 | $11,670.78 | $12,170.40 | $14,721.40 | $10,629.56 | $11,765.38 | $9,413.80 | $11,916.20 | $102,746.14 |
| cagr | 2.00% | 1.14% | 1.76% | 2.24% | 4.46% | 0.69% | 1.85% | -0.68% | 2.00% | 0.31% |
| avg_monthly_return | 0.18% | 0.09% | 0.16% | 0.20% | 0.41% | 0.06% | 0.19% | -0.05% | 0.18% | 0.03% |
| pct_profitable_months | 32.71% | 28.97% | 29.91% | 31.78% | 43.93% | 27.10% | 32.71% | 28.04% | 32.71% | 50.47% |
| pct_months_ge_5pct | 0.93% | 0.00% | 0.93% | 0.93% | 0.93% | 0.93% | 0.93% | 0.00% | 0.93% | 0.00% |
| max_drawdown | -10.98% | -3.14% | -9.93% | -8.15% | -15.01% | -4.97% | -17.95% | -13.99% | -10.98% | -3.69% |
| sharpe | 0.43 | 0.57 | 0.39 | 0.49 | 0.55 | 0.26 | 0.28 | -0.24 | 0.43 | 0.22 |
| sortino | 0.77 | 0.72 | 0.70 | 0.93 | 1.12 | 0.40 | 0.42 | -0.28 | 0.77 | 0.26 |
| trades | 130 | 106 | 137 | 110 | 110 | 124 | 127 | 120 | 130 | 281 |
| win_rate | 62.31% | 67.92% | 59.12% | 56.36% | 94.55% | 64.52% | 63.78% | 59.17% | 62.31% | 65.48% |
| profit_factor | 1.55 | 1.67 | 1.44 | 1.76 | 2.53 | 1.25 | 1.35 | 0.80 | 1.55 | 1.16 |
| avg_winner | $66.46 | $36.59 | $67.32 | $80.89 | $75.07 | $38.84 | $83.61 | $32.42 | $66.46 | $106.67 |
| avg_loser | $-70.75 | $-46.44 | $-67.54 | $-59.27 | $-514.23 | $-56.31 | $-108.84 | $-58.94 | $-70.75 | $-174.03 |
| expectancy | $14.74 | $9.96 | $12.20 | $19.73 | $42.92 | $5.08 | $13.90 | $-4.89 | $14.74 | $9.77 |
| assignment_rate | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| max_consecutive_losses | 4 | 3 | 4 | 3 | 2 | 3 | 3 | 3 | 4 | 5 |
| fees | $7.80 | $6.36 | $8.22 | $6.60 | $6.60 | $7.44 | $7.62 | $7.20 | $7.80 | $16.86 |
| modeled_spread_cost | $1,933.30 | $1,209.07 | $2,055.81 | $1,726.47 | $1,483.50 | $1,354.32 | $2,250.78 | $2,639.64 | $1,933.30 | $6,915.91 |
| return_on_collateral_annualized | 30.58% | 19.65% | 27.52% | 33.32% | 42.48% | 11.45% | 25.99% | -11.71% | 30.58% | 6.15% |
| exposure_pct_days | 24.89% | 21.75% | 24.53% | 25.78% | 39.19% | 22.15% | 26.77% | 22.42% | 24.89% | 56.14% |
| avg_collateral_utilization | 6.51% | 5.96% | 6.37% | 6.64% | 9.73% | 6.01% | 6.70% | 6.19% | 6.51% | 4.94% |

## 5. Market environments (SPY-tagged months)

**Portfolio A**

| Scenario | Months | Avg strategy month | % positive | Worst month | Avg SPY month |
|---|---|---|---|---|---|
| bull | 50 | +0.10% | 16% | -1.52% | +2.37% |
| bear | 7 | +0.23% | 29% | -1.54% | -4.95% |
| sideways | 44 | -0.09% | 11% | -1.50% | +0.70% |
| crash | 6 | -0.33% | 17% | -1.54% | -8.23% |
| recovery | 6 | -0.60% | 0% | -1.50% | +8.31% |
| high_vol | 32 | -0.09% | 9% | -1.54% | +0.09% |
| low_vol | 32 | +0.08% | 19% | -0.37% | +1.60% |

**Portfolio B**

| Scenario | Months | Avg strategy month | % positive | Worst month | Avg SPY month |
|---|---|---|---|---|---|
| bull | 50 | +0.17% | 44% | -0.99% | +2.37% |
| bear | 7 | +1.74% | 43% | -5.37% | -4.95% |
| sideways | 44 | -0.03% | 23% | -3.86% | +0.70% |
| crash | 6 | +0.25% | 50% | -0.30% | -8.23% |
| recovery | 6 | -0.98% | 0% | -3.86% | +8.31% |
| high_vol | 32 | +0.27% | 22% | -5.37% | +0.09% |
| low_vol | 32 | +0.05% | 28% | -0.86% | +1.60% |

## 6. Correlation of daily returns (last 252 sessions)

| | QQQ | TQQQ | SQQQ | SPY | UPRO | SPXU | SOXX | SOXL | SOXS |
|---|---|---|---|---|---|---|---|---|---|
| **QQQ** | 1.00 | 1.00 | -1.00 | 0.93 | 0.93 | -0.93 | 0.89 | 0.89 | -0.89 |
| **TQQQ** | 1.00 | 1.00 | -1.00 | 0.93 | 0.93 | -0.93 | 0.89 | 0.90 | -0.89 |
| **SQQQ** | -1.00 | -1.00 | 1.00 | -0.93 | -0.93 | 0.93 | -0.89 | -0.89 | 0.89 |
| **SPY** | 0.93 | 0.93 | -0.93 | 1.00 | 1.00 | -1.00 | 0.75 | 0.75 | -0.74 |
| **UPRO** | 0.93 | 0.93 | -0.93 | 1.00 | 1.00 | -1.00 | 0.75 | 0.75 | -0.75 |
| **SPXU** | -0.93 | -0.93 | 0.93 | -1.00 | -1.00 | 1.00 | -0.74 | -0.75 | 0.74 |
| **SOXX** | 0.89 | 0.89 | -0.89 | 0.75 | 0.75 | -0.74 | 1.00 | 1.00 | -0.99 |
| **SOXL** | 0.89 | 0.90 | -0.89 | 0.75 | 0.75 | -0.75 | 1.00 | 1.00 | -0.98 |
| **SOXS** | -0.89 | -0.89 | 0.89 | -0.74 | -0.75 | 0.74 | -0.99 | -0.98 | 1.00 |

Nasdaq-100, S&P 500 and semiconductor 3× ETFs are highly correlated; bull/bear pairs are ≈ −1. Simultaneous puts on two bull ETFs are close to doubling one position, which is why the risk engine vetoes a second position above 0.8 correlation.

## 7. Compounding: mathematical scenarios vs simulated results

> Projections are arithmetic scenarios (Ending = Start × (1+r)^months), NOT forecasts.

| Start | Monthly | Annualized | Year 1 | Year 5 | Year 10 | Year 15 |
|---|---|---|---|---|---|---|
| $5,000 | 0% | 0.0% | $5,000 | $5,000 | $5,000 | $5,000 |
| $5,000 | 1% | 12.7% | $5,634 | $9,083 | $16,502 | $29,979 |
| $5,000 | 2% | 26.8% | $6,341 | $16,405 | $53,826 | $176,604 |
| $5,000 | 3% | 42.6% | $7,129 | $29,458 | $173,555 | $1,022,517 |
| $5,000 | 5% | 79.6% | $8,979 | $93,396 | $1,744,560 | $32,586,959 |
| $10,000 | 0% | 0.0% | $10,000 | $10,000 | $10,000 | $10,000 |
| $10,000 | 1% | 12.7% | $11,268 | $18,167 | $33,004 | $59,958 |
| $10,000 | 2% | 26.8% | $12,682 | $32,810 | $107,652 | $353,208 |
| $10,000 | 3% | 42.6% | $14,258 | $58,916 | $347,110 | $2,045,034 |
| $10,000 | 5% | 79.6% | $17,959 | $186,792 | $3,489,120 | $65,173,918 |

Simulated A: avg monthly +0.029% → 15-yr extrapolation $5,267 (vs $32,586,959 at the 5% stretch target).

Simulated B: avg monthly +0.180% → 15-yr extrapolation $13,822 (vs $65,173,918 at the 5% stretch target).

## 8. Findings

1. **The 5% monthly target was not approached.** Baseline avg monthly return: A +0.03%, B +0.18%; months ≥5%: A 0%, B 1%. Under these risk limits, 5%/month is not supported by the simulation.
2. **Account size dominates.** With 40% max collateral, A can only sell puts with strikes ≤ ~$20 (exposure 10% of days); B ≤ ~$40 (exposure 25%). The same rules at $100k are in a position 56% of days with return on collateral 6%/yr, but because contract counts are capped (1–2), account-level CAGR is only 0.31%: the caps, not the edge, bound returns at every size tested.
2b. **Zero simulated assignments** in all variants: positions were closed by the profit target, the 7-DTE rule or a regime exit before expiry, so 'hold assigned' equals baseline. Daily-close modelling cannot see intraday early assignment; real assignment risk is under-represented here. [MISSING]
3. **Risk profile.** Max drawdown A -8.05%, B -10.98%; win rate B 62%, profit factor B 1.55. The drawdown halt fired in the sample; breakers limited new risk but did not cap losses on open positions.
4. **Sensitivity.** B CAGR under IV/RV 0.8: 0.69%, 1.2: 1.85%; 30% spreads: -0.68%. Results are highly sensitive to the unverifiable premium/spread model — a further reason they cannot be treated as achievable returns.
5. **Monthly RSI confirmation:** B CAGR 1.14% vs baseline 2.00% (trades 106 vs 130). **2× stop as a close rule:** CAGR 1.76%.
6. **Walk-forward OOS:** A CAGR 3.61%, max DD -5.38%; B CAGR 3.11%, max DD -8.87%. Parameter choices were unstable across years, which argues against over-fitting the screener.
7. **Screener settings remain PROVISIONAL.** Nothing here validates them for live use; they require a genuine historical-options dataset and a forward paper-trading record.