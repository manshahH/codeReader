from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.db import create_engine, create_session_factory

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    # Makes `import pipeline...` work from backend/tests regardless of the
    # pytest invocation's rootdir/cwd; pipeline/ lives at the repo root,
    # outside the `app` package this pyproject.toml installs.
    sys.path.insert(0, str(_REPO_ROOT))

# Module-level, not a fixture: pydantic-settings resolves Settings' env_file
# (".env") relative to cwd, and pytest runs from the repo root, where the
# untracked, gitignored root .env carries a real SENTRY_DSN for local compose
# use. Several test modules import `app.main` (which calls init_sentry()) at
# module scope, so pytest collection itself -- before any test or fixture
# runs -- would otherwise initialize a real Sentry client and start sending
# telemetry for a plain test run. An OS env var beats the .env file in
# pydantic-settings' precedence, so this neutralizes it for the whole
# session; any test that wants Sentry actually active sets SENTRY_DSN itself.
os.environ.setdefault("SENTRY_DSN", "")


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    config_path = repo_root / "alembic.ini"
    if not config_path.exists():
        config_path = backend_root / "alembic.ini"
    return Config(config_path)


async def _reset_public_schema() -> None:
    engine = create_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_db(alembic_config: Config) -> Iterator[None]:
    asyncio.run(_reset_public_schema())
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()
