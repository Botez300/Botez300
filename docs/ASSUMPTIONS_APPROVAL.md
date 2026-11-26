# Assumptions awaiting owner approval

Nothing in this table has been approved. Values marked "in use (provisional)" are active in PAPER testing only, as you instructed.
Values marked "blocking" keep the related entries blocked until you decide.

## A. Owner-proposed provisional defaults (Phase 3 message)
| # | Item | Value | Where | Status |
|---|---|---|---|---|
| A1 | Max actionable quote age | 60 s | config.SystemParams / OptionRules | in use (provisional) |
| A2 | Max adverse entry drift | 1% | SystemParams.max_price_drift_pct | in use (provisional) |
| A3 | Earnings blackout | 7 calendar days before | SystemParams.earnings_blackout_days | in use (provisional) |
| A4 | Min option open interest | 500 | OptionRules.min_oi | in use (provisional) |
| A5 | Min daily option volume | 100 | OptionRules.min_volume | in use (provisional) |
| A6 | Max option bid-ask spread | 10% of mid | OptionRules.max_spread_pct | in use (provisional) |
| A7 | Drive polling interval | 60 s | deploy/config.example.json poll_s | in use (provisional) |

## B. Additional assumptions introduced by the build (not specified by you)
| # | Item | Current value | Status |
|---|---|---|---|
| B1 | Credit-spread short-leg delta | 0.15-0.30 | in use (provisional) |
| B2 | Covered-call DTE / delta | 30-45 / 0.15-0.30 | in use (provisional) |
| B3 | LEAPS delta | 0.60-0.80 | in use (provisional) |
| B4 | Option strikes fetched | +/-30% of spot | in use (provisional) |
| B5 | Earnings inside option life | blocks all structures | in use (provisional) |
| B6 | Option expiration guard | close at DTE <= 1 | in use (provisional) |
| B7 | Stock liquidity for entries | avg vol >= 500k sh, >= $10M/day | in use (provisional) |
| B8 | Relative strength (entry check) | excess return vs SPY, 63 days | in use (provisional) |
| B9 | Candidate with any `missing_data` | ineligible | in use (provisional) |
| B10 | `execution_authorized: true` | schema-invalid | in use (provisional) |
| B11 | Paper start equity | $100,000 | in use (provisional) |
| B12 | Daily-report deadline | 09:15 ET | in use (provisional) |
| B13 | CSP max loss | full assignment downside to zero (sizes to 0 on most accounts) | in use (provisional) |
| B14 | Claude escalation | disabled by default; max 5/day; tools disabled | in use (provisional) |

## C. Strategy semantics (BLOCKING: these strategies cannot originate entries until decided)
| # | Strategy | Question | Build's current interpretation |
|---|---|---|---|
| C1 | All | Range(n,o) definition | n bars ending o bars before the latest completed bar (o=0 includes it) |
| C2 | CAN SLIM | Which index for "M" | none chosen (UNVERIFIED) |
| C3 | CAN SLIM | EPS basis (GAAP vs adjusted) | none accepted (UNVERIFIED) |
| C4 | CAN SLIM, Minervini, Turtle | "clearly untradeable spread" threshold | none (UNVERIFIED) |
| C5 | CAN SLIM | IWM holdings vs Russell 2000 index membership | not equivalent; no holdings source |
| C6 | Minervini | Range(100,1) High "equals" test | exact float equality |
| C7 | Weinstein | 3-candle group window semantics | common_anchor (the alternative `independent` is also implemented) |
| C8 | Weinstein, Parabolic | Relative Volume (20,SMA,1) | current bar / SMA20 ending 1 bar back |
| C9 | Parabolic | 10-candle ALL group | common_anchor; the other mode's result is reported too |
| C10 | Parabolic | Bollinger stdev convention | population (ddof=0), SMA basis |
| C11 | Parabolic | ROC scale | percent: 100 x (C/C[-5] - 1) |
| C12 | Magic Formula | ROIC definition | none accepted (UNVERIFIED) |
| C13 | Magic Formula | Operating income source | none accepted; Robinhood would only allow operatingMargin x totalRevenue |
| C14 | Magic Formula | Ranking ties | competition ranking; tie-break EY rank, then ticker |
| C15 | CAN SLIM, Minervini, Turtle, Weinstein, Parabolic | Ranking key | alphabetical, except Parabolic (extension) |
| C16 | All | Entry-confirmation rules after mechanical qualification | not defined, so every entry is blocked |
