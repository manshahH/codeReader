"""Per-run isolation helpers (D-147).

Pure functions are tested without I/O; the Redis claim and the drop guard get
their own checks. The load-bearing negative is that a personalized run-database
name still satisfies D-88's disposability guard -- that is what lets D-147 layer
on top of D-88 without weakening it."""

from __future__ import annotations

import pytest
from _db_guard import assert_disposable_test_database, is_declared_test_database
from _run_isolation import (
    REDIS_REGISTRY_DB,
    RunIsolationError,
    claim_redis_db,
    drop_database,
    isolation_enabled,
    personalize_db_url,
    redis_url_with_db,
    release_redis_db,
    run_token,
)
from redis.asyncio import Redis

_BASE = "postgresql://codereader:codereader@localhost:5433/codereader_test"


# --- run_token -------------------------------------------------------------


def test_run_token_uses_the_xdist_worker_when_present() -> None:
    assert run_token(worker="gw3", pid=999) == "gw3"


def test_run_token_falls_back_to_pid_off_xdist() -> None:
    assert run_token(worker=None, pid=12345) == "p12345"


def test_run_token_sanitizes_to_the_safe_charset() -> None:
    # A hostile/odd worker id can never inject characters into a database name.
    assert run_token(worker="gw-1/../x", pid=1) == "gw1x"


# --- personalize_db_url, and the D-88 tie-in -------------------------------


def test_personalize_inserts_the_token_and_keeps_the_test_suffix() -> None:
    url = personalize_db_url(_BASE, "p777")
    assert url == "postgresql://codereader:codereader@localhost:5433/codereader_p777_test"


def test_personalize_preserves_host_user_password_port() -> None:
    url = personalize_db_url("postgresql://u:pw@example.com:9999/mydb_test", "gw0")
    assert url == "postgresql://u:pw@example.com:9999/mydb_gw0_test"


def test_personalized_name_still_passes_the_d88_guard() -> None:
    """THE tie-in: two concurrent runs get different databases, and BOTH names
    still end in `_test`, so D-88's destructive-fixture guard still accepts them
    with no flag. Isolation is layered on, not carved out."""
    a = personalize_db_url(_BASE, run_token(worker=None, pid=111))
    b = personalize_db_url(_BASE, run_token(worker=None, pid=222))
    assert a != b
    assert is_declared_test_database(a, env={})
    assert is_declared_test_database(b, env={})
    assert_disposable_test_database(a, env={})  # must not raise
    assert_disposable_test_database(b, env={})  # must not raise


# --- redis_url_with_db -----------------------------------------------------


def test_redis_url_with_db_sets_the_logical_db() -> None:
    assert redis_url_with_db("redis://localhost:6380/0", 7) == "redis://localhost:6380/7"


def test_redis_url_with_db_preserves_auth_and_scheme() -> None:
    assert (
        redis_url_with_db("rediss://default:pw@host:6379/0", 3)
        == "rediss://default:pw@host:6379/3"
    )


# --- isolation_enabled -----------------------------------------------------


def test_isolation_is_on_by_default_and_for_non_1_values() -> None:
    assert isolation_enabled(env={}) is True
    assert isolation_enabled(env={"CODEREADER_TEST_NO_ISOLATION": "0"}) is True
    assert isolation_enabled(env={"CODEREADER_TEST_NO_ISOLATION": "false"}) is True


def test_isolation_off_only_on_exactly_1() -> None:
    assert isolation_enabled(env={"CODEREADER_TEST_NO_ISOLATION": "1"}) is False


# --- drop_database guard (negative, no DB needed) --------------------------


@pytest.mark.asyncio
async def test_drop_database_refuses_a_non_test_name() -> None:
    """The guard fires BEFORE any connection, so a bug that pointed teardown at
    a real database can never drop it."""
    with pytest.raises(RunIsolationError, match="_test"):
        await drop_database("postgresql://u:p@localhost:5433/codereader")


# --- Redis claim / release (integration; needs the compose Redis) ----------


@pytest.mark.asyncio
async def test_claim_gives_distinct_slots_and_release_frees_them() -> None:
    from app.config import get_settings

    base = get_settings().REDIS_URL  # rewritten to registry DB 0 internally
    a = await claim_redis_db(base, "tokA-isolation-test")
    b = await claim_redis_db(base, "tokB-isolation-test")
    try:
        assert a != b
        assert a in range(1, 16)
        assert b in range(1, 16)
    finally:
        await release_redis_db(base, a, "tokA-isolation-test")
        await release_redis_db(base, b, "tokB-isolation-test")

    # After release, the registry keys are gone (a later run can reclaim them).
    registry = Redis.from_url(redis_url_with_db(base, REDIS_REGISTRY_DB), decode_responses=True)
    try:
        assert await registry.get(f"codereader:test:redis_slot:{a}") is None
        assert await registry.get(f"codereader:test:redis_slot:{b}") is None
    finally:
        await registry.aclose()


@pytest.mark.asyncio
async def test_release_does_not_free_a_slot_reclaimed_by_another_run() -> None:
    """Compare-and-delete: if our TTL lapsed and another run reclaimed the slot,
    our release must NOT free it out from under them."""
    from app.config import get_settings

    base = get_settings().REDIS_URL
    index = await claim_redis_db(base, "original-owner")
    registry = Redis.from_url(redis_url_with_db(base, REDIS_REGISTRY_DB), decode_responses=True)
    try:
        # Simulate a later run reclaiming the same slot key after a TTL lapse.
        await registry.set(f"codereader:test:redis_slot:{index}", "new-owner")
        await release_redis_db(base, index, "original-owner")  # stale release
        assert await registry.get(f"codereader:test:redis_slot:{index}") == "new-owner"
    finally:
        await registry.delete(f"codereader:test:redis_slot:{index}")
        await registry.aclose()
