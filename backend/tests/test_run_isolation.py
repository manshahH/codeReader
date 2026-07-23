"""Per-run isolation helpers (D-147).

Pure functions are tested without I/O; the Redis claim and the drop guard get
their own checks. The load-bearing negative is that a personalized run-database
name still satisfies D-88's disposability guard -- that is what lets D-147 layer
on top of D-88 without weakening it."""

from __future__ import annotations

import pytest
from _db_guard import assert_disposable_test_database, is_declared_test_database
from _run_isolation import (
    MAX_CONCURRENT_RUNS,
    REDIS_REGISTRY_DB,
    REDIS_RUN_DBS,
    RunIsolationError,
    claim_redis_db,
    drop_database,
    isolation_enabled,
    orphan_candidates,
    personalize_db_url,
    redis_url_with_db,
    release_redis_db,
    run_token,
    token_from_db_name,
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


# --- Redis slot exhaustion (D-147 follow-up item 2) ------------------------


@pytest.mark.asyncio
async def test_claim_fails_loudly_when_every_slot_is_taken() -> None:
    """Negative (house rule): with all MAX_CONCURRENT_RUNS slots occupied, the
    16th claim must raise IMMEDIATELY with a message that names the ceiling and
    says what to do -- never hang, never silently collide onto an occupied slot
    (which would reintroduce the D-147 bug)."""
    from app.config import get_settings

    base = get_settings().REDIS_URL
    registry = Redis.from_url(redis_url_with_db(base, REDIS_REGISTRY_DB), decode_responses=True)
    filled = [f"codereader:test:redis_slot:{i}" for i in REDIS_RUN_DBS]
    try:
        for key in filled:
            await registry.set(key, "occupied-by-a-concurrent-run", ex=60)
        with pytest.raises(RunIsolationError) as caught:
            await claim_redis_db(base, "the-16th-run")
        message = str(caught.value)
        assert str(MAX_CONCURRENT_RUNS) in message  # names the ceiling
        assert "pytest -n" in message  # says what to do
    finally:
        for key in filled:
            await registry.delete(key)
        await registry.aclose()


# --- orphan sweep decision (D-147 follow-up item 3) ------------------------

_STEM = "codereader"


def test_token_from_db_name_recognises_only_per_run_shapes() -> None:
    assert token_from_db_name("codereader_p123_test", stem=_STEM) == "p123"
    assert token_from_db_name("codereader_gw0_test", stem=_STEM) == "gw0"
    # NOT per-run: the base test DB, the dev DB, an unrelated DB.
    assert token_from_db_name("codereader_test", stem=_STEM) is None
    assert token_from_db_name("codereader", stem=_STEM) is None
    assert token_from_db_name("something_else_test", stem=_STEM) is None


def test_sweep_refuses_live_base_dev_and_unrecognised_databases() -> None:
    """THE required negative: the sweep decision must leave alone every database
    it should not drop -- a live run's DB, the base test DB, the dev DB, this
    run's own DB, and anything not shaped like a per-run database -- and select
    ONLY a genuine orphan (per-run shape, token not live)."""
    names = [
        "codereader",  # dev database
        "codereader_test",  # base test database
        "codereader_p111_test",  # LIVE run (token p111 is held)
        "codereader_p999_test",  # this run's own database
        "codereader_pDEAD_test",  # genuine orphan: per-run shape, token not live
        "unrelated_prod_test",  # not our stem
        "customer_db",  # nothing to do with tests
    ]
    candidates = orphan_candidates(
        names,
        stem=_STEM,
        live_tokens={"p111"},
        protect={"codereader", "codereader_test", "codereader_p999_test"},
    )
    assert candidates == ["codereader_pDEAD_test"]
    # Every protected / live / unrecognised name is untouched.
    for safe in (
        "codereader",
        "codereader_test",
        "codereader_p111_test",
        "codereader_p999_test",
        "unrelated_prod_test",
        "customer_db",
    ):
        assert safe not in candidates
