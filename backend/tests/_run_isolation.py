"""Per-RUN test isolation (D-147).

D-88 isolated pytest from the DEV database: it points every test at
`codereader_test` instead of the database real content lives in. It did NOT make
two test RUNS safe against each other. `migrated_db` runs `DROP SCHEMA CASCADE`,
`clean_m4_tables` runs `TRUNCATE`, and the Redis fixtures run `FLUSHDB` -- all
global singletons against one shared database and one shared Redis. Two `pytest`
processes at once (a dev plus CI, two devs, or `pytest -n` workers) therefore
corrupt each other: schema DDL races to a `pg_type` catalog UniqueViolation, and
a `TRUNCATE users` in one run makes the other run's `session.get(User)` return
None mid-request, surfacing as a 401 on a freshly issued token. Proven in D-147.

This module adds the missing layer WITHOUT touching D-88's functions (whose exact
contract is pinned by test_m7_db_isolation_guard): it takes D-88's resolved
base test URL and gives THIS run its own database and its own Redis logical DB.

  * Postgres: `<base>_<token>_test`, where the token is the xdist worker id when
    running under `pytest -n`, else `p<pid>`. Both are unique per OS process, so
    two separate invocations and two xdist workers all differ. The name still
    ends in `_test`, so D-88's guard still accepts it. Created on demand, dropped
    at session end. The namespace is unbounded and pid reuse is self-healing
    (migrated_db DROP SCHEMAs on reuse), so runs never accumulate.
  * Redis: a logical DB claimed atomically from 1..15 (SET NX on a registry key
    in DB 0, which no run ever selects and so no FLUSHDB ever clears). The claim
    carries a TTL so a crashed run's slot self-frees. FLUSHDB then only ever
    clears this run's own logical DB.

Isolation is ON BY DEFAULT -- a developer running `pytest` the obvious way gets
it without setting anything. CODEREADER_TEST_NO_ISOLATION=1 opts out (a fixed,
shared `codereader_test` + Redis DB 0), for the rare case of inspecting the
database after a single-process run; it is never needed for safety.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

NO_ISOLATION_ENV_FLAG = "CODEREADER_TEST_NO_ISOLATION"
XDIST_WORKER_ENV = "PYTEST_XDIST_WORKER"

# Redis DB 0 holds the slot registry and is never handed to a run, so no run's
# FLUSHDB can ever clear it. Runs get 1..15 (15 concurrent runs / xdist workers).
REDIS_REGISTRY_DB = 0
REDIS_RUN_DBS = tuple(range(1, 16))
_REDIS_SLOT_KEY = "codereader:test:redis_slot:{index}"
# A slot claim outlives the longest plausible suite (the full run is ~440s) but
# self-frees long before a name could be confused with a live run, so a hard
# crash that skips teardown does not strand a slot forever.
REDIS_SLOT_TTL_SECONDS = 3 * 60 * 60

_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9]")


class RunIsolationError(RuntimeError):
    """Raised when per-run isolation cannot be established (e.g. every Redis
    logical DB is already claimed by another concurrent run)."""


def isolation_enabled(*, env: dict[str, str]) -> bool:
    """On by default; only an explicit CODEREADER_TEST_NO_ISOLATION=1 disables
    it. Anything else (unset, "0", "false") keeps isolation, because the safe
    state must be the one a developer gets without knowing this exists."""
    return env.get(NO_ISOLATION_ENV_FLAG) != "1"


def run_token(*, worker: str | None, pid: int) -> str:
    """A token unique per OS process. Under `pytest -n`, xdist sets
    PYTEST_XDIST_WORKER (e.g. "gw0"); otherwise fall back to the pid. Sanitized
    to the safe identifier charset so it can go straight into a database name."""
    raw = worker if worker else f"p{pid}"
    token = _SAFE_TOKEN.sub("", raw)
    if not token:  # worker was all-punctuation, which should never happen
        token = f"p{pid}"
    return token


def personalize_db_url(base_test_url: str, token: str) -> str:
    """`<name>_test` (D-88's base) -> `<name>_<token>_test` for THIS run.

    The `_test` suffix is preserved so D-88's `assert_disposable_test_database`
    still accepts the name; the token goes in front of it. Idempotent-safe on a
    name that does not end in `_test` (it simply appends `_<token>_test`)."""
    parts = urlsplit(base_test_url)
    name = parts.path.lstrip("/")
    stem = name[: -len("_test")] if name.endswith("_test") else name
    return urlunsplit(parts._replace(path=f"/{stem}_{token}_test"))


def redis_url_with_db(base_redis_url: str, index: int) -> str:
    """Same Redis server/auth as `base_redis_url`, logical DB set to `index`."""
    parts = urlsplit(base_redis_url)
    return urlunsplit(parts._replace(path=f"/{index}"))


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


async def claim_redis_db(base_redis_url: str, token: str) -> int:
    """Atomically claim a free Redis logical DB for this run and return its
    index. Uses SET NX on a registry key in DB 0, which no run ever selects, so
    the registry survives every run's FLUSHDB. Raises RunIsolationError if all
    run slots are taken (more than 15 concurrent runs)."""
    registry = Redis.from_url(
        redis_url_with_db(base_redis_url, REDIS_REGISTRY_DB), decode_responses=True
    )
    try:
        for index in REDIS_RUN_DBS:
            claimed = await registry.set(
                _REDIS_SLOT_KEY.format(index=index),
                token,
                nx=True,
                ex=REDIS_SLOT_TTL_SECONDS,
            )
            if claimed:
                return index
        raise RunIsolationError(
            "every Redis test slot (1..15) is claimed by another concurrent run; "
            "wait for one to finish or raise Redis `databases`."
        )
    finally:
        await registry.aclose()


async def release_redis_db(base_redis_url: str, index: int, token: str) -> None:
    """Release this run's Redis slot, but only if the registry key still holds
    OUR token (never free a slot a later run reclaimed after our TTL lapsed).
    Best-effort: the TTL frees it anyway if this never runs."""
    registry = Redis.from_url(
        redis_url_with_db(base_redis_url, REDIS_REGISTRY_DB), decode_responses=True
    )
    try:
        # Compare-and-delete so we never delete a slot another run now owns.
        await registry.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            _REDIS_SLOT_KEY.format(index=index),
            token,
        )
    finally:
        await registry.aclose()


async def drop_database(url: str) -> None:
    """DROP DATABASE the run's own database at session end so runs never
    accumulate. Terminates any lingering backends first (an undisposed pool
    connection would otherwise block the drop). Guarded: refuses any name that
    does not end in `_test`, so it can only ever drop a run database."""
    name = urlsplit(url).path.lstrip("/")
    if not name.endswith("_test"):
        raise RunIsolationError(
            f"refusing to DROP DATABASE {name!r}: name does not end in '_test'"
        )
    admin_url = urlunsplit(urlsplit(url)._replace(path="/postgres"))
    admin = create_async_engine(_sqlalchemy_url(admin_url), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        await admin.dispose()
