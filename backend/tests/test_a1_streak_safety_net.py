"""A1 streak safety net (docs/10; D-116): freeze accrual, freeze consumption,
repair / earn-back, and the ops outage freeze.

Date control follows the house style established in test_m4_streaks.py: seed
`last_active_local_date` relative to the app's OWN `local_date_for` helper and
offset with timedelta, so assertions are about day math and never about a
hardcoded calendar date. There is no time mocking in this repo.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.timezones import local_date_for
from app.main import create_app
from app.models import StreakEvent, User, UserStats
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)

ADMIN_TOKEN = "test-admin-token"


@pytest.fixture(autouse=True)
def admin_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """/admin/* is 404 with no token configured, by design. Configure one."""
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def truncate_after(db_session: AsyncSession):
    """clean_m4_tables truncates BEFORE each test, which is enough for files
    that sort after test_m1_database.py. This module sorts before it and
    commits attempt rows over HTTP, so it must also clean up AFTER itself or
    it leaves rows in the attempts partition that test_m1_database counts.

    NOTE FOR WHOEVER ADDS THE NEXT EARLY-SORTING TEST FILE: this is load-
    bearing on pytest's alphabetical collection order. test_m1_database.py's
    `test_every_schema_table_round_trips` asserts an absolute row count in
    attempts_2026_07 and relies on nothing having committed rows before it.
    Any new file that sorts ahead of it (test_a0_*, test_a1_*, ...) and
    commits over HTTP needs this same after-truncation, or that test starts
    failing with an off-by-N that looks unrelated to the change.
    """
    yield
    await db_session.execute(text("TRUNCATE TABLE users, exercises RESTART IDENTITY CASCADE"))
    await db_session.commit()


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


def _idem() -> str:
    return str(uuid.uuid4())


async def _seed_stats(
    db: AsyncSession,
    user: User,
    *,
    current_streak: int,
    last_active: dt.date | None,
    freezes: int,
) -> UserStats:
    stats = UserStats(
        user_id=user.id,
        current_streak=current_streak,
        longest_streak=current_streak,
        last_active_local_date=last_active,
        streak_freezes=freezes,
    )
    db.add(stats)
    await db.flush()
    await db.commit()
    return stats


async def _events(db: AsyncSession, user: User, event: str | None = None) -> list[StreakEvent]:
    query = select(StreakEvent).where(StreakEvent.user_id == user.id)
    if event is not None:
        query = query.where(StreakEvent.event == event)
    query = query.order_by(StreakEvent.local_date, StreakEvent.id)
    return list((await db.scalars(query)).all())


async def _submit(client: AsyncClient, headers: dict, exercise) -> dict:
    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _submit_today(
    client: AsyncClient,
    db: AsyncSession,
    user: User,
) -> dict:
    exercise = await make_stb_exercise(db, concepts=["mutable_default_args"])
    headers = auth_headers(user)
    assert (await client.get("/v1/session/today", headers=headers)).status_code == 200
    return await _submit(client, headers, exercise)


async def _fresh_stats(db: AsyncSession, user: User) -> UserStats:
    """Re-read past the identity map: the row was mutated by an HTTP handler
    on its own session, so the copy this session seeded is stale.
    """
    return await db.get(UserStats, user.id, populate_existing=True)


# --------------------------------------------------------------------------
# Freeze consumption
# --------------------------------------------------------------------------


async def test_one_missed_day_with_one_freeze_preserves_streak(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    missed = today - dt.timedelta(days=1)
    await _seed_stats(
        db_session,
        user,
        current_streak=5,
        last_active=today - dt.timedelta(days=2),
        freezes=1,
    )

    body = await _submit_today(client, db_session, user)

    assert body["streak"]["event"] == "extended"
    assert body["streak"]["current"] == 6

    stats = await _fresh_stats(db_session, user)
    assert stats.current_streak == 6
    assert stats.streak_freezes == 0

    freezes = await _events(db_session, user, "freeze_used")
    assert len(freezes) == 1
    assert freezes[0].local_date == missed
    assert freezes[0].from_value == freezes[0].to_value == 5

    extended = await _events(db_session, user, "extended")
    assert len(extended) == 1
    assert (extended[0].local_date, extended[0].from_value, extended[0].to_value) == (today, 5, 6)
    assert await _events(db_session, user, "reset") == []


async def test_two_missed_days_with_one_freeze_still_resets(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: a freeze must never PARTIALLY cover a gap."""
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(
        db_session,
        user,
        current_streak=5,
        last_active=today - dt.timedelta(days=3),
        freezes=1,
    )

    body = await _submit_today(client, db_session, user)

    assert body["streak"]["event"] == "reset"
    assert body["streak"]["current"] == 1

    stats = await _fresh_stats(db_session, user)
    assert stats.current_streak == 1
    # Nothing spent: the balance is untouched and no freeze row was written.
    assert stats.streak_freezes == 1
    assert await _events(db_session, user, "freeze_used") == []


# --------------------------------------------------------------------------
# Accrual
# --------------------------------------------------------------------------


async def test_accrual_grants_a_freeze_at_the_milestone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    # Land exactly on the EARN_EVERY milestone with room under the cap.
    await _seed_stats(
        db_session,
        user,
        current_streak=settings.STREAK_FREEZE_EARN_EVERY - 1,
        last_active=today - dt.timedelta(days=1),
        freezes=0,
    )

    body = await _submit_today(client, db_session, user)
    assert body["streak"]["current"] == settings.STREAK_FREEZE_EARN_EVERY

    stats = await _fresh_stats(db_session, user)
    assert stats.streak_freezes == 1

    adjusted = await _events(db_session, user, "adjusted")
    assert len(adjusted) == 1
    assert adjusted[0].local_date == today
    assert "freeze earned" in adjusted[0].note
    assert "streak_freezes 0 -> 1" in adjusted[0].note


async def test_accrual_at_the_cap_writes_no_row_and_does_not_exceed_max(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: hitting the milestone while already at the cap is a no-op."""
    settings = get_settings()
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(
        db_session,
        user,
        current_streak=settings.STREAK_FREEZE_EARN_EVERY - 1,
        last_active=today - dt.timedelta(days=1),
        freezes=settings.STREAK_FREEZE_MAX,
    )

    await _submit_today(client, db_session, user)

    stats = await _fresh_stats(db_session, user)
    assert stats.streak_freezes == settings.STREAK_FREEZE_MAX
    assert await _events(db_session, user, "adjusted") == []


# --------------------------------------------------------------------------
# D-116: outage-covered days are the same currency as spent freezes
# --------------------------------------------------------------------------


async def test_outage_covered_day_survives_a_gap_with_zero_balance(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-116: the outage promise must not be payable only by users holding
    currency. One missed day, already outage-covered, zero balance -> survives
    and spends nothing.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    missed = today - dt.timedelta(days=1)
    await _seed_stats(
        db_session,
        user,
        current_streak=4,
        last_active=today - dt.timedelta(days=2),
        freezes=0,
    )
    response = await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": missed.isoformat()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["users_covered"] == 1

    body = await _submit_today(client, db_session, user)

    assert body["streak"]["event"] == "extended"
    assert body["streak"]["current"] == 5

    stats = await _fresh_stats(db_session, user)
    assert stats.streak_freezes == 0  # nothing spent

    freezes = await _events(db_session, user, "freeze_used")
    assert len(freezes) == 1  # no duplicate written over the outage row
    assert freezes[0].note == "outage"


async def test_outage_day_plus_uncovered_day_needs_balance(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-116: the cap and balance apply to the UNCOVERED remainder only. Two
    missed days, one outage-covered, needs a balance of exactly 1 -- and fails
    at 0.
    """
    settings = get_settings()
    today = local_date_for("UTC")
    outage_day = today - dt.timedelta(days=2)

    poor = await make_user(db_session)
    rich = await make_user(db_session)
    for user in (poor, rich):
        await _seed_stats(
            db_session,
            user,
            current_streak=3,
            last_active=today - dt.timedelta(days=3),
            freezes=0 if user is poor else 1,
        )
    response = await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": outage_day.isoformat()},
    )
    assert response.status_code == 200

    poor_body = await _submit_today(client, db_session, poor)
    rich_body = await _submit_today(client, db_session, rich)

    assert poor_body["streak"]["event"] == "reset"
    assert rich_body["streak"]["event"] == "extended"
    assert rich_body["streak"]["current"] == 4

    assert (await _fresh_stats(db_session, poor)).streak_freezes == 0
    assert (await _fresh_stats(db_session, rich)).streak_freezes == 0

    # The gap spans 2 missed days but only 1 was paid for out of balance: the
    # outage day is free and does not consume the cap.
    rich_freezes = await _events(db_session, rich, "freeze_used")
    assert len(rich_freezes) == 2
    notes = sorted(f.note for f in rich_freezes)
    assert notes[0] == "outage"
    assert notes[1].startswith("streak freeze spent")
    assert [f.local_date for f in rich_freezes] == [outage_day, today - dt.timedelta(days=1)]
    assert settings.STREAK_FREEZE_MAX == 2


# --------------------------------------------------------------------------
# Outage freeze endpoint
# --------------------------------------------------------------------------


async def test_outage_freeze_spends_no_balance_and_mutates_no_streak(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    today = local_date_for("UTC")
    outage_day = today - dt.timedelta(days=1)
    users = [await make_user(db_session) for _ in range(3)]
    for user in users:
        await _seed_stats(
            db_session,
            user,
            current_streak=7,
            last_active=today - dt.timedelta(days=2),
            freezes=2,
        )

    response = await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": outage_day.isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["users_covered"] == 3

    for user in users:
        stats = await _fresh_stats(db_session, user)
        assert stats.streak_freezes == 2  # zero balance spent
        assert stats.current_streak == 7  # no streak manufactured
        rows = await _events(db_session, user, "freeze_used")
        assert len(rows) == 1
        assert rows[0].local_date == outage_day
        assert rows[0].note == "outage"
        assert rows[0].from_value == rows[0].to_value == 7

    # Re-running the same date is a no-op: no duplicate freeze_used rows.
    again = await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": outage_day.isoformat()},
    )
    assert again.json()["users_covered"] == 0


async def test_outage_freeze_does_not_manufacture_a_streak_for_a_long_inactive_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: a user inactive well before the outage day still resets at
    their next submit. One covered day out of many missed is not a rescue.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    outage_day = today - dt.timedelta(days=1)
    await _seed_stats(
        db_session,
        user,
        current_streak=9,
        last_active=today - dt.timedelta(days=30),
        freezes=2,
    )
    await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": outage_day.isoformat()},
    )

    body = await _submit_today(client, db_session, user)

    assert body["streak"]["event"] == "reset"
    assert body["streak"]["current"] == 1
    stats = await _fresh_stats(db_session, user)
    assert stats.streak_freezes == 2  # nothing spent on a hopeless gap


async def test_outage_freeze_requires_the_admin_token(client: AsyncClient) -> None:
    """Negative: the gate rejects a missing and a wrong token."""
    today = local_date_for("UTC").isoformat()
    missing = await client.post("/admin/streak/outage-freeze", json={"local_date": today})
    assert missing.status_code == 403

    wrong = await client.post(
        "/admin/streak/outage-freeze",
        headers={"X-Admin-Token": "not-the-token"},
        json={"local_date": today},
    )
    assert wrong.status_code == 403


# --------------------------------------------------------------------------
# Repair / earn-back
# --------------------------------------------------------------------------


async def _seed_reset(
    db: AsyncSession,
    user: User,
    *,
    lost_value: int,
    local_date: dt.date,
    age_hours: float,
) -> StreakEvent:
    event = StreakEvent(
        user_id=user.id,
        event="reset",
        from_value=lost_value,
        to_value=1,
        local_date=local_date,
        created_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=age_hours),
    )
    db.add(event)
    await db.flush()
    await db.commit()
    return event


async def _seed_extend(
    db: AsyncSession,
    user: User,
    *,
    from_value: int,
    local_date: dt.date,
) -> None:
    db.add(
        StreakEvent(
            user_id=user.id,
            event="extended",
            from_value=from_value,
            to_value=from_value + 1,
            local_date=local_date,
        ),
    )
    await db.flush()
    await db.commit()


async def test_repair_inside_the_window_restores_the_unbroken_counterfactual(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The restored value is "what the streak would read now if the gap had
    never happened": the value lost, PLUS the run built since the reset.

    The reset day is itself an ACTIVE day (a reset row is only written on a
    submit), so its credit lives inside the post-reset run and must not be
    dropped. Reset on day-1 losing 12, active again today, so the post-reset
    run is 2 and the unbroken value is 14 -- not 13.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    reset_date = today - dt.timedelta(days=1)
    await _seed_stats(db_session, user, current_streak=2, last_active=today, freezes=0)
    await _seed_reset(db_session, user, lost_value=12, local_date=reset_date, age_hours=5)
    await _seed_extend(db_session, user, from_value=1, local_date=today)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"current_streak": 14, "repaired": True}

    stats = await _fresh_stats(db_session, user)
    assert stats.current_streak == 14
    assert stats.longest_streak == 14

    repaired = await _events(db_session, user, "repaired")
    assert len(repaired) == 1
    assert repaired[0].local_date == today
    assert (repaired[0].from_value, repaired[0].to_value) == (2, 14)
    assert "[repair:anchor=" in repaired[0].note


async def test_repair_on_the_same_day_as_the_reset_credits_that_day(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The boundary case the day-count formula got wrong: repairing on the
    reset day itself. The user WAS active that day, so 8 lost restores to 9.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    await _seed_reset(db_session, user, lost_value=8, local_date=today, age_hours=1)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert response.json()["current_streak"] == 9


async def test_repair_restore_value_comes_from_the_ledger_not_current_streak(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """current_streak is not trusted: the post-reset run is read from the
    transition rows. Seeded deliberately inconsistent (99) to prove it.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=99, last_active=today, freezes=0)
    await _seed_reset(
        db_session,
        user,
        lost_value=20,
        local_date=today - dt.timedelta(days=2),
        age_hours=10,
    )
    await _seed_extend(db_session, user, from_value=1, local_date=today - dt.timedelta(days=1))
    await _seed_extend(db_session, user, from_value=2, local_date=today)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    # 20 lost + a post-reset run of 3 (reset day, then two extends). Never 99.
    assert response.json()["current_streak"] == 23


async def test_repair_does_not_over_credit_a_missed_day_since_the_reset(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Why the run is read from the ledger and not from elapsed days: the user
    reset 3 days ago but has only built a 2-day run since (one day missed and
    not frozen would have produced a newer reset, so here the run simply lags
    the calendar). A day-count formula would over-credit by 1.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=2, last_active=today, freezes=0)
    await _seed_reset(
        db_session,
        user,
        lost_value=10,
        local_date=today - dt.timedelta(days=3),
        age_hours=20,
    )
    await _seed_extend(db_session, user, from_value=1, local_date=today)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    # 10 + run of 2. The elapsed-days formula would have said 10 + 3 = 13.
    assert response.json()["current_streak"] == 12


async def test_repair_replay_with_the_same_key_is_byte_identical(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    await _seed_reset(db_session, user, lost_value=8, local_date=today, age_hours=1)

    key = _idem()
    headers = {**auth_headers(user), "Idempotency-Key": key}
    first = await client.post("/v1/streak/repair", headers=headers)
    second = await client.post("/v1/streak/repair", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    # The replay must not write a second ledger row.
    assert len(await _events(db_session, user, "repaired")) == 1


async def test_repair_of_an_already_repaired_reset_with_a_new_key_is_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: a reset is repairable at most once. A genuinely new request
    (new key) against an already-repaired reset is a conflict, not a replay.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    await _seed_reset(db_session, user, lost_value=8, local_date=today, age_hours=1)

    first = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert first.status_code == 200

    second = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "not_repairable"
    assert (await _fresh_stats(db_session, user)).current_streak == 9
    assert len(await _events(db_session, user, "repaired")) == 1


async def test_two_concurrent_repairs_with_different_keys_write_exactly_one_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-104's lock class, applied to repair. The idempotency reservation is
    per-KEY, so two concurrent requests with DIFFERENT keys both miss the
    cache and both take their own reservation. Without the per-user advisory
    lock they both read the same unrepaired reset and both write a repaired
    row, restoring the streak twice. asyncio.gather fires two REAL concurrent
    requests; exactly one must win.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    await _seed_reset(db_session, user, lost_value=15, local_date=today, age_hours=2)

    headers = auth_headers(user)
    responses = await asyncio.gather(
        client.post("/v1/streak/repair", headers={**headers, "Idempotency-Key": _idem()}),
        client.post("/v1/streak/repair", headers={**headers, "Idempotency-Key": _idem()}),
    )

    assert sorted(r.status_code for r in responses) == [200, 409]
    repaired = await _events(db_session, user, "repaired")
    assert len(repaired) == 1
    # And the streak was restored exactly once, not twice.
    assert (await _fresh_stats(db_session, user)).current_streak == 16
    assert repaired[0].to_value == 16


async def test_repair_outside_the_window_is_409_and_changes_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: past STREAK_REPAIR_WINDOW_H the offer is gone."""
    settings = get_settings()
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    await _seed_reset(
        db_session,
        user,
        lost_value=30,
        local_date=today - dt.timedelta(days=3),
        age_hours=settings.STREAK_REPAIR_WINDOW_H + 1,
    )

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_repairable"
    assert (await _fresh_stats(db_session, user)).current_streak == 1
    assert await _events(db_session, user, "repaired") == []


async def test_repair_requires_an_idempotency_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: same discipline as POST /attempts."""
    user = await make_user(db_session)
    response = await client.post("/v1/streak/repair", headers=auth_headers(user))
    assert response.status_code == 400


async def test_repair_with_no_reset_at_all_is_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: nothing to restore."""
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=4, last_active=today, freezes=0)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert response.status_code == 409


async def test_a_timezone_recon_repaired_row_does_not_consume_the_repair(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-116(c): jobs/streak_recon.py also writes event='repaired'. An
    unanchored row like that must not disqualify a genuine reset.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=0)
    reset = await _seed_reset(db_session, user, lost_value=6, local_date=today, age_hours=1)
    db_session.add(
        StreakEvent(
            user_id=user.id,
            event="repaired",
            from_value=1,
            to_value=1,
            local_date=today,
            note="timezone change 'UTC' -> 'Pacific/Midway' moved the boundary backward",
        ),
    )
    await db_session.commit()

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert response.status_code == 200
    assert response.json()["current_streak"] == 7
    assert str(reset.id) in (await _events(db_session, user, "repaired"))[-1].note


# --------------------------------------------------------------------------
# Serializer allowlist + invariant 5
# --------------------------------------------------------------------------


async def test_stats_payload_exposes_exactly_the_expected_allowlist(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Invariant 2: the payload is an allowlist. A1 adds repair_available and
    NOTHING else (streak_freezes was already exposed -- D-116(b)).
    """
    expected = {
        "current_streak",
        "longest_streak",
        "streak_freezes",
        "total_attempts",
        "total_correct",
        "accuracy_by_type",
        "last_active_local_date",
        "total_sessions",
        "repair_available",
        "repair_restores_to",
    }

    user = await make_user(db_session)
    empty = await client.get("/v1/me/stats", headers=auth_headers(user))
    assert empty.status_code == 200
    assert set(empty.json()) == expected
    assert empty.json()["repair_available"] is False
    assert empty.json()["repair_restores_to"] is None

    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=1, last_active=today, freezes=1)
    await _seed_reset(db_session, user, lost_value=9, local_date=today, age_hours=2)

    populated = await client.get("/v1/me/stats", headers=auth_headers(user))
    assert set(populated.json()) == expected
    assert populated.json()["repair_available"] is True
    # The N in "Restore your N-day streak": 9 lost + a post-reset run of 1.
    assert populated.json()["repair_restores_to"] == 10
    assert populated.json()["streak_freezes"] == 1


async def test_repair_restores_to_matches_what_the_repair_actually_writes(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The advertised N and the delivered value must not drift apart."""
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(db_session, user, current_streak=2, last_active=today, freezes=0)
    await _seed_reset(
        db_session, user, lost_value=11, local_date=today - dt.timedelta(days=1), age_hours=4
    )
    await _seed_extend(db_session, user, from_value=1, local_date=today)

    advertised = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()
    delivered = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": _idem()},
    )
    assert advertised["repair_restores_to"] == delivered.json()["current_streak"] == 13

    # Once used, the offer is gone from the payload.
    after = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()
    assert after["repair_available"] is False
    assert after["repair_restores_to"] is None


async def test_unique_index_permits_new_kinds_but_blocks_a_duplicate_transition(
    db_session: AsyncSession,
) -> None:
    """Invariant 5 / D-116: uq_streak_events_one_transition_per_day is PARTIAL
    (WHERE event IN ('extended','reset')), so backfilled freeze_used rows never
    collide, while a duplicate transition for one local day is still refused.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)

    # The new kinds coexist freely on one local date, including two
    # freeze_used rows -- which is what makes an ops backfill safe.
    for event in ("freeze_used", "freeze_used", "repaired", "adjusted"):
        db_session.add(
            StreakEvent(
                user_id=user.id,
                event=event,
                from_value=1,
                to_value=1,
                local_date=today,
            ),
        )
    await db_session.flush()

    db_session.add(
        StreakEvent(user_id=user.id, event="extended", from_value=1, to_value=2, local_date=today),
    )
    await db_session.flush()

    db_session.add(
        StreakEvent(user_id=user.id, event="reset", from_value=2, to_value=1, local_date=today),
    )
    with pytest.raises(Exception) as excinfo:
        await db_session.flush()
    assert "uq_streak_events_one_transition_per_day" in str(excinfo.value)
    await db_session.rollback()


async def test_freeze_consumption_writes_no_duplicate_or_extra_transition_rows(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Invariant 5: one covered gap writes exactly one freeze_used per missed
    date and exactly one transition row for today.
    """
    user = await make_user(db_session)
    today = local_date_for(user.timezone)
    await _seed_stats(
        db_session,
        user,
        current_streak=6,
        last_active=today - dt.timedelta(days=3),
        freezes=2,
    )

    # Both exercises must exist BEFORE the session is built, or the second is
    # not in it and POST /attempts rejects it as out-of-session.
    first = await make_stb_exercise(db_session, concepts=["mutable_default_args"])
    second = await make_stb_exercise(db_session, concepts=["closures"])
    headers = auth_headers(user)
    assert (await client.get("/v1/session/today", headers=headers)).status_code == 200

    await _submit(client, headers, first)
    # A second submit the same day must not transition again.
    await _submit(client, headers, second)

    rows = await _events(db_session, user)
    kinds = [row.event for row in rows]
    assert kinds.count("freeze_used") == 2
    assert kinds.count("extended") == 1
    assert kinds.count("reset") == 0
    assert len({row.local_date for row in rows if row.event == "freeze_used"}) == 2

    transitions = [row for row in rows if row.event in ("extended", "reset")]
    assert len(transitions) == 1
    assert transitions[0].local_date == today


async def test_initial_grant_backfills_pre_a1_accounts_idempotently(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-118: pre-A1 rows sit at 0 because they predate STREAK_FREEZE_START."""
    settings = get_settings()
    today = local_date_for("UTC")
    stale = await make_user(db_session)  # pre-A1: balance 0
    partial = await make_user(db_session)  # somehow below the grant
    current = await make_user(db_session)  # already at the cap
    await _seed_stats(db_session, stale, current_streak=4, last_active=today, freezes=0)
    await _seed_stats(db_session, partial, current_streak=1, last_active=today, freezes=1)
    await _seed_stats(
        db_session, current, current_streak=6, last_active=today, freezes=settings.STREAK_FREEZE_MAX
    )

    first = await client.post(
        "/admin/streak/grant-initial-freezes",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": today.isoformat()},
    )
    assert first.status_code == 200, first.text
    assert first.json() == {"granted_to": 2, "balance": settings.STREAK_FREEZE_START}

    for user in (stale, partial, current):
        stats = await _fresh_stats(db_session, user)
        assert stats.streak_freezes == settings.STREAK_FREEZE_START
        assert stats.current_streak in (4, 1, 6)  # streaks never touched

    rows = await _events(db_session, stale, "adjusted")
    assert len(rows) == 1
    assert "[a1:initial-grant]" in rows[0].note
    assert rows[0].from_value == rows[0].to_value == 4
    # Already at the cap: granted nothing, so no row explaining a non-change.
    assert await _events(db_session, current, "adjusted") == []

    # Re-running grants nobody a second time.
    second = await client.post(
        "/admin/streak/grant-initial-freezes",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": today.isoformat()},
    )
    assert second.json()["granted_to"] == 0
    assert len(await _events(db_session, stale, "adjusted")) == 1


async def test_initial_grant_does_not_re_grant_a_user_who_spent_their_freezes(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Negative: the balance test alone is not enough. A granted user who later
    spends down to 0 must NOT be topped back up by a re-run months later. The
    ledger marker is what prevents that.
    """
    today = local_date_for("UTC")
    user = await make_user(db_session)
    await _seed_stats(db_session, user, current_streak=3, last_active=today, freezes=0)
    await client.post(
        "/admin/streak/grant-initial-freezes",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": today.isoformat()},
    )
    # Simulate the user spending the whole balance afterwards.
    stats = await _fresh_stats(db_session, user)
    stats.streak_freezes = 0
    await db_session.commit()

    again = await client.post(
        "/admin/streak/grant-initial-freezes",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"local_date": today.isoformat()},
    )
    assert again.json()["granted_to"] == 0
    assert (await _fresh_stats(db_session, user)).streak_freezes == 0
    assert len(await _events(db_session, user, "adjusted")) == 1


async def test_initial_grant_requires_the_admin_token(client: AsyncClient) -> None:
    """Negative: same gate as every other /admin/* route."""
    today = local_date_for("UTC").isoformat()
    response = await client.post("/admin/streak/grant-initial-freezes", json={"local_date": today})
    assert response.status_code == 403


async def test_new_user_stats_start_with_the_configured_freeze_balance(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    user = await make_user(db_session)
    assert await db_session.get(UserStats, user.id) is None

    await _submit_today(client, db_session, user)

    stats = await _fresh_stats(db_session, user)
    assert stats.streak_freezes == settings.STREAK_FREEZE_START
