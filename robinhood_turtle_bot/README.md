# Robinhood Agentic Trading Bot — Turtle System 1 (RSI ≥ 50)

The only active strategy for the Robinhood agentic account. Long-only Turtle
System 1 on US stocks/ETFs, filtered by completed daily RSI(14) ≥ 50.

## Pieces

| File | What it does |
|---|---|
| `strategy_config.json` | All rule parameters and the Robinhood saved scanner id |
| `signals.py` | Turtle math: RSI(14), N, 20/55-day breakouts, skip-after-winner ledger, 10-day exit, 2N stop, 0.5N pyramids |
| `risk_gate.py` | Fail-closed buy sizing: 5 symbols, $500 cash reserve, 19% per symbol, 0.5% NAV stop risk |
| `mcp_server.py` | Local stdio MCP server exposing the above as tools (no extra packages) |
| `../.claude/skills/robinhood-turtle-bot/SKILL.md` | Step-by-step runbook Claude follows using the Robinhood MCP tools |

The local MCP server never talks to Robinhood. Claude pulls data with the
Robinhood Agentic Trading MCP, passes it to these tools, and every order goes
through `review_equity_order` and your explicit approval.

## MCP tools

- `turtle_strategy_config` — current rules
- `turtle_evaluate_entry` — signal for one candidate (`ENTER_20`, `ENTER_55_FAILSAFE`, `NONE`)
- `turtle_evaluate_position` — exit / add check for an open position
- `turtle_size_buy` — max whole shares allowed by the account gates

Registered in the repo's `.mcp.json` as `robinhood-turtle-bot`.

## Trading rules

- Long-only, stocks/ETFs. Check asset type and tradability.
- RSI(14) from the last completed daily bar must be ≥ 50 (never the forming bar).
- Entry: break above the prior 20 completed sessions' high, skipped if the last
  theoretical 20-day breakout was a winner (or is still open). The 55-day breakout
  failsafe ignores that filter. Same RSI filter on both.
- Exit: break below the prior 10 completed sessions' low, or the 2N stop below the
  latest unit. Exits ignore RSI.
- Pyramid every 0.5N, max 4 units, every add re-checked against the gates.
- No shorting, no margin, no liquidating to rebuild cash.

## Account limits

- Max 5 distinct symbols with holdings or open buy orders (all holdings count).
- At least $500 of actual cash left after any purchase, including open buy reservations (`min_post_trade_cash_usd` in the config). Buying power does not count.
- ≤ 19% market value and ≤ 0.5% stop risk per symbol, both measured on NAV minus the $500 reserve.
- If the account already breaks a limit, new buys are blocked; nothing is sold automatically.
- Stops and gaps can lose more than the sizing assumes.

## Tests

```
python3 -m unittest discover -s robinhood_turtle_bot/tests -t .
```
