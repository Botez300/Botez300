"""The Alembic migrations must produce exactly the schema the models declare (PostgreSQL only)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
                                reason="set TEST_DATABASE_URL to a PostgreSQL database")


def test_migrations_match_models():
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import text

    from legion_api import models  # noqa: F401
    from legion_api.db import Base, get_engine

    api = Path(__file__).resolve().parents[2] / "apps" / "api"
    cfg = Config(str(api / "alembic.ini"))
    cfg.set_main_option("script_location", str(api / "alembic"))
    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("drop table if exists alembic_version"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        left = conn.execute(text("select count(*) from information_schema.tables where table_schema='public' "
                                 "and table_name <> 'alembic_version'")).scalar_one()
    assert left == 0
