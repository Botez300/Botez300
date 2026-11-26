# Legion scheduled scanner instructions (owner-supplied, 2026-11-26, Phase 3 message) - canonical source text

GLOBAL: completed candles; split-consistent OHLCV; timestamped point-in-time fundamentals; never invent proprietary readings;
never substitute approximate indicators for exact platform signals; PASS/FAIL/UNVERIFIED; AND passes only when all mandatory
conditions pass; OR passes when at least one condition is verified true; unknown mandatory data blocks affected entries; separate
mechanical qualification from trade-entry confirmation; PAPER mode.

1 CUSTOM CAN SLIM. Universe: current complete IWM holdings. Liquidity: price >= $5; median 20-day daily dollar volume >= $5M; no clearly
untradeable spreads. E[k] = reported quarterly EPS k quarters ago. G(k): E[k] at least 25% above E[k+4]. Consistent GAAP or adjusted EPS;
nonpositive/undefined bases cannot automatically pass. C: G(0). A: (G1|G2|G3|G4) & (G5|G6|G7|G8) & (G9|G10|G11|G12); history through E[16].
N: daily close within inclusive +/-15% of W Range(52,1) High. S: monthly volume SMA20 offset1 > offset2 | > offset3 | > offset4 (completed
monthly bars). L: RP(yearly) for SPX500 strictly > 80 (exact provider metric or documented equivalent). I: >= 1 verified analyst Buy rating
within preceding 90 days. M: daily close > daily SMA200 AND SMA200 now > SMA200 90 sessions earlier (>= 290 completed daily bars).
All seven letters. Up to 20 candidates.

2 MINERVINI VCP/SEPA. Universe: broad US-listed common equities + liquidity gate. G1: "D Mark Minervini Trend Template Candles (yes), Meets
All 10 Trend Template Criteria Signal active" AND market cap > $2B. G2: D Range(100,1) High == same 10 daily candles earlier; daily close within
inclusive +/-7% of D Range(100,1) High; weekly close within inclusive +/-20% of W Range(100,0) High; daily close <= D Range(100,1) High.
G3: D Range(10,0) Low > same 10 candles ago; D Range(20,0) Low > same 20 ago; D Range(30,0) Low > same 30 ago. G4: ANY daily volume SMA20
offset1 < SMA20 at offset 30|25|20|15|10|5. All four groups. Not a confirmed breakout.

3 TURTLE. ANY: "D Turtle Trading Strategy (Long-Only) (yes, yes, yes, yes, 2), System 1 Entry Signal emerged" | "... System 2 Entry Signal
emerged" - new emergence on latest completed daily candle. Donchian 20/55 may exist as separately labeled research. RSI>50 diagnostic only.
Existing universe/liquidity floors. Up to 10. Turtle-only never automatically BUY_NOW.

4 WEINSTEIN STAGE 2. Completed weekly candles; ALL within a three-candle group window: "W Weinstein Stage Analysis (30,5,sma), Stage 2 Signal
emerged"; Stage 1 active 1, 2 and 3 candles ago; W Relative Volume (20,SMA,1) > 1. Up to 10. Separate long-base (>= 52 week) board, not mandatory.

5 MAGIC FORMULA. Broad US common equities. ALL: operating income / EV > 0.10; market cap > $10M; daily 20-period share-volume SMA > 300,000;
TTM ROIC >= 0.15; positive EV; TTM operating income default; documented ROIC definition (not ROE, not Greenblatt RoC). Universe ranking:
EY desc rank + ROIC desc rank, combined ascending. No $5 / $5M floor as mechanical gate. Up to 10. Not BUY_NOW.

6 PARABOLIC MOMENTUM. Broad US common equities. ALL within ten daily candles: close > Bollinger(20,2,2,0,close) Up; Relative Volume
(20,SMA,1) > 2; ROC(5,close) > 40; close > 5. Strict. Verify ROC scale, Bollinger stdev convention, relvol baseline/offset, common-anchor
vs different-candle semantics. Report dates, age, extension, ATR, liquidity, risk flags. Up to 10. No extra mechanical gates.
