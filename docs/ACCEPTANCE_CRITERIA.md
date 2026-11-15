# Acceptance criteria

A milestone is complete when every criterion is met and the evidence is reproducible from the repository.

## Milestone 0 — audit and design ✅
- [x] Environment, tools and licences audited; results recorded (PROJECT_STATUS.md, LICENSING.md).
- [x] PRODUCT_SPEC, FEATURE_PARITY_MATRIX, ARCHITECTURE, DATA_PROVIDERS, LICENSING, SECURITY, ROADMAP,
      ACCEPTANCE_CRITERIA, PROJECT_STATUS, CLAUDE.md exist and match the code.

## Milestone 1 — functional MVP
| # | Criterion | Evidence | Met |
| --- | --- | --- | --- |
| 1 | Repeatable local startup | `make setup && make dev`; `docker-compose.yml` | ✅ Local path verified in the sandbox; compose stack built and exercised by the CI `e2e` job |
| 2 | Persistent database with migrations | Alembic `0001`; `test_migrations_match_models` on PostgreSQL 16 | ✅ |
| 3 | Secure authentication | `tests/python/test_api.py` auth tests | ✅ for the MVP scope; gaps listed in SECURITY.md |
| 4 | Working dashboard | e2e "registration opens the Command Center…" | ✅ |
| 5 | Interactive Vela chart with attribution | e2e "symbol search opens a working chart…"; NOTICE | ✅ |
| 6 | Provider-backed historical OHLCV or labelled demo data | Demo provider (labelled `SIMULATED`); Alpaca/Polygon adapters with mock-transport tests | ✅ demo. ⚠️ vendor adapters unverified against live services |
| 7 | ≥ 15 independently verified indicators | 19 golden-tested vs TA-Lib + 6 property-tested; lookahead test on all 25 | ✅ |
| 8 | Saved watchlists | API tests + e2e reload check | ✅ |
| 9 | Configurable technical scanner with real results | `test_scanner.py`; e2e re-checks a result row against its rules | ✅ |
| 10 | Symbol search | API test + e2e | ✅ |
| 11 | Original navigation; every page works end-to-end | 6 e2e flows, no page errors or 5xx | ✅ |
| 12 | Automated tests and CI definition | 184 Python tests, 6 e2e; `.github/workflows/ci.yml` | ✅ CI green on PR #5 (python, web, e2e) |

## Milestone 2 — advanced technical analysis (draft)
- Every new detector has a documented rule, an algorithm version and a test that it emits nothing before its
  confirmation bar (truncation test).
- Patterns report all fields listed in the brief, including `developing` vs `confirmed`.
- Relative strength and ATH-AVWAP status are available as scanner columns.
- Golden or from-definition tests for each new indicator; `test_no_lookahead` covers them automatically.

## Standing gates (all milestones)
`make lint`, `make test`, `make test-pg` and `make e2e` pass; no fabricated data paths; parity matrix and status updated.
