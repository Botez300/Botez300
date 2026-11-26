# Assumptions: approval status (updated Phase 4, 2026-11-26)

"APPROVED (Phase 4)" means approved by you in the Phase 4 instructions. The approval covers independent Legion-native paper research only;
it does not claim equivalence to any proprietary platform. Nothing else has been approved.

## A. Execution defaults: APPROVED (Phase 4)
| # | Item | Value | Status |
|---|---|---|---|
| A1 | Max actionable quote age | 60 s | APPROVED |
| A2 | Max adverse price drift | 1% | APPROVED |
| A3 | Earnings blackout | 7 calendar days | APPROVED |
| A4 | Min option open interest | 500 | APPROVED |
| A5 | Min daily contract volume | 100 | APPROVED |
| A6 | Max options bid-ask spread | 10% of mid | APPROVED |
| A7 | Drive polling | 60 s | APPROVED |
| A8 | Max equity bid-ask spread | 0.50% of mid | APPROVED (native gate + native liquidity gate) |

## B. Build assumptions: STILL UNRESOLVED (in use provisionally in PAPER only)
| # | Item | Current value |
|---|---|---|
| B1 | Credit-spread short-leg delta | 0.15-0.30 |
| B2 | Covered-call DTE / delta | 30-45 / 0.15-0.30 |
| B3 | LEAPS delta | 0.60-0.80 |
| B4 | Option strikes fetched | +/-30% of spot |
| B5 | Earnings inside option life | blocks every structure |
| B6 | Option expiration guard | close at DTE <= 1 |
| B7 | Stock liquidity for entries | avg vol >= 500k sh and >= $10M/day |
| B8 | Relative strength (generic entry check) | excess return vs SPY over 63 days |
| B9 | Candidate with any `missing_data` | ineligible |
| B10 | `execution_authorized: true` | schema-invalid |
| B11 | Paper start equity | $100,000 |
| B12 | Daily-report deadline | 09:15 ET |
| B13 | CSP max loss | full assignment downside to zero |
| B14 | Claude escalation | off by default, max 5/day, no tools |
| B15 (new) | Native ROIC "unusual" effective tax rate | outside [0%, 50%] => UNVERIFIED |
| B16 (new) | Native ROIC invested-capital components | LTD noncurrent + LTD current + CP + ST borrowings + equity - cash |
| B17 (new) | Financial institutions (native Magic) | excluded when sector label contains "financ" |
| B18 (new) | Native EV | Robinhood market cap + SEC (debt - cash) |
| B19 (new) | SEC EPS point-in-time policy | first-filed value wins; restatements logged as conflicts |
| B20 (new) | Same-metric source conflicts | any disagreement => UNVERIFIED (tolerance 0 unless set) |
| B21 (new) | Scan strike/expiry universe for Robinhood options | unchanged from B4 |

## C. Strategy semantics
| # | Item | Status |
|---|---|---|
| C1 | Range(n,o) = n completed bars ending o bars before the evaluation bar | APPROVED (Phase 4) |
| C2 | CAN SLIM M (native) = stock close > own SMA200, SMA200 > value 90 sessions earlier | APPROVED for native; EXACT variant still unresolved |
| C3 | CAN SLIM EPS basis = diluted GAAP quarterly, 17 quarters | APPROVED for native |
| C4 | "Clearly untradeable spread" in EXACT liquidity gates | UNRESOLVED (native uses A8) |
| C5 | IWM holdings source | APPROVED direction (official issuer file); live download not yet verified |
| C6 | Minervini Range(100,1) High "equals" test (float equality) | UNRESOLVED |
| C7 | Weinstein window: common anchor, last 3 weekly candles | APPROVED for native research; EXACT stays UNVERIFIED |
| C8 | Relative volume = candle volume / mean of preceding 20 candles | APPROVED (Parabolic native); Weinstein weekly relvol uses the same, UNRESOLVED for EXACT |
| C9 | Parabolic 10-candle group = common anchor | APPROVED (native) |
| C10 | Bollinger = 20 SMA +/- 2 population std | APPROVED (native) |
| C11 | ROC = 100 x C/C[-5] - 100 | APPROVED (native) |
| C12 | ROIC = TTM NOPAT / avg(begin, end invested capital) | APPROVED structure; B15-B17 component choices UNRESOLVED |
| C13 | Operating income source = SEC TTM | APPROVED (native) |
| C14 | Magic ranking ties (competition; tie-break EY rank, ticker) | UNRESOLVED |
| C15 | Ranking keys for CAN SLIM / Minervini / Turtle / Weinstein / Parabolic | UNRESOLVED |
| C16 | Entry-confirmation thresholds (see specs/native/*.json `proposed_thresholds`) | UNRESOLVED: every native entry is blocked until approved |
| C17 (new) | Native Minervini trend template (published criteria + RS definition) | PROPOSED, not approved |
| C18 (new) | Which exact platform / TradingView script_id+version is the "exact" indicator (Minervini, Weinstein, Turtle) | UNRESOLVED |
