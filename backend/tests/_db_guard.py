"""Test-database isolation guard (D-88).

`conftest.py`'s `migrated_db` fixture is destructive by design: it DROPs and
recreates the entire `public` schema so every test session starts from a
known-clean, fully-migrated state. Before this module existed, that fixture
ran unconditionally against whatever `DATABASE_URL` resolved to -- which, in
this project, is the SAME database the API and pipeline use for real content
(root `.env` and `backend/.env` both point `DATABASE_URL` at the same dev
Postgres). A plain `pytest` invocation therefore silently destroyed all real
content, twice, confirmed by direct reproduction.

The fix mirrors D-62's `CODEREADER_ALLOW_SEED=1` pattern: a destructive
operation must be a conscious, structurally-guarded opt-in, never pytest's
default side effect. Every function here is pure string/URL logic with NO
database I/O except `ensure_database_exists`, which only ever CREATEs (never
drops) and only after the guard has already accepted the target name.
"""

from __future__ import annotations

import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_SUFFIX = "_test"
TEST_DB_ENV_FLAG = "CODEREADER_TEST_DB"
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"

# Postgres database identifiers this module will ever CREATE are restricted to
# this charset -- defense in depth against a pathological DATABASE_URL ending
# up interpolated into a raw `CREATE DATABASE "..."` statement (identifiers
# cannot be bind-parameterized). The `_test` suffix guard already constrains
# this in practice; this is a second, independent check.
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


class DatabaseGuardError(RuntimeError):
    """Raised when the destructive test-schema fixture would otherwise run
    against a database that has not been explicitly declared disposable."""


def db_name_from_url(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def is_declared_test_database(url: str, *, env: dict[str, str]) -> bool:
    """True iff `url` is explicitly declared safe to DROP SCHEMA CASCADE:
    the database name ends in `_test`, OR the operator set
    CODEREADER_TEST_DB=1 to explicitly confirm the target is disposable
    (an escape hatch for a pre-existing disposable DB whose name does not
    happen to end in `_test`). Either alone is sufficient; this is an OR,
    matching the requested "must end in _test, or CODEREADER_TEST_DB=1 must
    be set, or both."
    """
    name = db_name_from_url(url)
    return name.endswith(TEST_DB_SUFFIX) or env.get(TEST_DB_ENV_FLAG) == "1"


def assert_disposable_test_database(url: str, *, env: dict[str, str]) -> None:
    """FAIL LOUDLY, before any DB I/O, unless `url` is declared disposable.

    Pure function: inspects the URL string and `env` only, touches no
    database and no network. Callers (the `migrated_db` fixture) must call
    this BEFORE any DROP SCHEMA -- calling it can never itself destroy
    anything, which is what lets a unit test prove "the guard fires" without
    needing a real database at all.
    """
    if not is_declared_test_database(url, env=env):
        name = db_name_from_url(url) or "(empty)"
        raise DatabaseGuardError(
            f"refusing to run the destructive test-schema fixture against database "
            f"{name!r}: its name does not end in {TEST_DB_SUFFIX!r} and "
            f"{TEST_DB_ENV_FLAG}=1 is not set. This fixture DROPs and recreates the "
            "ENTIRE public schema every test session -- pointing it at a real "
            "database destroys all content in it (this happened twice: see "
            "docs/07-decisions.md D-88). Point DATABASE_URL/TEST_DATABASE_URL at a "
            f"database whose name ends in {TEST_DB_SUFFIX!r} (the default -- see "
            f"derive_test_database_url), or set {TEST_DB_ENV_FLAG}=1 to explicitly "
            f"confirm {name!r} is disposable.",
        )


def derive_test_database_url(base_url: str) -> str:
    """`<name>` -> `<name>_test` (idempotent if already suffixed), same host/
    user/password/port/query as `base_url`. This is the DEFAULT test target
    (D-88 point 2): pytest, run with no special configuration, never touches
    the database DATABASE_URL names.
    """
    parts: SplitResult = urlsplit(base_url)
    name = parts.path.lstrip("/")
    if not name:
        raise DatabaseGuardError(
            f"cannot derive a test database from {base_url!r}: no database name in the URL path",
        )
    test_name = name if name.endswith(TEST_DB_SUFFIX) else name + TEST_DB_SUFFIX
    return urlunsplit(parts._replace(path="/" + test_name))


def resolve_test_database_url(*, env: dict[str, str], default_database_url: str) -> str:
    """TEST_DATABASE_URL, if set, always wins (an operator's explicit
    choice); otherwise DERIVE one from `default_database_url`. Does not touch
    the database and does not apply the guard -- callers must still call
    `assert_disposable_test_database` on the result.

    `default_database_url` must be the caller's fully-resolved base URL (in
    `conftest.py`, `app.config.get_settings().DATABASE_URL`) -- NOT read from
    `env` directly here: `DATABASE_URL` in this project is normally supplied
    via the `.env` FILE, which pydantic-settings parses internally and never
    writes back into `os.environ`. Reading `env["DATABASE_URL"]` directly
    would silently miss it and fall back to a guessed default, which is
    exactly how this bug was first caught -- a guessed default pointed at the
    wrong port and only surfaced as a confusing connection failure.
    """
    explicit = env.get(TEST_DATABASE_URL_ENV)
    if explicit:
        return explicit
    return derive_test_database_url(default_database_url)


def _admin_url(target_url: str) -> str:
    """Same host/user/password/port as `target_url`, database `postgres` --
    the maintenance database every Postgres instance has, needed to CREATE a
    database that does not exist yet (you cannot create a database while
    connected to it)."""
    parts = urlsplit(target_url)
    return urlunsplit(parts._replace(path="/postgres"))


async def ensure_database_exists(target_url: str) -> None:
    """CREATE DATABASE `target_url`'s db if it does not already exist.

    Never drops or alters anything -- the only DDL here is a conditional
    CREATE. Callers must have already run `assert_disposable_test_database`
    on `target_url`; this function additionally re-validates the identifier
    charset before interpolating it into `CREATE DATABASE "..."` (identifiers
    cannot be bind-parameterized in SQL), so a malformed name fails loudly
    instead of being passed to the database verbatim.
    """
    name = db_name_from_url(target_url)
    if not _SAFE_IDENTIFIER.match(name):
        raise DatabaseGuardError(
            f"refusing to CREATE DATABASE for {name!r}: contains characters outside "
            f"{_SAFE_IDENTIFIER.pattern}",
        )
    admin_engine = create_async_engine(
        _sqlalchemy_url(_admin_url(target_url)),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": name},
            )
            if not exists:
                # CREATE DATABASE cannot run inside a transaction block and its
                # identifier cannot be bind-parameterized; `name` is charset-
                # validated above.
                await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin_engine.dispose()


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url
