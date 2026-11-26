# Legion Quant Capital - Phase 6 Deployment-Readiness Report (2026-11-26) - PAPER MODE

## Summary
- **Software preparation is complete.**
  - The installer no longer registers any scheduled task.
  - Task registration is a separate script that registers the task DISABLED.
  - Even when enabled, the service runs OBSERVE_ONLY (no simulated orders) until nine activation gates pass.
- **Forward paper trading is NOT permitted yet.** It needs your approvals and acceptance tests run on your Windows PC.
- **Your PC is not attached to this session** (no computer folders available), so nothing was installed on it.

## Verified starting state
- Base commit f18ddc5; CI success (run 45872143103).
- 286 passed / 1 skipped, re-run locally.

## Development results
| Item | Result |
|---|---|
| Latest code commit | d9f78c6 |
| Tests | **302 passed, 0 failed, 1 skipped** (LIVE Robinhood). 286 regression tests unchanged + 16 new |
| Lint / bandit / schema / deps | clean / clean / OK / clean |
| CI | **success** on d9f78c6 (run 45873829047: lint, bandit, schema + genuine-report pins, pip-audit, 302 tests + 1 LIVE skipped, order-tool guard) |

## Contraction discrepancy (item 3)
**Three** definitions existed, not two: the spec key name (ATR5/ATR14), the live gate (consolidation TR / ATR14 at the decision bar) and the backtester (consolidation TR / ATR14 at the anchor).
- **Implementation:** all three are now separately named methods in `legion/backtest/contraction.py`. Each module keeps its previous default; nothing was substituted.
- **Numbers, tight 3-candle base:**

| Method | Ratio | Result at 0.80 |
|---|---|---|
| ATR5/ATR14 | 1.49 | FAIL |
| Consolidation TR / ATR14 at anchor | 0.48 | PASS |
| Consolidation TR / ATR14 now | 0.53 | PASS |

- **Numbers, loose 8-candle base:** 1.30, 1.44 and 1.20 respectively.
- **Why ATR5/ATR14 fails:** its 5-bar window still contains the anchor spike, so it rejects almost every consolidation shorter than 5 candles. The decision is yours (P4); I recommend consolidation TR / ATR14 at the anchor.

## Report expiration (item 4)
- **Proposed policy:** `legion/expiry_policy.py`, compatibility-tested and NOT enforced.
  - DAILY reports expire at the next applicable session close. The genuine Thanksgiving report would expire at the Nov 27 13:00 early close.
  - WEEKLY reports run through the final session of the following trading week (Nov 29 -> Dec 4 16:00; Dec 20 -> Dec 24 13:00 early close).
  - Candidate expiration is capped at the report's.
- **The genuine report stays non-actionable under the policy** (DRAFT; and holiday even if VERIFIED). Its bytes are unchanged.
- **A valid window never replaces quote freshness.**

## Requirement status
| Requirement | Status |
|---|---|
| Starting equity (A9) | AWAITING OWNER APPROVAL (service refuses to start while unset) |
| Entry parameters P1-P6 (incl. P4 definition) | AWAITING OWNER APPROVAL |
| Exit configuration P7-P8 | AWAITING OWNER APPROVAL (`exit_rules` empty) |
| B7 liquidity, B22 fill model, B1-B6 options, B15-B18 ROIC, C18 sources, D1 providers, E1 expiry, G1 sign-off | AWAITING OWNER APPROVAL |
| Python/Git/Claude Code on PC | UNVERIFIED (requires you at the PC) |
| Repo checkout, venv, dependencies on PC | UNVERIFIED |
| Google Drive synced directory | UNVERIFIED (real path unknown to me) |
| Secure configuration / credential store | PASS in code (keyring-only, insecure backends refused); UNVERIFIED on PC |
| Robinhood authentication | BLOCKED here (sandbox proxy); UNVERIFIED on PC. Standalone OAuth acceptance by Robinhood unknown |
| Authenticated read-only market-data tests | UNVERIFIED (`acceptance.ps1` step 1) |
| Genuine report: retrieval, hash, schema, duplicate, stale/DRAFT handling | PASS (connector retrieval + recorded tests); host re-run in `acceptance.ps1` step 2 |
| Outbox publication to Drive from host | UNVERIFIED (publisher with readback + restart ledger tested against a fake Drive; needs a host Drive token) |
| Restart recovery (ledger, paper state, outbox ledger, single-instance lock) | PASS (tests) |
| Risk restrictions | PASS (unchanged + halt latch) |
| Emergency shutdown | PASS (drill runs the real service entry point: exit code 3); host drill UNVERIFIED |
| Scheduled task cannot trade before gates | PASS (no auto-registration; registered DISABLED; OBSERVE_ONLY without all gates; tested) |
| Valid research reports (VERIFIED, unexpired, evidence-backed) | BLOCKED: none received yet |
| Sufficient strategy validation | BLOCKED: no point-in-time universe (see Norgate below) |
| Real brokerage order/cancel/exercise tools blocked | PASS |
| PAPER mode | PASS |

## Data providers (item 5)
From vendor pages read today; nothing purchased.
- **Norgate Platinum:** US$630/yr, with delisted securities and historical index constituents back to 1990. This is the largest unblocker, enabling survivorship-free stock backtests.
- **ORATS:** end-of-day options chains with Greeks from 2007. Delayed Data API US$199/mo; Live API US$299/mo. Needed only for historical options claims.
- **Analyst rating history:** not resolved. Bigdata.com licensing is to be evaluated.
- **Proprietary indicators:** must come from the original platform (C18).

## Exact commands on your Windows PC (you must be present)
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
git clone https://github.com/Botez300/Botez300 C:\\Legion\\Botez300
cd C:\\Legion\\Botez300; git checkout claude/cool-fermi-5sk4s9
.\\deploy\\windows\\install.ps1 -Root C:\\Legion            # venv, deps, full tests; registers NOTHING
notepad C:\\Legion\\config.json                            # local_dir (real synced path), state_dir, paper_start_equity
.\\deploy\\windows\\reauth_robinhood.ps1 -Root C:\\Legion   # browser OAuth; STOP and send me the error if registration is refused
.\\deploy\\windows\\acceptance.ps1 -Root C:\\Legion         # Robinhood read-only, Drive genuine report, emergency-stop drill
# only after you have reviewed everything and approved P1-P8 + A9:
.\\deploy\\windows\\register_task.ps1 -Root C:\\Legion      # registered DISABLED
```

## Phase 6 entry criteria
1. A9, P1-P8, B7 and B22 approved and written into `specs/native/PARABOLIC_NATIVE.json` by a reviewed commit.
2. All three `acceptance.ps1` steps PASS on your PC.
3. Drive API token created on the host and outbox publication verified by readback.
4. A genuine VERIFIED, unexpired, evidence-backed report ingested.
5. A walk-forward on a point-in-time universe reviewed by you.
6. You create `OWNER_ACTIVATION_SIGNOFF.json`.
