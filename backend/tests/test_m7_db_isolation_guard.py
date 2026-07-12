"""D-88: the destructive test-schema fixture must refuse to run against
anything that isn't explicitly declared a disposable test database.

Confirmed by direct reproduction (docs/07-decisions.md D-88): running `pytest`
DROP SCHEMA CASCADE'd the real dev database twice, destroying real content,
because `migrated_db` used to run unconditionally against whatever
DATABASE_URL resolved to -- the SAME database the API/pipeline use. These
tests exercise `_db_guard.py` directly, independent of the real `migrated_db`
fixture, so "the guard fires" is provable without needing a second database
wipe to prove it.
"""

from __future__ import annotations

import os
import uuid

import pytest
from _db_guard import (
    DatabaseGuardError,
    assert_disposable_test_database,
    derive_test_database_url,
    ensure_database_exists,
    is_declared_test_database,
    resolve_test_database_url,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_REAL_LOOKING_URL = "postgresql://codereader:codereader@localhost:5433/codereader"
_TEST_SUFFIXED_URL = "postgresql://codereader:codereader@localhost:5433/codereader_test"


# --- the guard itself: pure, no DB I/O -- these prove nothing can be dropped
# --- as a side effect of the check failing or passing.


def test_guard_rejects_a_real_looking_database_name_with_no_flag() -> None:
    with pytest.raises(DatabaseGuardError, match="codereader"):
        assert_disposable_test_database(_REAL_LOOKING_URL, env={})


def test_guard_rejection_message_names_the_offending_database() -> None:
    # The message is the operator's only signal when this fires in a real
    # session -- assert it actually names the database, not just "something
    # went wrong".
    with pytest.raises(DatabaseGuardError) as exc_info:
        assert_disposable_test_database(_REAL_LOOKING_URL, env={})
    assert "codereader" in str(exc_info.value)
    assert "_test" in str(exc_info.value)


def test_guard_accepts_a_test_suffixed_database_name() -> None:
    assert_disposable_test_database(_TEST_SUFFIXED_URL, env={})  # must not raise


def test_guard_accepts_a_real_looking_name_when_the_flag_is_explicitly_set() -> None:
    assert_disposable_test_database(_REAL_LOOKING_URL, env={"CODEREADER_TEST_DB": "1"})


def test_guard_still_rejects_when_the_flag_is_present_but_not_exactly_1() -> None:
    with pytest.raises(DatabaseGuardError):
        assert_disposable_test_database(_REAL_LOOKING_URL, env={"CODEREADER_TEST_DB": "true"})


def test_is_declared_test_database_matches_assert_disposable_test_database() -> None:
    # The predicate and the raising assertion must agree in both directions,
    # or one could be silently more permissive than the other.
    assert is_declared_test_database(_TEST_SUFFIXED_URL, env={}) is True
    assert is_declared_test_database(_REAL_LOOKING_URL, env={}) is False
    assert is_declared_test_database(_REAL_LOOKING_URL, env={"CODEREADER_TEST_DB": "1"}) is True


# --- derivation / resolution -------------------------------------------------


def test_derive_test_database_url_appends_the_suffix() -> None:
    assert derive_test_database_url(_REAL_LOOKING_URL) == _TEST_SUFFIXED_URL


def test_derive_test_database_url_is_idempotent_if_already_suffixed() -> None:
    assert derive_test_database_url(_TEST_SUFFIXED_URL) == _TEST_SUFFIXED_URL


def test_derive_test_database_url_preserves_host_user_password_port() -> None:
    derived = derive_test_database_url("postgresql://u:p@example.com:9999/mydb")
    assert derived == "postgresql://u:p@example.com:9999/mydb_test"


def test_resolve_test_database_url_derives_by_default() -> None:
    resolved = resolve_test_database_url(env={}, default_database_url=_REAL_LOOKING_URL)
    assert resolved == _TEST_SUFFIXED_URL


def test_resolve_test_database_url_explicit_override_wins() -> None:
    resolved = resolve_test_database_url(
        env={"TEST_DATABASE_URL": "postgresql://x:y@h/custom_test"},
        default_database_url=_REAL_LOOKING_URL,
    )
    assert resolved == "postgresql://x:y@h/custom_test"


def test_resolve_test_database_url_never_reads_database_url_from_env_directly() -> None:
    # D-88's actual bug: DATABASE_URL in this project is supplied via the
    # `.env` FILE, which pydantic-settings parses without ever writing it
    # into os.environ. A `default_database_url` caller-supplied argument is
    # therefore load-bearing, not an env["DATABASE_URL"] read -- an `env`
    # dict that HAS a (wrong/stale) DATABASE_URL key must be ignored in favor
    # of the explicit argument.
    resolved = resolve_test_database_url(
        env={"DATABASE_URL": "postgresql://wrong:wrong@nowhere/decoy"},
        default_database_url=_REAL_LOOKING_URL,
    )
    assert resolved == _TEST_SUFFIXED_URL


# --- ensure_database_exists: real DB I/O, but only ever CREATE, never DROP --


async def test_ensure_database_exists_creates_and_is_idempotent() -> None:
    scratch_name = f"codereader_guard_probe_{uuid.uuid4().hex[:10]}_test"
    scratch_url = f"postgresql://codereader:codereader@localhost:5433/{scratch_name}"
    admin_url = "postgresql+asyncpg://codereader:codereader@localhost:5433/postgres"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists_before = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": scratch_name},
            )
        assert exists_before is None

        await ensure_database_exists(scratch_url)
        await ensure_database_exists(scratch_url)  # idempotent: must not raise on the 2nd call

        async with admin_engine.connect() as conn:
            exists_after = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": scratch_name},
            )
        assert exists_after == 1
    finally:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}"'))
        await admin_engine.dispose()


async def test_ensure_database_exists_rejects_an_unsafe_identifier() -> None:
    # assert_disposable_test_database would already reject this name (no
    # `_test` suffix), but ensure_database_exists re-validates independently
    # (defense in depth: identifiers can't be bind-parameterized) rather than
    # trusting a caller who skipped the guard.
    with pytest.raises(DatabaseGuardError):
        await ensure_database_exists(
            'postgresql://codereader:codereader@localhost:5433/robert"; DROP TABLE x; --_test',
        )


# --- end-to-end: the REAL session this test itself is running in -----------


def test_current_pytest_session_is_isolated_from_the_dev_database() -> None:
    """The strongest proof: by the time ANY test runs, conftest.py's
    module-level override has already run. Assert its effect directly rather
    than re-deriving it, so this fails loudly if a future edit reorders
    conftest.py and the override stops happening before collection."""
    from app.config import get_settings

    database_url = get_settings().DATABASE_URL
    assert is_declared_test_database(database_url, env=os.environ)
    assert "codereader" in database_url  # sanity: still the same logical project db family
