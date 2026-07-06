from __future__ import annotations

import datetime as dt
import decimal
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exercises.service import ExerciseImmutableError, update_exercise_fields
from app.jobs.partitions import count_attempts_default_rows, ensure_next_month_attempts_partition
from app.models import (
    Attempt,
    AuthIdentity,
    DailySession,
    Dispute,
    Exercise,
    ExerciseStat,
    RefreshToken,
    StreakEvent,
    User,
    UserConceptState,
    UserStats,
)

UTC = dt.UTC


async def make_user(session: AsyncSession, username: str = "reader") -> User:
    user = User(username=f"{username}-{uuid.uuid4().hex[:8]}")
    session.add(user)
    await session.flush()
    return user


async def make_exercise(
    session: AsyncSession,
    *,
    status: str = "draft",
    exercise_type: str = "trace",
) -> Exercise:
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type=exercise_type,
        grading_mode="deterministic",
        difficulty_authored=5,
        concepts=["control_flow"],
        tags=[],
        status=status,
        source={"origin": "test"},
        payload={"code": "print(1)"},
        grading={"answer": "1"},
        explanation={"text": "prints one"},
    )
    session.add(exercise)
    await session.flush()
    return exercise


async def make_attempt(
    session: AsyncSession,
    user: User,
    exercise: Exercise,
    *,
    created_at: dt.datetime | None = None,
    score: decimal.Decimal = decimal.Decimal("1.000"),
) -> Attempt:
    attempt = Attempt(
        user_id=user.id,
        exercise_id=exercise.id,
        exercise_version=exercise.version,
        session_date=dt.date(2026, 7, 6),
        answer={"choice": "1"},
        grading_mode="deterministic",
        status="graded",
        is_correct=True,
        score=score,
        created_at=created_at or dt.datetime(2026, 7, 15, 12, tzinfo=UTC),
        graded_at=created_at or dt.datetime(2026, 7, 15, 12, tzinfo=UTC),
    )
    session.add(attempt)
    await session.flush()
    return attempt


@pytest.mark.asyncio
async def test_every_schema_table_round_trips(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    exercise = await make_exercise(db_session, status="live")

    identity = AuthIdentity(
        user_id=user.id,
        provider="github",
        provider_user_id=uuid.uuid4().hex,
        provider_login="reader",
        access_token_enc=b"sealed",
        token_scopes="read:user",
    )
    refresh_token = RefreshToken(
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash=uuid.uuid4().bytes,
        expires_at=dt.datetime(2026, 8, 1, tzinfo=UTC),
    )
    daily_session = DailySession(
        user_id=user.id,
        session_date=dt.date(2026, 7, 6),
        exercise_list=[{"exercise_id": str(exercise.id), "version": 1, "slot": 1}],
    )
    user_stats = UserStats(user_id=user.id)
    streak_event = StreakEvent(
        user_id=user.id,
        event="extended",
        from_value=0,
        to_value=1,
        local_date=dt.date(2026, 7, 6),
    )
    concept_state = UserConceptState(user_id=user.id, concept="control_flow")
    exercise_stat = ExerciseStat(exercise_id=exercise.id, exercise_version=exercise.version)
    db_session.add_all(
        [
            identity,
            refresh_token,
            daily_session,
            user_stats,
            streak_event,
            concept_state,
            exercise_stat,
        ],
    )
    await db_session.flush()

    july_attempt = await make_attempt(db_session, user, exercise)
    default_attempt = await make_attempt(
        db_session,
        user,
        exercise,
        created_at=dt.datetime(2035, 1, 15, 12, tzinfo=UTC),
    )
    dispute = Dispute(
        exercise_id=exercise.id,
        exercise_version=exercise.version,
        user_id=user.id,
        attempt_id=july_attempt.id,
        reason="other",
        body="test dispute",
    )
    db_session.add(dispute)
    await db_session.flush()

    assert await db_session.get(User, user.id) is not None
    assert await db_session.get(AuthIdentity, identity.id) is not None
    assert await db_session.get(RefreshToken, refresh_token.id) is not None
    assert await db_session.get(Exercise, (exercise.id, exercise.version)) is not None
    assert await db_session.get(DailySession, (user.id, dt.date(2026, 7, 6))) is not None
    assert await db_session.get(Attempt, (july_attempt.id, july_attempt.created_at)) is not None
    assert await db_session.get(UserStats, user.id) is not None
    assert await db_session.get(StreakEvent, streak_event.id) is not None
    assert await db_session.get(UserConceptState, (user.id, "control_flow")) is not None
    assert await db_session.get(ExerciseStat, (exercise.id, exercise.version)) is not None
    assert await db_session.get(Dispute, dispute.id) is not None

    assert await db_session.scalar(text("SELECT count(*) FROM attempts_2026_07")) == 1
    assert await db_session.scalar(text("SELECT count(*) FROM attempts_default")) == 1
    assert default_attempt.id is not None


@pytest.mark.asyncio
async def test_exercises_type_check_rejects_bad_value(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await make_exercise(db_session, exercise_type="not_a_type")


@pytest.mark.asyncio
async def test_attempt_score_check_rejects_out_of_range(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    exercise = await make_exercise(db_session)

    with pytest.raises(IntegrityError):
        await make_attempt(db_session, user, exercise, score=decimal.Decimal("1.500"))


@pytest.mark.asyncio
async def test_user_concept_state_mastery_check_rejects_out_of_range(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    db_session.add(
        UserConceptState(
            user_id=user.id,
            concept="control_flow",
            mastery=decimal.Decimal("-0.001"),
        ),
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_attempt_composite_fk_rejects_missing_exercise_version(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    missing_exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="trace",
        grading_mode="deterministic",
        difficulty_authored=5,
        concepts=["control_flow"],
        tags=[],
        source={"origin": "test"},
        payload={"code": "print(1)"},
        grading={"answer": "1"},
        explanation={"text": "prints one"},
    )

    attempt = Attempt(
        user_id=user.id,
        exercise_id=missing_exercise.id,
        exercise_version=missing_exercise.version,
        session_date=dt.date(2026, 7, 6),
        answer={"choice": "1"},
        grading_mode="deterministic",
        status="graded",
        is_correct=True,
        score=decimal.Decimal("1.000"),
        created_at=dt.datetime(2026, 7, 15, 12, tzinfo=UTC),
    )
    db_session.add(attempt)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_next_month_partition_routing(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    exercise = await make_exercise(db_session)
    partition_name = await ensure_next_month_attempts_partition(db_session, dt.date(2026, 7, 6))

    await make_attempt(
        db_session,
        user,
        exercise,
        created_at=dt.datetime(2026, 8, 15, 12, tzinfo=UTC),
    )

    routed_count = await db_session.scalar(text(f"SELECT count(*) FROM {partition_name}"))
    assert partition_name == "attempts_2026_08"
    assert routed_count == 1
    assert await count_attempts_default_rows(db_session) == 0


@pytest.mark.asyncio
async def test_live_exercise_update_guard_blocks_service_update(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, status="live")

    with pytest.raises(ExerciseImmutableError):
        await update_exercise_fields(
            db_session,
            exercise.id,
            exercise.version,
            {"difficulty_authored": 7},
        )

    await db_session.refresh(exercise)
    assert exercise.difficulty_authored == 5


@pytest.mark.asyncio
async def test_schema_uses_text_checks_and_gen_random_uuid_v4(db_session: AsyncSession) -> None:
    enum_count = await db_session.scalar(text("SELECT count(*) FROM pg_type WHERE typtype = 'e'"))
    user_id_default = await db_session.scalar(
        text(
            """
            SELECT pg_get_expr(adbin, adrelid)
            FROM pg_attrdef
            WHERE adrelid = 'users'::regclass
              AND adnum = (
                SELECT attnum
                FROM pg_attribute
                WHERE attrelid = 'users'::regclass
                  AND attname = 'id'
              )
            """,
        ),
    )
    exercise_type_check = await db_session.scalar(
        text(
            """
            SELECT count(*)
            FROM pg_constraint
            WHERE conrelid = 'exercises'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%spot_the_bug%'
            """,
        ),
    )

    assert enum_count == 0
    assert user_id_default == "gen_random_uuid()"
    assert exercise_type_check >= 1
