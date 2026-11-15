# Project status

_Last verified: 2026-11-15._

## Where things stand
Milestones 0 and 1 are implemented. The terminal runs end-to-end in **demo mode** (synthetic data, labelled
`SIMULATED`). Next task: Milestone 2, item 1 in `docs/ROADMAP.md` (relative strength + cross-symbol indicators),
after the carry-over checks listed there.

## Implemented and verified
| Area | What works | Verified by |
| --- | --- | --- |
| API | FastAPI: register/login/logout/me, provider info, symbol search, bars, indicator catalog + compute, watchlists CRUD, scan run/presets/saved | 31 API tests |
| Tenancy & security | Workspace per account, roles, org-scoped queries, Argon2id, JWT cookie, login throttling, audit log, prod config guards | tests listed in `docs/SECURITY.md` |
| Database | PostgreSQL 16 schema via Alembic; SQLite for fast tests | migration drift test |
| Indicators | 25 indicators in one registry | 121 tests (80 golden vs TA-Lib, 41 property) incl. a lookahead check on every indicator |
| Data layer | Provider contract, demo provider, Alpaca + Polygon adapters, NYSE calendar, resampling, quality checks, verification states | 15 data tests |
| Scanner | JSON rule schema, AND/OR groups, offsets, multipliers, crosses, daily/weekly/monthly, ranking, 6 templates, completed-bars-only | 17 scanner tests |
| Web | Sign-in, Command Center, Vela chart with API-computed indicators, scanner builder with export/save, watchlists | 6 Playwright flows |

Test totals on this commit: **184 passed, 1 skipped** on SQLite; **185 passed** on PostgreSQL; **6/6** e2e;
ruff, mypy and tsc clean; `npm audit --omit=dev` 0 vulnerabilities.

## Simulated vs live
- **Everything shown today is simulated.** Demo tickers are fictional; prices come from a seeded factor model.
- The Alpaca and Polygon/Massive adapters are **implemented but have never been run against the live services**
  (no credentials; vendor hosts blocked in the build environment).

## Not verified / known limitations
- The Docker stack has only been run in CI (GitHub Actions run 43672933104 on commit ceeef4a: `python`, `web` and
  `e2e` jobs green; `e2e` builds `docker compose` and runs the 6 browser flows against it). It has not been run on a
  developer machine; the build sandbox has no Docker daemon.
- Daily bars only (weekly/monthly derived). No intraday, fundamentals, options, corporate-action events or index constituents.
- Bars are cached in API process memory (5 min TTL); no shared bar store or ingestion worker yet.
- Vela draws the newest bar as a forming candle; on end-of-day data that bar is in fact complete.
- Chart preferences are stored in the browser; drawings are not persisted.
- The scan builder edits a single AND/OR level (the API accepts nested groups).
- Security gaps before any public exposure: see "Known gaps" in `docs/SECURITY.md` (no email verification, password
  reset, MFA, session revocation, general rate limiting, CSP, backups or monitoring).
- No billing, alerts, backtesting, AI agents, paper trading, pattern recognition or specialized scanners yet.

## Measured (not targets)
Single API process, 4 vCPU sandbox, demo provider, 2,735 daily bars per symbol:
bars endpoint ~28 ms median; one indicator ~20 ms; multi-timeframe scan of 70 symbols ~1.4 s cold, ~0.8 s warm.
No concurrency or load testing has been done; scans are single-threaded Python and will need workers or
vectorisation before large universes.

## External dependencies still needed
| Need | For |
| --- | --- |
| Market-data credentials + confirmation of display/redistribution rights | Any real data |
| Fundamentals, index constituents, options chains (licensed) | Scanners B/K, options module |
| `ANTHROPIC_API_KEY` | M5 agents |
| Stripe account | M7 billing |
| Legal review (see `docs/LICENSING.md` checklist) | Public launch |

## Environment notes
Python 3.13, Node 22, PostgreSQL 16, Redis 7 available locally. Docker CLI present, daemon not running.
A configured LuxAlgo MCP endpoint in `.mcp.json` was unreachable from the sandbox and was not used.
