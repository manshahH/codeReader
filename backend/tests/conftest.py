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

from _db_guard import (  # noqa: E402 -- must follow the sys.path fix above
    assert_disposable_test_database,
    ensure_database_exists,
    resolve_test_database_url,
)

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

# D-88: pytest's DB fixtures below are destructive (DROP SCHEMA CASCADE) and
# used to run unconditionally against DATABASE_URL -- which in this project
# is the SAME database the API/pipeline use for real content. Confirmed by
# direct reproduction: a plain `pytest` run destroyed all real content twice.
#
# Resolve the test database (TEST_DATABASE_URL if set, else DATABASE_URL with
# `_test` appended), refuse to proceed if it isn't explicitly declared
# disposable, create it on demand if it doesn't exist yet, then override the
# DATABASE_URL env var itself -- BEFORE any OTHER `app.config.get_settings()`
# call anywhere in the process (this module runs, and this block executes,
# before pytest imports any test module or fixture). This is deliberately an
# env-var override rather than threading a URL through every call site:
# alembic/env.py, app/db.py's create_engine() default, and app/main.py's
# lifespan all independently read get_settings().DATABASE_URL, and three test
# files construct a bare create_engine() of their own -- an env override makes
# every one of those transparently target the isolated database with no
# per-call-site changes, so there is no path left that can silently keep
# pointing at the real one.
#
# The base URL to derive from is get_settings().DATABASE_URL, NOT
# os.environ["DATABASE_URL"] directly: this project supplies DATABASE_URL via
# the `.env` FILE (pydantic-settings parses it internally and never writes it
# into os.environ), so reading raw os.environ here would silently fall back to
# a guessed default instead of the actually-configured value. get_settings()
# is `@lru_cache`d, so it is cleared immediately after this read (nothing else
# may have called it yet) and again after the override, so every later caller
# -- including this same module's own `migrated_db` fixture -- reconstructs
# Settings from the now-overridden env var rather than a stale cached one.
from app.config import get_settings as _get_settings  # noqa: E402

_base_database_url = _get_settings().DATABASE_URL
_get_settings.cache_clear()

_test_database_url = resolve_test_database_url(
    env=os.environ, default_database_url=_base_database_url,
)
assert_disposable_test_database(_test_database_url, env=os.environ)
asyncio.run(ensure_database_exists(_test_database_url))
os.environ["DATABASE_URL"] = _test_database_url
_get_settings.cache_clear()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    config_path = repo_root / "alembic.ini"
    if not config_path.exists():
        config_path = backend_root / "alembic.ini"
    return Config(config_path)


async def _reset_public_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_db(alembic_config: Config) -> Iterator[None]:
    # Re-checked here, not just at module load (belt and suspenders): this is
    # the actual destructive call, and it must refuse to run -- never drop,
    # never silently proceed -- if the target isn't a declared-disposable
    # database, however DATABASE_URL got to whatever value it currently holds.
    from app.config import get_settings

    database_url = get_settings().DATABASE_URL
    assert_disposable_test_database(database_url, env=os.environ)
    asyncio.run(_reset_public_schema(database_url))
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
