# Legion Quant Capital - Phase 5 Completion Report (2026-11-26) - PAPER MODE

## Executive summary
- The genuine ChatGPT report `DAILY_2026-11-26_123541` was retrieved, verified and correctly blocked:
  - SHA-256 matches; the bytes validate against the pinned v1.1 schema (blob 6f3dbea7) with 0 errors.
  - Ingestion is rejected for DRAFT and EXPIRED. The report expired at the instant of publication (`valid_until == generated_at`).
  - Re-ingestion is rejected as a duplicate. Both attempts are recorded in SQLite.
  - Zero orders.
- **Every reported INSM value was reproduced independently** from Robinhood OHLCV, with differences of at most 4e-5. INSM is **not actionable**: the report is DRAFT, and the only anchor is the latest candle, with no consolidation.
- The data also shows a **pinned-price event-risk pattern** (0.24-0.31% daily range on 17.7x volume). It is consistent with a pending corporate event, but unverified.
- Backtesting, entry and exit research, a risk halt latch, the operating calendar and the deployment fixes are implemented and tested.
- **No strategy is activated.** Forward paper trading is ready to switch on for PARABOLIC_NATIVE once you approve P1-P8 plus the starting equity, and an authenticated Robinhood test passes on your PC.

## Development results
| Item | Result |
|---|---|
| Base | 858e491 verified: HEAD matched, schema blob 6f3dbea7, 249 passed / 1 skipped re-run locally |
| Latest code commit | 4996327 |
| Tests | **286 passed, 0 failed, 1 skipped** (LIVE Robinhood; needs host auth). 249 regression tests unchanged + 37 new |
| Lint / security / deps / schema | ruff clean; bandit (medium+) clean after marking the Drive-md5 comparison non-security; pip-audit core + host deps clean; schema validation OK |
| CI | **success** on 4996327 (run 45872005747: lint, bandit, schema, genuine-report hash + schema-blob pins, pip check, pip-audit, 286 tests + 1 LIVE skipped, order-tool guard) |

## Defects found and fixed this phase
1. **Backtester skipped exits on the final bar.** This was an optimistic bias; fixed and covered by a test.
2. **Entry bar double-processed in the backtester.** Fixed.
3. **`install.ps1` path substitution** corrupted the repo path when the install root was not `C:\Legion`. Fixed with explicit placeholders.
4. **Documented install used `-ExecutionPolicy Bypass`.** Replaced with the per-user `RemoteSigned` policy; a test forbids bypass flags.
5. **Bandit high finding:** MD5 used for the Drive checksum comparison, now marked as non-security.

## Acceptance checks
| # | Check | Status |
|---|---|---|
| 1 | Regression tests preserved | PASS (249 unchanged) |
| 2 | New tests executed | PASS (37) |
| 3 | Latest CI verified | PASS (4996327) |
| 4 | Canonical schema v1.1 enforced (pinned blob) | PASS |
| 5 | Genuine report retrieved (raw bytes, Drive connector) | PASS |
| 6 | Integrity (SHA-256 443e77ac...) | PASS |
| 7 | Independent validation: ID, timestamps, NYSE holiday session, last-close data time, expiry, status, safety flags, provenance | PASS (4 third-party web sources are not authorized: their claims stay UNVERIFIED) |
| 8 | INSM reproduced | PASS (RSI warmup sensitivity: 82.9707 at 61 bars vs 82.9360 at 227 bars) |
| 9 | DRAFT blocked | PASS (also EXPIRED) |
| 10 | Zero unauthorized orders | PASS (0 orders; all order, cancel and exercise tools blocked) |
| 11 | Entry parameters documented | AWAITING OWNER APPROVAL (P1-P6) |
| 12 | Exit parameters documented | AWAITING OWNER APPROVAL (P7-P8; `exit_rules` stays empty) |
| 13 | Assumptions consolidated | PASS (`docs/OWNER_APPROVALS.md`) |
| 14 | Data coverage assessed | PASS (`docs/DATA_PROVIDERS.md`) |
| 15 | Backtesting infrastructure validated | PASS (synthetic integrity tests); multi-year runs **BLOCKED** (no point-in-time universe on the host yet) |
| 16 | Local deployment documented | PASS (docs); install **UNVERIFIED** on your PC |
| 17 | Authentication blockers identified | PASS |
| 18 | Risk restrictions preserved (+ halt latch) | PASS |
| 19 | PAPER mode preserved | PASS |
| 20 | Report published + readback | PASS: uploaded to 07_Performance, then downloaded and its SHA-256 compared with the committed file |

## Integration results
- **Google Drive:** connector retrieval of raw bytes **PASS**. App-level Drive API auth is UNVERIFIED (fake-service tests only). Desktop sync is UNVERIFIED (your PC).
- **Robinhood:** read-only market data through the Claude connector is **PASS** (INSM, SPY, SEC, options). The app's own OAuth is **UNVERIFIED**: the sandbox proxy blocks the host, and it's not confirmed that Robinhood accepts standalone client registration.
- **Credentials:** OS-keyring-only storage; insecure backends are refused (tested with injected backends).
- **Scheduler:** phases, holiday and early-close handling, missing-report alerts, auth alerts, single-instance lock and post-close outbox are **PASS** (synthetic clock). Task Scheduler and launchd are not installed (UNVERIFIED).
- **Claude routing:** Opus for risk/semantics, Sonnet for blockers/data failures, Haiku for triage. Model availability is checked at call time, and an unavailable model is reported as MODEL_UNAVAILABLE_OR_FAILED.

## Strategy readiness
| Strategy | Mechanical | Data | Entry | Exit | Backtest | Paper eligible | Blockers |
|---|---|---|---|---|---|---|---|
| CAN SLIM exact | done | GAP (RP, dated ratings, IWM holdings) | undefined | none | blocked | no | C18, D1, data |
| CAN SLIM native | done | GAP (L, I; Q4 EPS) | proposed | none | blocked | no | data |
| Minervini exact | done | GAP (exact template) | proposed | none | blocked | no | C18 |
| Minervini native | proposal | partial (RS) | proposed | none | blocked | no | C17, B8 |
| Turtle exact | done | GAP (platform signal) | - | - | blocked | no | C18 |
| Turtle native | done | OK (OHLCV) | proposed | stop 2N, channel exits | blocked | never alone | Turtle-only rule |
| Weinstein exact / native | done | GAP (stage readings) | proposed | none | blocked | no | C18 |
| Magic exact | done | GAP (exact ROIC) | - | - | blocked | no | C18 |
| Magic native | done | OK (SEC) | proposed | none | blocked | never alone | B15-B18 |
| **Parabolic native** | **done; INSM reproduced** | **OK (OHLCV)** | **AWAITING APPROVAL (P1-P6)** | **AWAITING APPROVAL (P7-P8)** | framework ready; real multi-year run blocked | after approvals + host auth | P1-P8, A9, host auth |
| Parabolic exact | done | semantics pending | - | - | blocked | no | platform semantics |

## Your decisions
See `docs/OWNER_APPROVALS.md`. In priority order:
1. **A9: starting paper equity.**
2. **P1-P8: Parabolic entry, extension and exit configuration.**
3. B7, B22 (liquidity and fill model).
4. B1-B6 (options).
5. B15-B18 (ROIC).
6. C18 (exact indicator sources).
7. D1 (data provider for analyst ratings).

## Windows next steps
Follow `docs/DEPLOYMENT_WINDOWS.md` steps 1-13, then send me the output of step 12 (login) and step 13 (LIVE test).

## Phase 6 prerequisites
1. Host install passes its tests.
2. Robinhood authenticated read-only test passes (or Robinhood confirms the supported path).
3. A9 + P1-P8 approved.
4. Point-in-time universe source chosen, so a real walk-forward can run.
5. A genuine VERIFIED report arrives and passes.
6. Daily outbox publication to Drive is wired to an authenticated Drive credential.
