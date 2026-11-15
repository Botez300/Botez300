# Legion Quant Terminal

A multi-tenant market-research terminal: charting, a verified indicator library and a rule-based
scanner on a provider-independent data layer. **Milestone 1 (functional MVP) is implemented**; see
[PROJECT_STATUS.md](PROJECT_STATUS.md) for exactly what works and [docs/ROADMAP.md](docs/ROADMAP.md) for what does not yet.

Out of the box it runs in **demo mode**: fictional tickers with deterministic synthetic prices, labelled
`SIMULATED` everywhere. Real data needs your own Alpaca or Polygon/Massive credentials
([docs/DATA_PROVIDERS.md](docs/DATA_PROVIDERS.md)). It is a research tool, not investment advice.

## Run it

**Docker** (PostgreSQL, Redis, API, web):

```bash
cp .env.example .env
docker compose up --build        # http://localhost:3000  (API docs: http://localhost:8000/docs)
```

**Without Docker** (Python 3.11+, Node 22+, a local PostgreSQL 16 with a `legion` role and database):

```bash
make setup      # virtualenv + npm install
make dev        # migrates the database, then runs the API on :8000 and the web app on :3000
```

Create an account on the sign-in page; each account gets its own workspace.

## Test it

```bash
make test       # 184 Python tests on SQLite (indicators vs TA-Lib, data, scanner, API, tenant isolation)
make test-pg    # the same on PostgreSQL plus the migration/model drift check
make lint       # ruff, mypy, tsc
make e2e        # 6 Playwright browser flows against the running stack
```

## Layout

| Path | What |
| --- | --- |
| `apps/api` | FastAPI service: auth, tenancy, market data, indicators, watchlists, scans. Alembic migrations. |
| `apps/web` | Next.js terminal UI. Charts are rendered by [Vela](https://velacharts.dev) (Apache-2.0). |
| `services/indicators` | `legion_indicators`: indicator math and the registry every other component reads. |
| `services/data-ingestion` | `legion_data`: provider contract, demo/Alpaca/Polygon adapters, NYSE calendar, data-quality checks. |
| `services/market-scanner` | `legion_scanner`: scan schema, engine (completed bars only), templates. |
| `tests/python`, `tests/e2e` | Automated tests. |
| `infra`, `docker-compose.yml` | Container builds and the local stack. |
| `docs` | Spec, architecture, parity matrix, licensing, security, roadmap, acceptance criteria. |
