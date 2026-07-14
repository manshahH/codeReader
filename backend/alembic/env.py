from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings
from app.db import normalize_database_url
from app.models import metadata

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False, NOT the fileConfig default of True: the
    # default disables every logger already imported into the process, which
    # here means all of `app.*` (conftest and any in-process migration run
    # import the app first). That silently swallowed app logging, including
    # normalize_database_url()'s warning about dropped DATABASE_URL params --
    # the one line that explains a connection failure (D-112).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def run_migrations_offline() -> None:
    url, _ = normalize_database_url(get_settings().DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    url, connect_args = normalize_database_url(get_settings().DATABASE_URL)
    configuration["sqlalchemy.url"] = url
    # Same normalizer as app/db.py's create_engine(), so `alembic upgrade head`
    # and the app can never disagree about a URL (D-112). connect_args carries
    # the SSLContext, which cannot be expressed in the URL at all.
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
