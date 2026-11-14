# LEGION QUANT CAPITAL — Robinhood Leveraged-ETF CSP Engine v1.1 (PAPER)

A Python research and **paper-trading-only** system for systematic cash-secured puts
on 3× leveraged ETFs (TQQQ/SQQQ, UPRO/SPXU, SOXL/SOXS). It uses Robinhood's official
Trading MCP strictly as a **read-only** market-data source and runs two fully
independent simulated portfolios: **A = $5,000** and **B = $10,000**.

> **No live orders exist in this system.** There is no configuration that enables
> them, Robinhood order tools are denied in `.claude/settings.json`, and the engine
> refuses data from any non-allowlisted tool. Nothing here is investment advice.

## Current status (2026-11-14 snapshot)

| | |
|---|---|
| Robinhood MCP | Connected; read access verified (quotes, chains, instruments, Greeks/IV/OI, daily history). No account tools used. |
| Market regime (2026-11-13 close) | **NEUTRAL** for Nasdaq-100, S&P 500 and Semis (QQQ below SMA200 with SMA50 above, 3 SMA200 crossings in 20 days, realized vol ≈2× its 1-year median) |
| Scan result | **NO QUALIFIED TRADE** — 117 verified put quotes screened; both portfolios remain 100% simulated cash |
| Account-size constraint | A can only secure strikes ≤ $20 (no universe ETF currently fits); B ≤ $40 (only SQQQ/SPXU fit). Even with the regime gate waived, the best TQQQ candidates are vetoed for both. |
| Backtest (HYPOTHETICAL) | 2018-01 → 2026-11: A +0.33% CAGR, B +2.00% CAGR; walk-forward OOS 3.6% / 3.1%. The 5%/month target is **not** supported. See `reports/backtest/BACKTEST_REPORT.md`. |
| Tests | `python -m pytest` → 69 passed |

## Install

```bash
python3 -m pip install -e ".[dev]"     # pandas, numpy, PyYAML, pytest (Python 3.12+)
python -m pytest
```

## Commands (`python -m src.cli <command>`)

| Command | Purpose |
|---|---|
| `status [--portfolio A\|B]` | Paper portfolio status |
| `regime [--as-of YYYY-MM-DD] [-v]` | Current market regime per pair |
| `scan [--snapshot DIR]` | Options scan (read-only; nothing persisted) |
| `rank [--snapshot DIR]` | Eligible contract ranking with PASS/CONDITIONAL/VETO per portfolio |
| `order --portfolio B --instrument ID [--contracts 1] [--limit X]` | Create a PAPER order intent (after full risk gate) |
| `fill [--snapshot DIR]` | Try to fill pending PAPER orders from a fresh snapshot |
| `manage [--snapshot DIR]` | Mark, apply management rules, close/expire/assign PAPER positions |
| `run-daily [--snapshot DIR] [--no-submit]` | Full session + daily dashboard (`reports/daily/`) |
| `backtest [--no-walk]` | Historical research suite (`reports/backtest/`) |
| `project` | 15-year compounding scenarios (0/1/2/3/5% monthly) |
| `risk-audit [--as-of]` | Limits, breakers, cash-security and safety checks |
| `report daily\|weekly\|monthly` | Performance reports |
| `reset --portfolio A --confirm "RESET A"` | Archive state+reports, restore original simulated balance |
| `import-history --kind adjusted\|raw FILES` | Import MCP `get_equity_historicals` results |
| `validate-b [--apply]` | Check Portfolio B's two-contract paper-validation gate |
| `safety-check` | Verify the paper boundary and deny-list |

## Daily runbook (Claude Code is the integration layer)

Standalone Python cannot use Claude Code's authenticated MCP session (and unofficial
auth is forbidden), so each session is:

1. In Claude Code, call the read-only Robinhood tools listed in `CLAUDE.md` and save the
   results into `data/snapshots/<date>/` (format documented in `CLAUDE.md`).
2. `python -m src.cli run-daily --snapshot data/snapshots/<date>`
3. Read `reports/daily/LATEST.md`; commit `state/` and `reports/`.

Run it during regular hours if you want simulated fills: the fill model requires a
quote < 15 minutes old during RTH. Weekend or after-hours snapshots only produce
proposals.

**Scheduler:** no scheduler is running. This repository runs in ephemeral cloud
containers, so nothing operates continuously unless you set up a scheduled Claude Code
session or a local cron/launchd job that performs the runbook above. Do not assume
uninterrupted operation.

## Strategy rules (provisional — see `config.yaml`)

- **Regime** (completed candles only; vectorized and causal, shared by live + backtest):
  Bullish = benchmark > SMA200, SMA50 > SMA200, daily & weekly RSI(14) > 50, bull/bear
  relative strength positive or strengthening, bull ETF in its own uptrend. Bearish =
  mirror conditions plus inverse ETF uptrend and inverse daily & weekly RSI > 50.
  Neutral on conflicts, missing/stale data, ≥3 SMA200 crossings in 20 days, or 20-day
  realized vol > 2× its 1-year median. Optional monthly-RSI confirmation is measured in
  the backtest.
- **Screener**: 21–35 DTE puts; |Δ| 0.10–0.20 (broad) / 0.08–0.15 (semis); positive bid;
  Greeks must come from Robinhood (never invented). OI ≥ 500 and spread ≤ 10% of mid are
  *preferences* (failing them → CONDITIONAL); hard floors OI ≥ 50 and spread ≤ 35% are
  research assumptions. Ranking blends trend, liquidity, premium/collateral, delta,
  correlation and IV/RV event risk; it never auto-picks the richest premium.
- **Risk**: collateral = strike × multiplier × contracts incl. pending orders; A max 1
  contract; B 1 contract until paper-validated (then 2 at ≤20% each); ≤40% total
  collateral; ≥60% unencumbered cash; no margin; no opposing bull/bear positions;
  second position vetoed above 0.80 return correlation; unrealized option gains never
  add capacity; breakers at 2% daily / 4% weekly / 8% from equity high.
- **Management**: close at 50% of credit retained, at ≤7 DTE, or on regime loss; flag at
  2× credit (configurable to close); flag early-assignment risk; never auto-roll;
  assignment buys shares at strike, which are liquidated next open (configurable).
- **Fills**: sell = bid + 25% of (mid − bid), capped by Robinhood's
  `high_fill_rate_sell_price`, minus one tick; buy symmetric; $0.03/contract fee
  assumption; unfilled if stale, outside RTH, too wide, or insufficient size.

## Architecture

```
CLAUDE.md, config.yaml, .claude/settings.json (order-tool deny list)
src/safety.py        hard-coded PAPER boundary + MCP tool allowlist
src/broker/          read-only Robinhood MCP snapshot adapter (no network, no orders)
src/data/            typed models, validated history, split detection/repair
src/regime/          indicators + bullish/bearish/neutral classifier
src/options/         Black-Scholes utilities, CSP screener/ranking
src/risk/            collateral, concentration, correlation, drawdown gates
src/portfolio/       simulated balances/positions/orders, atomic JSON state, reset+archive
src/paper/           fill model, PAPER broker, management rules, session orchestrator
src/backtest/        engine, metrics, scenarios, walk-forward, historical-options adapter
src/reports/         daily dashboard, weekly/monthly, compounding projections
tests/               69 pytest tests
data/history/        verified daily bars (adjusted + raw) + data_quality.json
data/snapshots/      Robinhood MCP snapshots
data/raw_mcp/        raw MCP history payloads (provenance)
state/, reports/     paper portfolio state and generated reports
```

## Known limitations / missing capabilities

- **No genuine historical options backtest.** Robinhood MCP gives per-contract historical
  OHLC bars but not historical bid/ask, Greeks or OI, and no other verified chain dataset
  was available. The backtest is HYPOTHETICAL (synthetic Black-Scholes prices on verified
  underlying bars). `src/backtest/chains.py` defines the CSV schema for plugging in a
  vendor dataset.
- Synthetic-premium results are very sensitive to IV and spread assumptions (30% spreads
  turn B's CAGR negative). The one verified snapshot showed much wider spreads at the
  close than the baseline assumption.
- ETF distributions are not modelled; trading halts and intraday early assignment are not
  observable in daily bars. Event risk (FOMC/CPI) has no data source wired in; the
  screener uses an IV/RV proxy only.
- Python cannot fetch data by itself in this environment (outbound hosts are blocked and
  MCP auth lives in Claude Code). Each session needs a Claude Code data capture.
- Historical paper validation for Portfolio B's second contract requires ≥12 closed paper
  trades over ≥3 months; none exist yet.
