# Legion Quant Capital - Phase 2 Integration Report (2026-11-26) - PAPER MODE
Branch `claude/cool-fermi-5sk4s9`, draft PR #7 (not merged). No live trading, no real orders, no credentials in the repo.

## Test results (actually executed, local sandbox, Python 3.13)
| Suite | Result |
|---|---|
| tests/test_ingestion.py (Phase 1, unchanged) | 20 passed |
| tests/test_phase2.py (new) | 86 passed |
| **Total** | **106 passed, 0 failed** |
| ruff | clean |
| scripts/validate_schema.py | OK (schema valid; both TEST_ONLY files schema-valid and NOT tradeable) |
| pip-audit -r requirements.txt | no known vulnerabilities |
| GitHub Actions workflow | written; **not yet observed running** (see PR checks) |

**Synthetic vs real.** All order-path, risk, options-selection, scheduler and strategy tests use SYNTHETIC fixtures and a synthetic clock
(Tue 2026-12-01 11:00 ET). Robinhood *response shapes* were RECORDED from live read-only MCP calls on 2026-11-26 (a market holiday; SPY only,
previous-session data) and replayed in tests. **No live-market entry verification has been performed**, because the market was closed and the
Python process has no Robinhood transport.

## What each defect-finding test caught during development
- Naked-option guard had the wrong cover rule (would have rejected valid verticals) - fixed.
- A missing strategy spec file crashed the pipeline instead of blocking the entry - fixed; per-candidate errors now fail closed.
- Test fixtures exposed a too-wide spread being (correctly) rejected - fixture corrected, rule unchanged.

## Working (verified by tests unless noted)
- Canonical schema `schemas/legion_signal_v1.schema.json` (19 report fields, 23 candidate fields, enums as specified); structural validity separate from eligibility.
- Eligibility gate: test_only, status, expiry, mandatory fields, duplicates (id + hash + in-report signal_id), prompt-injection heuristics, partial-sync deferral, BUY_NOW + VERIFIED + all-PASS candidates only.
- Robinhood adapter (read-only allowlist; all order/cancel/exercise/watchlist/alert tools blocked before any transport call); parsers for quotes, OHLCV, fundamentals, indicators, chains, instruments, option quotes+Greeks, earnings calendar.
- Session-aware freshness (NYSE calendar 2026 holidays, early closes, America/New_York); holiday/previous-session quotes never actionable.
- Deterministic risk engine with all requested limits; broker re-checks every order independently.
- Options engine: long call/put, bull-call/bear-put/bull-put/bear-call spreads, CSP (full assignment downside counted), covered call, LEAPS; defined-risk only; no 0DTE; spreads submitted atomically.
- Paper broker, position monitor (stop/target/strategy exits from COMPLETE specs; option expiration guard), restart-safe state, duplicate-signal prevention.
- Service: 60 s poll, exponential backoff, missing-daily-report alert, connection alerts, heartbeat, emergency stop (file/SIGTERM).
- Windows Task XML and launchd plist parse (syntax only).

## Remaining placeholders / not working
1. **Strategy specs: all six strategies INCOMPLETE.** The original Legion scanner specs were not provided; no criteria were invented, so every stock entry is blocked. Provide the specs (docs/STRATEGY_SPECS.md).
2. Even with specs: CAN SLIM EPS growth cannot be verified from Robinhood fundamentals; Magic Formula needs a ranking job; VCP contraction pattern not verified.
3. **Robinhood transport (`McpHttpTransport`) is untested** and its endpoint/auth are unknown to me. Without it, all entries fail closed.
4. **`DriveApiSource` never run against Google** (no credentials). `LocalDirSource` is tested on a plain folder, not a real Drive-for-desktop mount.
5. Scheduler configs not installed or run on Windows/macOS. Service is NOT claimed operational. Alerts are local files only (nothing pushed to 09_Alerts).
6. Claude escalation is a request-file queue only; nothing invokes Claude automatically.
7. Bearish options: no bearish strategy spec exists, so the live path never marks a setup bearish-verified (selection logic itself is tested with a synthetic flag).
8. Independent earnings check: the non-empty response shape of `get_earnings_calendar` was never observed; unparsable => treated as unknown => blocks.
9. Legacy Phase 1 modules (`validator.py`, `pipeline.py`, `engines.py`, `orders.py`) are retained only to keep the original 20 tests; the runtime does not use them.

## ASSUMPTIONS to confirm (not specified by owner)
Quote max age 60 s; live-vs-report price drift <= 1%; min avg volume 500k shares and $10M/day; earnings blackout 7 days (options: any earnings before expiry); RS = excess return vs SPY over 63 days;
credit-spread short-leg delta 0.15-0.30; covered call 30-45 DTE / delta 0.15-0.30; LEAPS delta 0.60-0.80; option strikes fetched within +/-30% of spot;
reports claiming `execution_authorized: true` are schema-invalid; candidates with any `missing_data` are ineligible; paper start equity $100,000; option expiration guard closes at DTE <= 1;
daily-report deadline 09:15 ET; only an unbroken CSP downside-to-zero counts toward the 0.5% options risk (so CSPs on typical accounts size to zero).

## Authentication requirements
Google (service account Viewer share OR OAuth read-only token), Robinhood MCP endpoint + token. All outside the repo.

## Unresolved blockers
Original strategy specs; Robinhood MCP transport details; a real host to install/test the scheduler; a first genuine VERIFIED report to exercise live verification during market hours.
