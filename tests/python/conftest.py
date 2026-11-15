"""Shared fixtures. Tests run on SQLite by default; set TEST_DATABASE_URL to run them on PostgreSQL."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime

import pytest

_tmp = tempfile.mkdtemp(prefix="legion-test-")
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["DATA_PROVIDER"] = "demo"
os.environ["REDIS_URL"] = ""
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-0123"

# A fixed instant (Friday 2025-06-13, after the close) so demo data is identical on every run.
FROZEN_NOW = datetime(2025, 6, 13, 21, 30, tzinfo=UTC)


@pytest.fixture(scope="session")
def demo():
    from legion_data import DemoProvider

    return DemoProvider(clock=lambda: FROZEN_NOW)


@pytest.fixture()
def client(demo):
    from fastapi.testclient import TestClient

    from legion_api import deps
    from legion_api.db import Base, get_engine
    from legion_api.main import app

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    deps.get_rate_limiter().reset()
    app.dependency_overrides[deps.get_market] = lambda: _MARKET.setdefault("m", deps.CachedBars(demo, 3600))
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


_MARKET: dict = {}


def register(client, email="ada@example.com", password="correct-horse-battery", name="Ada"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "display_name": name})
    assert r.status_code == 201, r.text
    client.cookies.clear()  # tests authenticate explicitly with the bearer token
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
