# Legion Quant Capital - Phase 4 Integration Report (2026-11-26) - PAPER MODE
PR #7, branch `claude/cool-fermi-5sk4s9`, base milestone 3067568 (Phase 3). Unmerged. There is no real order, cancel or exercise path.

## Bottom line
- The pipeline ran end-to-end on the two genuine Drive reports and produced **zero simulated trades**. Both are TEST_ONLY and were correctly rejected.
- The journal and risk report were published to 05_Trade_Journal and 06_Risk_Reports.
- **No strategy, exact or native, can originate a paper entry yet.** The reasons are listed under "Readiness".

## Tests and CI
| Item | Result |
|---|---|
| Original suites (Phase 1-3) | 201 passed, unchanged |
| Phase 4 suite | 48 passed + 1 LIVE test skipped (needs authenticated Robinhood on the host) |
| **Total, local** | **249 passed, 1 skipped, 0 failed** |
| ruff / schema validation / pip-audit (core + drive/mcp/keyring) | clean / OK / no known vulnerabilities |
| GitHub Actions, latest commit | CI_PLACEHOLDER |

Test classes:
- **SYNTHETIC:** hand-built data.
- **RECORDED:** real responses captured today through the Claude Robinhood connector, plus the two genuine Drive files.
- **LIVE:** skipped. **No authenticated app-level connectivity has been demonstrated.** Mocked responses are never counted as authenticated.

## Defects found and fixed this phase
1. The Robinhood MCP transport called `streamablehttp_client(url, headers=...)`, which doesn't exist in MCP SDK 2.3.0. It is rewritten for `streamable_http_client` + `create_mcp_http_client(auth=...)`.
2. The Parabolic consolidation-contraction measure included the qualifying spike candle. It now uses only the consolidation candles.
3. `rh_auth` imported keyring even when a backend was injected. That is fixed, and keyring is added to the host dependencies.

## Built this phase
- **Evidence layer** (`legion/evidence.py`):
  - A source registry splits sources into authorized and proposed. Unauthorized providers raise.
  - Every criterion needs a source, observation time, value, threshold and method. Stale or future evidence, unmapped indicator sources and ChatGPT claims all count as UNVERIFIED.
  - Same-metric conflicts across sources make the criterion UNVERIFIED.
  - Schema v1.1 makes these evidence fields mandatory. v1.0 PASS labels are audited as UNSUPPORTED_LABEL, and the production service rejects them.
- **SEC research** (`legion/research/sec.py`), using Robinhood's SEC tools:
  - Point-in-time GAAP diluted quarterly EPS. The first-filed value wins, restatements are logged, and Q4 slots stay UNVERIFIED because Q4 isn't separately filed.
  - TTM flows, invested capital, and the native ROIC with provenance. Negative invested capital, unusual tax rates, financial institutions and incomplete statements are handled explicitly.
  - Verified against recorded AAPL data: 2.02 vs 1.57 EPS, invested capital of $152.32B.
- **Official ETF holdings parser** (iShares, point-in-time "as of" date required).
- **LEGION_NATIVE variants** (`specs/native/`, `legion/scanners/native.py`), kept separate from the untouched EXACT_PLATFORM scanners:
  - CAN SLIM native (GAAP diluted EPS; M on the stock itself).
  - Parabolic native (same candle, population standard deviation, preceding-20 relative volume, percent ROC).
  - Weinstein native (common anchor in the last 3 weeks; stage readings still have to be imported).
  - Magic native (SEC ROIC/EV).
  - Turtle native: the original Donchian System 1 with the skip-after-winner rule, and System 2, with N and a 2N stop. It does not claim equivalence to the platform tuple.
  - Minervini native: **proposed only**.
- **Entry confirmation rules** for all six, with thresholds marked PROPOSED. The native gate also enforces the approved 0.5% equity spread. Turtle-only and Magic-only hits never become BUY_NOW, and a failed bullish screen never becomes a bearish entry.
- **Robinhood transport:**
  - The official endpoint is confirmed on robinhood.com.
  - OAuth uses the SDK provider (PKCE, refresh), with tokens in the OS keyring only. Insecure backends are refused.
  - Non-interactive mode fails closed. A retry wrapper handles transient failures.
- **Service:** graceful STOP_REQUEST, rotating persistent logs, journal and risk-report generation.
- **Windows** install/start/stop/restart/emergency/reauth/status scripts and **macOS** equivalents. See docs/DEPLOYMENT_WINDOWS.md. **None of it has been run on a real machine.**

## Readiness
| Strategy | EXACT_PLATFORM | LEGION_NATIVE |
|---|---|---|
| CAN SLIM | blocked: RP(yearly), dated analyst Buys, exact M index, spread threshold | mechanics approved; blocked by L and I (no source), Q4 EPS gaps, entry thresholds pending |
| Minervini | blocked: exact 10-criteria signal, platform mapping unknown | proposal only (RS definition + approval needed) |
| Turtle | blocked: platform System 1/2 readings | mechanics implemented and approved; Turtle-only never BUY_NOW; entry thresholds pending |
| Weinstein | blocked: authentic stage readings | blocked: needs imported authentic stage evidence + entry thresholds |
| Magic Formula | blocked: exact ROIC indicator | mechanics computable from SEC; ranking-only never BUY_NOW; entry thresholds pending; B15-B17 pending |
| Parabolic | semantics pending (exact variant kept) | mechanics approved + tested; **blocked only by entry-confirmation thresholds (C16)** |

## Authentication still required (host)
- **Robinhood OAuth login** (`deploy\windows\reauth_robinhood.ps1`). It is unverified whether Robinhood's OAuth server allows dynamic client registration for a non-Claude client.
- **Google Drive:** either Drive for desktop sync (no credentials) or a Drive API token/service account outside the repo.
- **Claude CLI login**, only if you enable escalation.

## Decisions you need to make
1. Approve or adjust the entry-confirmation thresholds in each `specs/native/*.json` (C16). This is the first gate for any paper trade.
2. Resolve B1-B21 (incl. the new ROIC components B15-B17) and C4, C6, C14, C15, C17 and C18.
3. Name the exact platform, or the TradingView script_id+version, behind the Minervini, Weinstein, Turtle and RP indicators.
4. Approve or reject the proposed providers (Alpha Vantage, Bigdata.com, a licensed analyst-actions feed) for CAN SLIM "I".
5. Ask ChatGPT to publish genuine (non-TEST_ONLY) reports in schema v1.1 with full criterion evidence.
6. Run the Windows install and acceptance checklist on the real machine.
