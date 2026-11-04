# Flush Reversal: Robinhood MCP Strategy

Based on the TTI "Flush Reversal: Internals Cheat Sheet" (@capitalflows).
Idea: buy calls on SPY (or QQQ) right after a 1-minute washout, **only when
breadth, volume and VIX agree the selling is done**.

Account: the agent-enabled Robinhood account nicknamed **MCP** (••3179, limited
margin, options level 3). It is the only account the agent can trade.

---

## 1. What Robinhood MCP can and can't see

| Cheat-sheet input | Robinhood MCP | What we use |
|---|---|---|
| SPY / QQQ 1-min bars | ✅ `get_equity_historicals` (interval `minute`) | Direct |
| VIX | ✅ `get_index_historicals` (id `3b912aa2-88f9-4682-8ae3-e39520bdf4db`) | Direct |
| NYSE TICK | ❌ not offered | **Basket TICK proxy** |
| NYSE ADD | ❌ not offered | **Basket ADD proxy** |
| NYSE TRIN | ❌ not offered | **Basket TRIN proxy** |
| VWAP | computed from SPY bars | Direct |
| Options chain, quotes, orders | ✅ `get_option_chains`, `get_option_quotes`, `review_option_order`, `place_option_order` | Direct |
| Econ calendar (Rule 6) | ❌ in Robinhood | TradingView MCP `mcp-tv-get-economic-calendar`, or enter manually |

### Breadth basket (19 names + the underlying = 2 calls of 10)

**SPY version:** AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA BRK.B JPM LLY V XOM UNH MA COST WMT HD PG
**QQQ version:** AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA COST NFLX AMD PEP ADBE CSCO TMUS INTU QCOM AMAT TXN

### How the proxies work (`signals.py`)

- **TICK proxy** = (names up on the minute − names down) ÷ N × 1000. Range ±1000.
- **ADD proxy** = average of each name's % change vs. prior close, scaled so −1% = full decliner. Range ±1000. Smooth enough to "turn up".
- **TRIN proxy** = (up names ÷ down names) ÷ (up volume ÷ down volume), rolling 5 minutes.

Mega-caps move together more than the whole NYSE, so the proxies hit extremes
more easily. Thresholds are set tighter than the card and **must be calibrated**
(see §6).

| Rule | Card | This strategy (proxy) |
|---|---|---|
| Setup TICK | ≤ −900 | ≤ **−700** |
| A+ TRIN | ≥ 1.5 | ≥ **1.5** |
| Exit TICK | ≥ +800 | ≥ **+800** |

---

## 2. The rules, mapped to Robinhood MCP

**1. SETUP.** SPY prints a new intraday low on a 1-min bar **and** the TICK proxy is ≤ −700.
A+ if the TRIN proxy is ≥ 1.5 on that bar. If the next bars keep making lower lows, the setup rolls down to the newest flush bar.

**2. CONFIRM (within 3 bars).** All three:
- VIX stops making new highs and closes below its peak.
- ADD proxy rises off its low since the setup.
- TRIN proxy < 1, or lower than it was on the flush bar.

**3. ENTRY.** A 1-min bar **closes above the flush-bar high** within 10 bars of the setup.
- Contract: SPY calls, **next-day expiry** (like the card's 10/9 contract bought on 10/8), ATM or 1 strike OTM.
- Order: limit at the mid from `get_option_quotes` → `review_option_order` → `place_option_order`.
- Not filled within 2 bars → `cancel_option_order`. Don't chase.

**4. STOP (set before entry, no exceptions).** Exit everything if either happens:
- SPY trades below the flush low.
- VIX makes a new high above the setup peak.
- Backup hard stop: option down **35%** from fill.

**5. EXIT.**
- Take a partial at **VWAP** or when TICK proxy ≥ +800. With 1 contract, sell it all there.
- 5+ bars after entry, if TRIN proxy > 1 while price rises, tighten the stop to that bar's low.
- Flat by 15:45 ET unless deliberately holding the next-day contract overnight (see PDT note).

**6. NO TRADE.**
- ADD proxy still making new lows.
- First 5 minutes of the open (before 9:35 ET), and after 15:45 ET.
- Within 15 min of a scheduled release (10:00 data, 14:00 FOMC, etc.).
- After a confirmed setup fails with a new low, no re-entry until steps 1–3 reset.
- Max **1 trade per day**.

---

## 3. Sizing for this account

Snapshot when written (Nov 4, 2026): account value ≈ **$9,724**, buying power ≈ **$613**.

| Limit | Value |
|---|---|
| Max premium per trade | lower of **3% of account (~$290)** and buying power |
| Max loss per trade | **~1% of account (~$100)**: the 35% option stop on a ~$2.90 contract |
| Contracts | usually **1** SPY call (2 only if premium ≤ $1.45) |
| Daily stop | 1 losing trade → done for the day |
| Weekly stop | 2 losing trades → paper only until next week |

**PDT warning:** this is a limited-margin account under $25k, so it's limited
to **3 day trades per rolling 5 business days**. A same-day buy and sell of a
call counts. The next-day expiry lets you hold overnight instead of using a day
trade, but that carries gap risk. Plan for ~3 trades a week at most.

---

## 4. Agent playbook (exact tool calls)

**Pre-market (9:00 ET)**
1. `get_portfolio(<MCP account_number>)`: refresh buying power, apply §3 sizing.
2. `get_trade_approval_setting(<MCP account_number>)`: trades currently run **without** your manual approval. For the first live trades, consider turning approvals on in the Robinhood app.
3. `get_equity_historicals(symbols=basket, interval="day", start_time=<5 days ago>)` → save to `cache/<date>/00_daily_*.json` (prior closes).
4. Get today's release times (TradingView MCP economic calendar) → `--blackout 10:00,14:00`.
5. `get_option_chains("SPY")`: note the next-day expiry.

**Every minute, 9:35–15:45 ET**
1. `get_equity_historicals(["SPY", +9 basket], interval="minute", start_time=<last 5 min>)`
2. `get_equity_historicals([10 remaining basket], interval="minute", start_time=<last 5 min>)`
3. `get_index_historicals([VIX id], interval="minute", start_time=<last 5 min>)`
4. Save each raw response to `cache/<date>/<HHMM>_<n>.json` (the engine merges and de-dupes).
5. `python strategies/flush_reversal/signals.py cache/<date> --blackout 10:00,14:00`
6. Act on the latest event:
   - `2 CONFIRM` → pre-pick the strike: `get_option_instruments` + `get_option_quotes`.
   - `3 ENTRY` → limit buy at mid. Also `create_alert` on SPY at the flush low as a phone backup for the stop.
   - `4 STOP` / `5 EXIT` → limit sell at mid; if not filled in 1 bar, sell at the bid.

**After the close**
- Log the trade (internals at setup, fill, exit, P&L) for calibration.

---

## 5. Modes

| Mode | What the agent does | When |
|---|---|---|
| **ALERT** (default) | Runs the engine, reports signals, places no orders | First 2 weeks / first 10 signals |
| **PAPER** | Logs the trades it *would* place with live option mids | Until win rate and average R look acceptable |
| **LIVE** | Places orders per §2–§4 | Only when you say so, ideally with approvals on |

---

## 6. Calibration before going live

The proxy thresholds are guesses until replayed on real data. For 10–20 past
sessions (start with Oct 8, 2026, the card's example, using the QQQ basket):
1. Pull the day's minute bars for the underlying, basket and VIX, plus prior-day closes, into `cache/<date>/`.
2. Run `signals.py` and compare its setups with the obvious flush lows on the chart.
3. Adjust `TICK_SETUP`, `TICK_EXIT` and `ADD_FULL_PCT` at the top of `signals.py`.

Test on synthetic data: `cd strategies/flush_reversal && python3 -m unittest test_signals`

---

*Not financial advice. 1-minute options trading is high risk, and proxy
internals are an approximation of NYSE TICK, ADD and TRIN, not a copy.*
