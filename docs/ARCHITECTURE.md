# Architecture

```
Browser ──► Next.js (apps/web) ──/api proxy──► FastAPI (apps/api) ──► PostgreSQL   users, orgs, watchlists, scans, audit
              Vela chart                          │                └─► Redis        shared login rate limiting (optional)
                                                  ├─► legion_indicators   indicator registry + math
                                                  ├─► legion_scanner      scan schema + engine
                                                  └─► legion_data         provider contract ─► demo | Alpaca | Polygon/Massive
```

## Decisions
| Area | Choice | Why |
| --- | --- | --- |
| Charts | `@luxalgo/vela` 0.10.8 (Apache-2.0), bare `Vela` chart inside our own chrome | Evaluated first as requested: native renderer, drawing tools, replay, plugin SDK. Attribution kept (see LICENSING). Lightweight Charts remains the fallback. |
| Indicator values on the chart | Computed by the API, drawn through Vela's native-indicator SDK | One implementation shared with the scanner and later the backtester. Vela's built-in studies are not used for analysis. |
| API | FastAPI + Pydantic v2, sync SQLAlchemy 2, Alembic | Scans and indicators are CPU-bound; sync handlers run in the threadpool. |
| Auth | Argon2id passwords, HS256 JWT in an httpOnly SameSite=Lax cookie (Bearer also accepted) | Same-origin proxy keeps the cookie first-party; no token in JS storage. |
| Tenancy | `org_id` on every tenant row, membership re-checked per request, 404 for foreign rows | Simple to audit and test. PostgreSQL row-level security is a hardening item (M8). |
| Data | Daily OHLCV through `MarketDataProvider`; weekly/monthly derived | Works with every vendor's cheapest tier. Intraday is M2+. |
| Bars cache | In-process TTL cache with per-symbol single-flight | Enough for one API process. A TimescaleDB bar store + ingestion worker replaces it when history must be shared (M3). |
| Backtesting | Not started. LEAN (Apache-2.0) to be evaluated against a lightweight in-house event-driven engine in M4 | LEAN is heavy (.NET, containers); decision deferred until the strategy schema exists. |

## Repository structure and deviations from the brief
Implemented: `apps/api`, `apps/web`, `services/indicators`, `services/data-ingestion`, `services/market-scanner`,
`infra`, `tests`, `docs`.

Not created yet, on purpose — empty folders would misrepresent progress: `services/backtesting`, `alerts`,
`paper-trading`, `ai-orchestrator`, `reporting` (M3–M8); `packages/strategy-schema` (M4);
`packages/chart-extensions`, `packages/ui`, `packages/shared-types` (the web app's `src/lib` and `src/components`
hold this code until a second consumer exists). `packages/indicator-contracts` is the registry in
`services/indicators`, served as JSON by `GET /api/v1/indicators`.

Services are Python packages imported by the API process today. They are separated by package boundaries so that
scanning and ingestion can move to queue workers (M3) without changing callers.

## Request flow: a scan
1. Web posts a `ScanDefinition` (JSON rules) and a universe to `POST /api/v1/scans/run`.
2. The API validates schema and semantics (indicator ids, params, outputs), resolves the universe (provider
   universe, a symbol list, or a watchlist owned by the caller's org) and enforces the plan's symbol cap.
3. The engine loads daily bars per symbol, derives weekly/monthly, **drops any forming bar**, computes each distinct
   operand once, and evaluates the rule tree with three-valued logic (true / false / insufficient history).
4. The response lists the conditions as evaluated, per-row operand values, bar date, data status and
   verification state, plus symbols that could not be evaluated and why.

## Data model
`organizations` ─< `memberships` >─ `users`; `watchlists` ─< `watchlist_items`; `saved_scans`; `audit_log`.
Migrations in `apps/api/alembic/versions`; a test fails if they drift from the models.
