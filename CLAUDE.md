# Legion Quant Terminal — working notes for Claude Code sessions

Resume by reading `PROJECT_STATUS.md` (what is verified) and `docs/ROADMAP.md` (next task), then continue from there.

## Ground rules (from the product owner's brief)
- Working, tested, integrated features over mockups. A milestone is done only when `docs/ACCEPTANCE_CRITERIA.md` passes.
- Never fabricate quotes, signals, backtest results or benchmarks. Demo data is synthetic, uses fictional tickers and is
  labelled `SIMULATED`; never substitute it silently when a real provider is configured (`build_provider` raises instead).
- No lookahead: indicators use bars ≤ t; scans use completed bars only. Every new indicator gets the `test_no_lookahead` check.
- Original implementations only. No proprietary formulas, no competitor branding or UI copies, no AGPL dependencies.
- Keep the Vela attribution visible on any screen with a chart (`NOTICE`, in-chart mark, "Charts by Vela" link).
- Update `PROJECT_STATUS.md` and the parity matrix whenever a feature's state changes.

## Commands
- `make setup | dev | test | test-pg | lint | e2e` (see `Makefile`). Python venv is `.venv`.
- New migration: `cd apps/api && ../../.venv/bin/alembic revision --autogenerate -m "..."`; `make test-pg` checks drift.
- This sandbox has no Docker daemon: start PostgreSQL with `service postgresql start`; the compose stack is untested here.

## Conventions
- Single source of truth for indicators: `services/indicators/legion_indicators/registry.py`. The API serves the catalog;
  the web chart registers each entry as a Vela native indicator whose values come from `POST /indicators/compute`.
  Do not re-implement indicator math in TypeScript.
- Indicators: pure functions on float64 arrays, NaN during warm-up, golden-tested against TA-Lib where one exists
  (TA-Lib is test-only), otherwise property-tested from the definition.
- Daily bars are indexed at 00:00 UTC of the session date; weekly/monthly are derived by `to_timeframe`.
- Every tenant-owned table has `org_id`; load rows through an `owned(...)` helper that filters by the caller's org and
  returns 404 for other tenants. Add a case to `test_tenants_cannot_see_or_touch_each_others_data` for new resources.
- Plan limits live in `apps/api/legion_api/entitlements.py`; never branch on a plan name elsewhere.
- Scan labels are produced in two places that must stay in sync: `Operand.label()` (Python) and `operandLabel` (web).
- Frontend calls the API only through `apps/web/src/lib/api.ts` (same-origin `/api` proxy, cookie session).
