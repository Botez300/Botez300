# Owner approvals: consolidated table (Phase 5, 2026-11-26)

This is the single authoritative list. "APPROVED" means approved by the owner's own Phase 4 instruction text; nothing here is approved by an AI recommendation.
Columns: current value / recommended / rationale / risk if wrong / evidence available / backtest needed / blocks activation?

## Already APPROVED by owner (Phase 4), native paper research only
Range(n,o) definition; CAN SLIM native = diluted GAAP EPS (17q) and M on the stock's own SMA200; Parabolic native = same candle within 10, 20 SMA +/- 2 population std,
preceding-20 relvol, percent ROC, close > $5; Weinstein native = common anchor in the last 3 weekly candles; Magic native ROIC structure (TTM NOPAT / average IC); execution
defaults (quote age 60 s, drift 1%, earnings blackout 7 d, OI 500, contract vol 100, options spread 10%, equity spread 0.50%, Drive poll 60 s).

## AWAITING OWNER APPROVAL
| ID | Item | Current | Recommended | Rationale | Risk if wrong | Evidence | Backtest | Blocks activation |
|---|---|---|---|---|---|---|---|---|
| P1 | Parabolic min reward/risk | 2.0 (your proposal) | 2.0 | Matches your proposal; partial-2R exit makes it consistent | Too low -> negative expectancy after costs | none historical | yes | **yes** |
| P2 | Parabolic max stop distance | 8% | 8% | Bounds gap risk on volatile names | Wider -> larger gap losses | INSM shows 17-26% daily moves | yes | **yes** |
| P3 | Consolidation length | 3-10 candles | 3-10 | Your proposal; excludes the anchor itself (no chasing) | Too short -> chasing | INSM: anchor-day only, correctly no setup | yes | **yes** |
| P4 | Contraction (mean TR of consolidation / ATR14 at anchor) | <= 0.80 | 0.80 | Your proposal; measured on consolidation candles only | Loose -> unstable bases | none | yes | **yes** |
| P5 | Max extension of pivot above SMA20 | 20% (testing 15/20/30) | choose after walk-forward; provisional 20% | Middle of the tested set | 15% may starve trades; 30% admits chasing | synthetic only | **yes, required** | **yes** |
| P6 | Entry trigger + permitted range | buy-stop at consolidation high, range [P, P x 1.01], skip gap-opens above range | as current | Deterministic, no subjective labels | slippage on gaps | synthetic tests | yes | **yes** |
| P7 | Parabolic exit configuration | none approved (exit_rules = []) | stop = consolidation low; half at 2R, stop to breakeven; ATR(14) x 3 trail; 20-session max hold | Bounded loss, banks gains, lets runners run, caps dead capital | Untested on real data | none | **yes, required** | **yes** |
| P8 | Exit protections | proposed | failed breakout (close < pivot within 3 sessions), earnings exit within 7 d, ATR5/ATR14 > 2, spread > 0.50% or 5d vol < 50% of 20d | Event-risk control | over-exiting | none | yes | yes |
| A9 | Starting paper equity | **unset (service refuses to start)** | owner chooses | Must not assume $100k or your real balance | wrong sizing context | - | no | **yes** |
| B1 | Credit-spread short-leg delta | 0.15-0.30 | 0.15-0.30 | Mirrors the approved CSP band | assignment frequency | none | yes (needs historical options) | only for credit spreads |
| B2 | Covered call DTE/delta | 30-45 / 0.15-0.30 | same | Mirrors CSP; low call-away odds | capped upside | none | yes | only CC |
| B3 | LEAPS delta | 0.60-0.80 | 0.70-0.85 | Deeper ITM reduces theta/IV exposure for 1-2y holds | less leverage | none | yes | only LEAPS |
| B4 | Option strike scan | +/-30% of spot | +/-30% | Covers 0.15-0.85 deltas for most names | missed contracts on extreme-IV names | recorded SPY chain | no | no |
| B5 | Earnings inside option life | blocks every structure | keep blocking | IV crush/gap risk | fewer trades | - | no | no |
| B6 | Option expiration guard | close at DTE <= 1 | DTE <= 2 for short legs, <= 1 for long | Pin and early-assignment risk is concentrated in the final sessions | assignment | - | no | short options |
| B7 | Stock entry liquidity | avg vol >= 500k sh and >= $10M/day | same | Supports the 0.5% spread rule | excludes small caps | - | no | **yes (all stock entries)** |
| B8 | RS vs SPY (generic entry check) | 63-day excess return | 63-day excess return > 0 | Simple, reproducible | not an IBD-style rating | - | yes | yes (Minervini entry) |
| B9 | Candidate `missing_data` non-empty | ineligible | keep | Conservative | fewer trades | - | no | no |
| B10 | `execution_authorized: true` | schema-invalid | keep | Reports never authorize execution | none | - | no | no |
| B12 | Daily-report deadline | 09:15 ET | 09:15 ET | 15 min after the scheduled 09:00 publication | false alarms | - | no | no |
| B12w | Weekly-report deadline | 21:00 ET Sunday | 21:00 ET | 2 h after 19:00 ET publication | - | - | no | no |
| B13 | CSP max loss | strike - premium (to zero) | keep | Full economic downside (your rule) | sizes most CSPs to 0 | - | no | no |
| B14 | Claude escalation | off; 5/day; no tools; routing per CLAUDE.md | enable after host install | advisory only | cost/noise | one live CLI run succeeded | no | no |
| B15 | ROIC "unusual" tax rate | outside [0%, 50%] -> UNVERIFIED | [0%, 40%] | Excludes one-off tax benefits and charges | excludes some valid firms | AAPL ~17.6% (recorded) | yes | Magic native |
| B16 | Invested capital | LTD noncurrent + LTD current + CP + ST borrowings + equity - cash | add operating lease liabilities when tagged | Closer to economic capital | ROIC overstated for lease-heavy firms | recorded AAPL | yes | Magic native |
| B17 | Financials | excluded if sector contains "financ" | exclude SIC 6000-6799 once SIC is sourced | Bank ROIC is not comparable | misclassification | - | no | Magic native |
| B18 | Native EV | market cap + SEC (debt - cash) | same, plus preferred stock and minority interest when tagged | Standard EV | EV understated | - | no | Magic native |
| B19 | SEC restatements | first-filed value wins; conflicts logged | same (point-in-time) | Avoids look-ahead | uses since-corrected numbers | - | no | no |
| B20 | Same-metric source conflicts | any difference -> UNVERIFIED | 0.5% relative for prices, exact for EPS | Rounding noise should not block | masking real conflicts | INSM reproduced to <= 4e-5 | no | no |
| B22 | Paper fill model | buy at ask x (1 + 0.10%), sell at bid x (1 - 0.10%) | same | Conservative; never fills at last | over-pessimistic | - | no | **yes** |
| B23 | Backtest costs | 0.10% slippage + 0.10% half-spread each way, $0 commission | same | Conservative for liquid names | understated for illiquid | - | - | no |
| B24 | Sector/correlation limits | reported only, not enforced | sector <= 25% of equity; >= 0.8 correlation counts as same position | Concentration control | trade starvation | - | yes | recommended |
| B25 | RISK_HALT latch | any halt -> manual `resume --confirm` | same | Matches your "manual authorization" rule | downtime | - | no | no |
| B26 | Risk-reduction on breach | none (review only) | none until a procedure is specified | No automatic liquidation without approval | larger drawdown | - | no | no |
| C4 | EXACT liquidity "untradeable spread" | unresolved | 0.50% (reuse A8) | Consistency | - | - | no | EXACT scanners |
| C6 | Minervini Range(100,1) "equals" | exact float equality | equality within 1 tick ($0.01) | Avoids float noise | false pass on near-equal | - | no | EXACT Minervini |
| C14 | Magic ranking ties | competition ranking; tie-break EY rank, then ticker | same | Deterministic | - | tested | no | no |
| C15 | Ranking keys (others) | alphabetical; Parabolic by extension | CAN SLIM by C growth; Minervini by RS; Turtle by N-adjusted breakout; Weinstein by relvol; Parabolic by lowest extension | Puts the best-qualified first | - | - | yes | no |
| C16 | Entry thresholds, all native strategies | PROPOSED in specs/native | approve Parabolic first (P1-P6); others later | Parabolic has the fewest data gaps | - | - | yes | **yes** |
| C17 | Native Minervini trend template | proposal (8 published criteria + RS) | approve the criteria, with B8 as the RS definition | Removes the RS-rating dependency | diverges from the exact template | - | yes | Minervini native |
| C18 | Exact indicator sources | unknown | owner names the platform, or TradingView script_id+version | Only you know which platform the specs came from | - | multiple same-named TV scripts found | - | EXACT Minervini, Weinstein, Turtle, CAN SLIM L |
| D1 | Data providers | none beyond Robinhood/SEC/iShares | see docs/DATA_PROVIDERS.md | - | - | - | - | CAN SLIM I |
