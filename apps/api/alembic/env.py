from alembic import context

from legion_api import models  # noqa: F401  (registers tables on Base.metadata)
from legion_api.db import Base, get_engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; set DATABASE_URL and run online.")
run_migrations_online()
