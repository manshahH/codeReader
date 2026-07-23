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

from _ci_guard import (  # noqa: E402 -- must follow the sys.path fix above
    MIN_TESTS_ENV,
    is_vacuous_run,
    required_minimum,
)
from _db_guard import (  # noqa: E402 -- must follow the sys.path fix above
    assert_disposable_test_database,
    db_name_from_url,
    ensure_database_exists,
    resolve_test_database_url,
)
from _run_isolation import (  # noqa: E402 -- must follow the sys.path fix above
    XDIST_WORKER_ENV,
    claim_redis_db,
    drop_database,
    isolation_enabled,
    personalize_db_url,
    redis_url_with_db,
    release_redis_db,
    run_token,
    sweep_orphan_databases,
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

_settings = _get_settings()
_base_database_url = _settings.DATABASE_URL
_base_redis_url = _settings.REDIS_URL
_get_settings.cache_clear()

# D-88: resolve the disposable BASE test database (codereader_test, or an
# explicit TEST_DATABASE_URL). This is per-PROJECT isolation from the dev DB.
_base_test_database_url = resolve_test_database_url(
    env=os.environ, default_database_url=_base_database_url,
)

# D-147: give THIS run its own database and Redis logical DB, so two concurrent
# runs (a dev plus CI, two devs, or future `pytest -n` workers) cannot corrupt
# each other via DROP SCHEMA / TRUNCATE / FLUSHDB against a shared target. On by
# default; CODEREADER_TEST_NO_ISOLATION=1 opts out to the shared base. The token
# is the xdist worker id under `-n`, else this process's pid -- unique per OS
# process either way. The personalized name still ends in `_test`, so D-88's
# guard still accepts it (asserted below, belt and suspenders).
_ISOLATE = isolation_enabled(env=os.environ)
_RUN_TOKEN = run_token(worker=os.environ.get(XDIST_WORKER_ENV), pid=os.getpid())
_run_database_url = (
    personalize_db_url(_base_test_database_url, _RUN_TOKEN)
    if _ISOLATE
    else _base_test_database_url
)
_redis_slot: int | None = None

assert_disposable_test_database(_run_database_url, env=os.environ)

if _ISOLATE:
    # Claim the Redis slot FIRST, then create the database. Two reasons
    # (D-147 follow-up): the slot is the resource that can be exhausted, so a
    # claim failure here must leak NO database (it is the last thing before the
    # DB is created, not the first thing after); and claiming records this run's
    # token as live, so the orphan sweep below can never target our own DB.
    _redis_slot = asyncio.run(claim_redis_db(_base_redis_url, _RUN_TOKEN))
    os.environ["REDIS_URL"] = redis_url_with_db(_base_redis_url, _redis_slot)

    # Drop databases left behind by runs that crashed before pytest_sessionfinish
    # could drop them (D-147 follow-up item 3): their Redis slot has since
    # expired, so their token is not live. The sweep never touches the base test
    # DB, the dev DB, this run's own DB, or any DB with an active connection.
    _base_test_db_name = db_name_from_url(_base_test_database_url)
    _stem = (
        _base_test_db_name[: -len("_test")]
        if _base_test_db_name.endswith("_test")
        else _base_test_db_name
    )
    asyncio.run(
        sweep_orphan_databases(
            _run_database_url,
            _base_redis_url,
            stem=_stem,
            protect={
                _base_test_db_name,
                db_name_from_url(_base_database_url),
                db_name_from_url(_run_database_url),
            },
        )
    )

asyncio.run(ensure_database_exists(_run_database_url))
os.environ["DATABASE_URL"] = _run_database_url

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


_passed_count = 0


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Count tests that actually PASSED their call phase, for the vacuous-green
    guard below. Skips and errors do not count -- that is the whole point."""
    global _passed_count
    if report.when == "call" and report.passed:
        _passed_count += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """D-147 teardown (drop this run's DB, release its Redis slot) plus the D-152
    vacuous-green guard. Teardown never raises -- a teardown failure must not
    turn a green run red (the Redis TTL and pid reuse self-heal a skipped
    teardown anyway)."""
    if _ISOLATE:
        try:
            asyncio.run(drop_database(_run_database_url))
        except Exception as exc:  # noqa: BLE001 -- teardown is best-effort by design
            print(f"D-147 teardown: could not drop {_run_database_url!r}: {exc}", file=sys.stderr)
        if _redis_slot is not None:
            try:
                asyncio.run(release_redis_db(_base_redis_url, _redis_slot, _RUN_TOKEN))
            except Exception as exc:  # noqa: BLE001 -- best-effort; TTL frees it anyway
                print(f"D-147 teardown: could not release redis slot: {exc}", file=sys.stderr)

    # D-152: refuse a green that ran too few tests to mean anything (e.g. a whole
    # class silently skipped). Opt-in via CODEREADER_MIN_TESTS, set only where the
    # FULL suite runs (CI), so a local subset run is never affected. Skipped under
    # xdist, where each worker sees only its shard of the count.
    if os.environ.get(XDIST_WORKER_ENV):
        return
    minimum = required_minimum(os.environ)
    if exitstatus == 0 and is_vacuous_run(_passed_count, minimum):
        print(
            f"D-152 GUARD: only {_passed_count} tests passed, below the "
            f"{MIN_TESTS_ENV}={minimum} floor -- refusing a vacuous green. A whole "
            f"class of tests likely did not run (all skipped, a collection filter, "
            f"a plugin misconfig). Investigate before trusting this run.",
            file=sys.stderr,
        )
        session.exitstatus = 1
