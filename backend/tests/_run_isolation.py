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
# THE CEILING (D-147): DB 0 is the registry, so 1..15 gives 15 usable slots.
# Each run OR each xdist worker claims one, so the hard limit on concurrent test
# processes is 15. `pytest -n 16` alone exhausts it; two runs at `-n 8` reach 16
# claims. Beyond this, claim_redis_db fails immediately and legibly rather than
# colliding (which would reintroduce the D-147 bug) or hanging.
MAX_CONCURRENT_RUNS = len(REDIS_RUN_DBS)  # 15
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
    the registry survives every run's FLUSHDB. Raises RunIsolationError, loudly
    and immediately, once all MAX_CONCURRENT_RUNS slots are taken -- never
    collides onto an occupied slot (that would reintroduce the D-147 bug) and
    never hangs."""
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
            f"all {MAX_CONCURRENT_RUNS} Redis test slots (logical DBs 1..15) are in "
            f"use, so this is the 16th+ concurrent test process. That is the "
            f"per-run-isolation ceiling (D-147): at most {MAX_CONCURRENT_RUNS} test "
            f"runs or `pytest -n` workers at once. WHAT TO DO: use `pytest -n "
            f"{MAX_CONCURRENT_RUNS}` or fewer, wait for another run to finish, or "
            f"if a crashed run stranded slots they self-free after "
            f"{REDIS_SLOT_TTL_SECONDS // 3600}h (or clear "
            f"'codereader:test:redis_slot:*' in Redis DB {REDIS_REGISTRY_DB})."
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


async def live_run_tokens(base_redis_url: str) -> set[str]:
    """The tokens of every run that currently holds a Redis slot -- i.e. every
    LIVE run. A slot's value IS the run's token (claim_redis_db stores it), and
    the slot self-frees on the TTL, so a crashed run drops out of this set once
    its TTL lapses. This is the liveness authority the orphan sweep trusts: a
    per-run database whose token is in here belongs to a running suite."""
    registry = Redis.from_url(
        redis_url_with_db(base_redis_url, REDIS_REGISTRY_DB), decode_responses=True
    )
    tokens: set[str] = set()
    try:
        for index in REDIS_RUN_DBS:
            value = await registry.get(_REDIS_SLOT_KEY.format(index=index))
            if value:
                tokens.add(value)
    finally:
        await registry.aclose()
    return tokens


def token_from_db_name(name: str, *, stem: str) -> str | None:
    """Extract `<token>` from a per-run database name `<stem>_<token>_test`, or
    None if `name` is not shaped like one (so the base `<stem>_test`, the dev
    database, and anything else are never mistaken for a run database)."""
    prefix, suffix = f"{stem}_", "_test"
    if not (name.startswith(prefix) and name.endswith(suffix)):
        return None
    token = name[len(prefix) : -len(suffix)]
    return token or None


def orphan_candidates(
    all_db_names: list[str],
    *,
    stem: str,
    live_tokens: set[str],
    protect: set[str],
) -> list[str]:
    """Pure decision: which databases are safe-to-consider orphans. A name is a
    candidate ONLY if it is shaped like a per-run database (`<stem>_<token>_test`),
    its token is NOT held by a live run, and it is not explicitly protected (the
    base test database, the dev database, this run's own database). Everything
    else -- unrecognised names, live-token names, protected names -- is left
    alone. The I/O caller adds a second, independent guard (no active
    connections) before actually dropping."""
    candidates: list[str] = []
    for name in all_db_names:
        if name in protect:
            continue
        token = token_from_db_name(name, stem=stem)
        if token is None or token in live_tokens:
            continue
        candidates.append(name)
    return candidates


async def sweep_orphan_databases(
    admin_target_url: str,
    base_redis_url: str,
    *,
    stem: str,
    protect: set[str],
) -> list[str]:
    """Drop per-run databases left behind by runs that crashed before teardown
    (whose Redis slot has since expired). Safe by construction: it only drops a
    name that is (1) shaped like a per-run database, (2) whose token no live run
    holds, (3) not protected, AND (4) has ZERO active backend connections at the
    moment of the drop. If unsure -- any active connection, any live token -- it
    leaves the database alone. Returns the names actually dropped."""
    tokens = await live_run_tokens(base_redis_url)
    admin_url = urlunsplit(urlsplit(admin_target_url)._replace(path="/postgres"))
    admin = create_async_engine(_sqlalchemy_url(admin_url), isolation_level="AUTOCOMMIT")
    dropped: list[str] = []
    try:
        async with admin.connect() as conn:
            names = list(
                await conn.scalars(
                    text("SELECT datname FROM pg_database WHERE datname LIKE :pat"),
                    {"pat": f"{stem}\\_%\\_test"},
                )
            )
            for name in orphan_candidates(names, stem=stem, live_tokens=tokens, protect=protect):
                active = await conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = :name"
                    ),
                    {"name": name},
                )
                if active:  # someone is connected -- leave it, we are unsure
                    continue
                if not name.endswith("_test"):  # the same guard drop_database uses
                    continue
                try:
                    await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
                    dropped.append(name)
                except Exception:  # noqa: BLE001 -- a concurrent sweep won the race, or
                    # a connection appeared between the check and the drop. Either way
                    # leave it: another run will sweep it, or its owner still holds it.
                    continue
    finally:
        await admin.dispose()
    return dropped


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
