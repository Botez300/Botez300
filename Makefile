# Local development without Docker. Needs Python 3.11+, Node 22+, PostgreSQL 16 (and optionally Redis).
PY := .venv/bin/python
SHELL := /bin/bash

.PHONY: setup migrate api web dev test test-pg lint e2e

setup:            ## Create the virtualenv and install everything
	python3 -m venv .venv
	.venv/bin/pip install -q -e services/indicators -e services/data-ingestion -e services/market-scanner -e apps/api
	.venv/bin/pip install -q -r requirements-dev.txt
	cd apps/web && npm ci --no-audit --no-fund

migrate:          ## Apply database migrations (uses DATABASE_URL)
	cd apps/api && ../../.venv/bin/alembic upgrade head

api:              ## Run the API on :8000 with reload
	cd apps/api && ../../.venv/bin/uvicorn legion_api.main:app --reload --port 8000

web:              ## Run the web app on :3000
	cd apps/web && npm run dev

dev: migrate      ## Run API and web together
	$(MAKE) -j2 api web

test:             ## Python tests on SQLite
	$(PY) -m pytest

test-pg:          ## Python tests on PostgreSQL, including the migration check (set TEST_DATABASE_URL)
	TEST_DATABASE_URL=$${TEST_DATABASE_URL:-postgresql+psycopg://legion:legion@localhost:5432/legion_test} $(PY) -m pytest

lint:             ## Ruff, mypy and TypeScript
	.venv/bin/ruff check services apps/api tests/python
	.venv/bin/mypy services/indicators/legion_indicators services/data-ingestion/legion_data services/market-scanner/legion_scanner apps/api/legion_api
	cd apps/web && npx tsc --noEmit

e2e:              ## Browser tests against a running stack (BASE_URL defaults to http://localhost:3000)
	cd tests/e2e && npx playwright test --trace off
