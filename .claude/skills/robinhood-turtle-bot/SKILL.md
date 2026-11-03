---
name: robinhood-turtle-bot
description: Run the Robinhood Agentic Trading bot — Turtle System 1 on US stocks/ETFs filtered by completed daily RSI(14) >= 50. Use whenever the user asks to run the bot, scan for trades, check Turtle signals, manage/exit Turtle positions, or size a buy in the agentic Robinhood account. This is the only active strategy; older scans (Minervini VCP, LW Volatility Breakout, Agent Momentum Pullback, etc.) are not part of the bot.
---

# Robinhood Turtle System 1 bot (RSI ≥ 50)

Mode: **research and approval only**. Never place an order without the user's explicit "yes" for that specific order in this conversation.

Tools:
- Robinhood data/orders: `mcp__Robinhood_Agentic_Trading__*`
- Strategy math: `robinhood-turtle-bot` MCP server (`turtle_strategy_config`, `turtle_evaluate_entry`, `turtle_evaluate_position`, `turtle_size_buy`). If that server is not loaded, run the same functions from `robinhood_turtle_bot/signals.py` and `risk_gate.py` with `python3 -I`.

## Each run

1. **Account.** `get_accounts` → use the one agentic account. `get_trade_approval_setting` for it. Confirm the market is open (`get_index_quotes`/quote timestamps) before proposing entries.
2. **Snapshot (all of it, not just bot trades).** `get_portfolio` (total_value = NAV, `cash` = cash; never use buying power), `get_equity_positions`, `get_equity_quotes` for every holding, and `get_equity_orders` with state filters for open orders (`new`, `queued`, `confirmed`, `unconfirmed`, `partially_filled`). Every holding and every open buy order occupies one of the 5 symbol slots.
3. **Exits first** (always allowed, even when entry gates fail). For each Turtle position, rebuild `unit_fill_prices` from the filled agent buy orders (`get_equity_orders agent_initiated=true symbol=…`) and `entry_N` from the bars ending the day before the first fill. Call `turtle_evaluate_position`. On `EXIT_ALL_*`, propose a sell of `shares_available_for_sells`. Holdings that are not Turtle positions (no recorded entry) are left alone — never sell them to free cash or slots.
4. **Candidates.** `run_scan` with scan id `2a70f2b7-0326-4eab-b5c0-3720757abbb6` ("Turtle System 1 — Stocks ETFs RSI14 >= 50"). A scan hit is NOT a signal. Confirm stock/ETF type and `get_equity_tradability`.
5. **Signal.** For each candidate: `get_equity_historicals` (interval `day`, bounds `regular`, start ≈ 1 year ago, ≤10 symbols per call) and the live last price. Call `turtle_evaluate_entry` with `last_bar_complete=false` during the session (today's bar is forming and is dropped). Act only on `ENTER_20` or `ENTER_55_FAILSAFE`. After the close, today's daily bar may still come back `interpolated: true` (a placeholder); rebuild it from `interval: hour` bars for the session, then use `last_bar_complete=true` and place next-day buy stop-limit orders at the trigger (limit = trigger + 0.5N, so a gap above it does not fill). `run_scan` returns at most 200 rows (largest market cap first).
6. **Size.** `turtle_size_buy` with the full snapshot. For each existing Turtle position pass `risk_at_stop = shares × max(0, price − stop_all_units)`; for non-Turtle holdings pass `risk_at_stop = 0` and their market value. For each open buy order pass remaining cost. `permitted_shares = 0` → no trade, report the reason.
7. **Pyramids.** `ADD_UNIT_SUBJECT_TO_RISK_GATE` → size again with `turtle_size_buy`; the gates usually allow fewer than 4 units.
8. **Propose → review → approve → place.** Show symbol, signal, shares, expected cost, stop, cash left vs the $500 reserve, slots used. Call `review_equity_order`. Only after explicit approval, `place_equity_order` (whole shares, limit near the ask, no margin). After fill, recompute stop/adds from the actual fill price.

## Hard rules

- Long only, stocks/ETFs only. No shorting, no margin borrowing, no options.
- RSI(14) uses the last **completed** daily bar for both 20- and 55-day entries.
- Skip a 20-day breakout if the last theoretical 20-day breakout was a winner (or is still open); the 55-day failsafe ignores that filter.
- Stop = 2N below the latest unit's fill (all units). Exit on a break of the prior 10 completed sessions' low. Exits ignore RSI.
- Max 5 distinct symbols (holdings + open buys). At least $500 in real cash after every buy, including open-order reservations (sizing never spends it). Each buy gets an even share of deployable cash across free slots (19% / 0.5% per-symbol caps are off), so once all 5 are filled about $500 is left. Size with `expected_fill_price` = the order's limit price, cheapest-per-share names first so leftovers flow to the rest.
- If the account already breaks a limit, block new buys; do not liquidate to fix it.
- Do not create schedulers or auto-trading loops unless the user explicitly asks.
