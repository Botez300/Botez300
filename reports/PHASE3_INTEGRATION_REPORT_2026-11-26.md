# Legion Quant Capital - Phase 3 Integration Report (2026-11-26) - PAPER MODE
Draft PR #7, branch `claude/cool-fermi-5sk4s9`. Not merged. No real orders, cancels or exercises are possible: every non-allowlisted
Robinhood tool raises `ToolBlocked` before any network call.

## Bottom line
All six scanners are implemented exactly as written in your Nov 26 instructions, and the configs are version-controlled (`specs/*.json`, format 2, each carrying the
SHA-256 of `specs/source/legion_scanner_instructions_2026-11-26.md`). **None of them can originate a paper entry today.** Five need
data Robinhood does not provide. The sixth (Parabolic) is computable, but its semantics await your approval. In every strategy,
the rules for confirming an entry after mechanical qualification are undefined, and no strategy has been activated.

## Tests (actually executed)
| Suite | Result |
|---|---|
| Phase 1 + Phase 2 (original 106) | 106 passed |
| Phase 3 (new; SYNTHETIC unless named RECORDED) | 95 passed |
| Total, local (Python 3.13) | **201 passed, 0 failed** |
| ruff / schema validation / pip-audit (core + drive deps) | clean / OK / no known vulnerabilities |
| GitHub Actions on latest code commit | **success** on code commit 17e69b6 (run 45863498712: lint, schema, pip check, pip-audit, 201 tests, order-tool guard). This report-only commit is re-verified in the PR checks |

The Phase 3 tests cover:
- three-state AND/OR truth tables and nested groups
- strict vs inclusive boundaries for every threshold
- completed-candle filtering (daily, early close, weekly, monthly)
- Range/SMA offsets
- missing-data UNVERIFIED paths and proprietary-signal absence
- Turtle emergence vs already-active signals
- Weinstein and Parabolic window-mode differences
- the Magic Formula ranking job (ties and coverage)
- the activation gate, runner caps, overlays and the escalation rate limit
- the Drive API adapter against a fake service, and stale/malformed reports

RECORDED tests replay real Robinhood response shapes captured today through the Claude connector.

**Live, authenticated checks this session:**
- Robinhood read-only probes: earnings results, analyst ratings, financials, index bars, scanner preview, Legend catalog.
- One real headless Claude escalation (tools disabled). It answered advisory-only and ignored an injected "place an order" string.
- Drive listing of 03_Verified_Signals through the Claude connector: it still holds only the two TEST_ONLY files.

None of these checks went through the app's own transports.

## What works
1. Deterministic implementations for all six scanners: CAN SLIM (C, A, N, S, L, I, M plus liquidity), Minervini Groups 1-4, Turtle System 1/2 emergence, Weinstein 3-candle window, Magic Formula, and Parabolic 10-candle group with diagnostics (dates, age, extension, ATR, liquidity, risk flags).
2. Magic Formula ranking job: EY rank + ROIC rank, combined ascending, competition ties, coverage report.
3. Separate research and overlay layers: Turtle Donchian research (labeled), Weinstein long-base board (not mandatory), and computable overlays (Wilder RSI14 <= 30, 200-week EMA, 200-month SMA, ATH-anchored VWAP, RS vs SPY, 52-week-high ranking). Unavailable overlays stay UNVERIFIED and are never treated as capital inflow.
4. A v2 activation gate in the trade path. It requires your approval, no pending semantics, no data gaps, defined entry-confirmation rules, a mechanical PASS and the existing entry checks. Turtle-only and Magic-only qualifications never become BUY_NOW.
5. Robinhood adapter extensions (read-only): earnings history, analyst ratings, index lookup and bars, and a scanner universe preview (read-only; saved-scan writes stay blocked).
6. Claude escalation through the supported headless CLI (`claude -p --tools "" --strict-mcp-config --json-schema`). It is wired to missing-report and connection-loss alerts, disabled by default and rate-limited. Answers are advisory only.
7. CI now installs and audits the Drive/MCP dependencies and runs the whole suite.

## Blocked (capability gaps; details in docs/CAPABILITY_GAPS.md)
- **CAN SLIM:**
  - EPS history covers only 7 reported quarters (needs E[0..16]), and the EPS basis is undocumented.
  - RP(yearly) is unavailable.
  - Analyst data is aggregate counts only, with no dated Buy ratings.
  - There is no IWM holdings list (Russell 2000 index membership is not the same thing).
- **Minervini:** the 10-criteria trend-template signal is unavailable, and the ten exact criteria were not supplied.
- **Turtle and Weinstein:** platform indicator readings are unavailable (not in the Legend catalog).
- **Magic Formula:** there is no ROIC field. Operating income is only derivable as operatingMargin x totalRevenue, and that is not approved.
- **Robinhood transport:** not reachable from this sandbox (the proxy returned 403 for agent.robinhood.com). It needs OAuth on your host. Token refresh is not implemented.
- **Google Drive API:** real authentication has not been tested. There are no credentials and none are stored in the repo.
- **Scheduler:** Windows and macOS configs are not installed or tested on a real host.

## Needs your approval
See docs/ASSUMPTIONS_APPROVAL.md:
- A1-A7: your provisional defaults, in use for PAPER testing only.
- B1-B14: build assumptions, including the credit-spread, covered-call and LEAPS delta bands.
- C1-C16: strategy semantics. These block entries until you decide.

Nothing has been approved on your behalf.
