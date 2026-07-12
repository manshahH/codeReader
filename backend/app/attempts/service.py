"""POST /attempts orchestration.

Write order inside the transaction (see the M4 report for the full
rationale): insert Attempt -> upsert UserConceptState per concept (spaced
repetition) -> upsert UserStats + streak transition (StreakEvent row only on
a transition) -> flip DailySession.completed_at if this was the last
exercise -> commit. The JSONL event append happens strictly AFTER commit and
is best-effort (app.core.events.append_attempt_event never raises).

Streak credit attaches to SUBMITTING the first attempt of the local day, not
to is_correct or to grading resolving (D-19): `_update_streak_and_attempt_count`
records the streak transition and total_attempts unconditionally, before the
grade is known. `update_concept_state`/`update_correctness_stats` (the
correctness-dependent updates) only run once is_correct is actually known --
immediately for deterministic types and successfully-graded-inline
summarize, or later via jobs/grading_retry.py for a summarize attempt that
first lands `grading_pending` (D-38).
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from dataclasses import dataclass
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.grading import (
    DETERMINISTIC_TYPES,
    AnswerShapeError,
    UnsupportedExerciseTypeError,
    build_reveal,
    grade_deterministic,
    is_skip_answer,
    validate_answer_shape,
)
from app.attempts.rubric import (
    RubricGradingInvalidResponse,
    RubricGradingTimeout,
    build_summarize_reveal,
    grade_rubric,
    validate_summarize_answer_shape,
)
from app.config import get_settings
from app.core import grader_health
from app.core.accuracy import bump as bump_accuracy
from app.core.errors import ApiError
from app.core.events import append_attempt_event
from app.core.idempotency import (
    acquire_reservation,
    get_cached,
    release_reservation,
    request_hash,
    wait_for_cached,
)
from app.core.idempotency import store as store_idempotency
from app.core.ratelimit import check_token_bucket
from app.models import (
    Attempt,
    DailySession,
    Exercise,
    ExerciseStat,
    StreakEvent,
    User,
    UserConceptState,
    UserStats,
)
from app.schemas.attempts import (
    AttemptRequest,
    AttemptResponse,
    GraderOutput,
    PercentileInfo,
    SessionProgress,
    StreakInfo,
)
from app.sessions.service import get_today_slots, slots_from_dicts

IDEMPOTENCY_NAMESPACE = "attempts"
PERCENTILE_MIN_N = 30

CONCEPT_INTERVAL_WRONG_DAYS = 2
CONCEPT_INTERVAL_RIGHT_DAYS = 7
CONCEPT_INTERVAL_RIGHT_AGAIN_DAYS = 21
# D-93: shorter than WRONG_DAYS on purpose. An honest "I don't know" is a
# CLEANER signal than a wrong guess -- no misconception was planted, just an
# absence of evidence -- so it is worth re-testing sooner, not later.
CONCEPT_INTERVAL_SKIPPED_DAYS = 1

_MASTERY_DECAY = decimal.Decimal("0.7")
_MASTERY_GAIN = decimal.Decimal("0.3")
# A wrong answer pulls mastery toward 0 (mastery*0.7 + 0*0.3): it asserts a
# misconception. A skip asserts nothing directional -- it should decay
# mastery LESS than a wrong answer, reflecting only time-since-practice, with
# no target term pulling it anywhere. 0.85 > 0.7 (less shrinkage than WRONG).
_MASTERY_DECAY_SKIPPED = decimal.Decimal("0.85")
_MASTERY_QUANT = decimal.Decimal("0.001")

ConceptOutcome = Literal["correct", "incorrect", "skipped"]


@dataclass(frozen=True)
class AttemptOutcome:
    status_code: int
    body: dict
    is_replay: bool
    rate_limit_headers: dict[str, str] | None


async def _read_percentile(
    db: AsyncSession,
    exercise_id: uuid.UUID,
    exercise_version: int,
) -> PercentileInfo | None:
    stat = await db.get(ExerciseStat, (exercise_id, exercise_version))
    if stat is None or stat.attempts_count < PERCENTILE_MIN_N:
        return None
    return PercentileInfo(
        solve_rate=float(stat.solve_rate) if stat.solve_rate is not None else 0.0,
        n=stat.attempts_count,
    )


async def update_concept_state(
    db: AsyncSession,
    user: User,
    concepts: list[str],
    outcome: ConceptOutcome,
    now: dt.datetime,
) -> None:
    """D-93: a third branch for an honest skip, alongside correct/incorrect.
    A skip increments `declined`, never `attempts` -- it must not inflate the
    accuracy denominator (attempts/correct) that per-concept accuracy and
    exercise_stats-style ratios are built from. It schedules sooner than a
    wrong answer (CONCEPT_INTERVAL_SKIPPED_DAYS < WRONG_DAYS) and decays
    mastery less (no directional target term, just a gentler multiplier)."""
    for concept in concepts:
        row = await db.get(UserConceptState, (user.id, concept))
        if row is None:
            row = UserConceptState(
                user_id=user.id,
                concept=concept,
                mastery=decimal.Decimal("0"),
                attempts=0,
                correct=0,
                declined=0,
            )
            db.add(row)
            await db.flush()

        if outcome == "skipped":
            row.declined += 1
            row.mastery = (row.mastery * _MASTERY_DECAY_SKIPPED).quantize(_MASTERY_QUANT)
            row.next_review_at = now + dt.timedelta(days=CONCEPT_INTERVAL_SKIPPED_DAYS)
        else:
            is_correct = outcome == "correct"
            already_correct_before = row.correct > 0

            row.attempts += 1
            if is_correct:
                row.correct += 1

            target = decimal.Decimal("1") if is_correct else decimal.Decimal("0")
            updated_mastery = row.mastery * _MASTERY_DECAY + target * _MASTERY_GAIN
            row.mastery = updated_mastery.quantize(_MASTERY_QUANT)

            # D-36: "right again" = correct at least once before this attempt,
            # not strictly consecutive-correct (no schema column tracks that).
            if not is_correct:
                interval_days = CONCEPT_INTERVAL_WRONG_DAYS
            elif already_correct_before:
                interval_days = CONCEPT_INTERVAL_RIGHT_AGAIN_DAYS
            else:
                interval_days = CONCEPT_INTERVAL_RIGHT_DAYS
            row.next_review_at = now + dt.timedelta(days=interval_days)

        row.last_seen_at = now

    await db.flush()


async def update_correctness_stats(
    db: AsyncSession,
    user: User,
    exercise_type: str,
    is_correct: bool,
) -> None:
    """Bumps total_correct/accuracy_by_type. Only called once a grade is
    actually known -- i.e. never at submit time for a summarize attempt that
    lands grading_pending (D-19/D-38); jobs/grading_retry.py calls this once
    it resolves such an attempt. Assumes total_attempts was already recorded
    by _update_streak_and_attempt_count at submit time.
    """
    stats = await db.get(UserStats, user.id)
    if stats is None:
        stats = UserStats(user_id=user.id)
        db.add(stats)
        await db.flush()

    if is_correct:
        stats.total_correct += 1
    stats.accuracy_by_type = bump_accuracy(stats.accuracy_by_type, exercise_type, is_correct)
    await db.flush()


async def _update_streak_and_attempt_count(
    db: AsyncSession,
    user: User,
    today: dt.date,
) -> StreakInfo | None:
    """Streak transition + total_attempts, independent of correctness
    (D-19): a submission counts toward the streak/day whether or not -- or
    even whether yet -- it's known to be correct.
    """
    stats = await db.get(UserStats, user.id)
    if stats is None:
        stats = UserStats(user_id=user.id)
        db.add(stats)
        await db.flush()

    stats.total_attempts += 1

    if stats.last_active_local_date == today:
        # Already counted today: no streak transition, no StreakEvent row.
        await db.flush()
        return None

    from_value = stats.current_streak
    consecutive = stats.last_active_local_date == today - dt.timedelta(days=1)
    if stats.last_active_local_date is None or consecutive:
        to_value = from_value + 1
        event = "extended"
    else:
        to_value = 1
        event = "reset"

    stats.current_streak = to_value
    stats.longest_streak = max(stats.longest_streak, to_value)
    stats.last_active_local_date = today

    db.add(
        StreakEvent(
            user_id=user.id,
            event=event,
            from_value=from_value,
            to_value=to_value,
            local_date=today,
        ),
    )
    await db.flush()
    return StreakInfo(current=to_value, event=event)


async def _remaining_count(
    db: AsyncSession,
    user: User,
    today: dt.date,
    slots: list,
) -> int:
    if not slots:
        return 0
    attempted_rows = await db.execute(
        select(Attempt.exercise_id).where(
            Attempt.user_id == user.id,
            Attempt.session_date == today,
        ),
    )
    attempted_ids = {row[0] for row in attempted_rows.all()}
    done = sum(1 for s in slots if s.exercise_id in attempted_ids)
    return max(0, len(slots) - done)


async def submit_attempt(
    db: AsyncSession,
    redis: Redis,
    user: User,
    *,
    idempotency_key: str,
    payload: AttemptRequest,
) -> AttemptOutcome:
    body_dict = payload.model_dump(mode="json")
    req_hash = request_hash(body_dict)

    # Rate limit is checked BEFORE the idempotency lookup so every response
    # -- including a replay -- carries X-RateLimit-* headers (docs/05
    # section 1: "Headers on every response"); checking only on a fresh
    # submit left replays with no headers at all.
    settings = get_settings()
    rl = await check_token_bucket(
        redis,
        key=f"rl:attempts:{user.id}",
        limit=settings.RATE_LIMIT_ATTEMPTS_PER_MINUTE,
    )
    if not rl.allowed:
        raise ApiError(429, "rate_limited", "Too many requests.", headers=rl.headers)

    cached = await get_cached(
        redis,
        namespace=IDEMPOTENCY_NAMESPACE,
        idempotency_key=idempotency_key,
    )
    if cached is not None:
        if cached.request_hash != req_hash:
            raise ApiError(
                409,
                "idempotency_conflict",
                "This Idempotency-Key was already used with a different request body.",
            )
        return AttemptOutcome(
            status_code=cached.status_code,
            body=cached.body,
            is_replay=True,
            rate_limit_headers=rl.headers,
        )

    # Concurrency fix (M7 audit): a network retry racing the still-in-flight
    # original carries the SAME Idempotency-Key. Without a reservation here,
    # both requests miss the `cached` lookup above (neither has stored a
    # result yet) and would run independently -- a duplicate attempt row, a
    # duplicate stats update. Whoever wins this SET NX proceeds normally;
    # the loser waits for the winner's result and replays it
    # byte-identically instead of racing it through to a DB-level conflict.
    reserved = await acquire_reservation(
        redis,
        namespace=IDEMPOTENCY_NAMESPACE,
        idempotency_key=idempotency_key,
    )
    if not reserved:
        record = await wait_for_cached(
            redis,
            namespace=IDEMPOTENCY_NAMESPACE,
            idempotency_key=idempotency_key,
            timeout_seconds=settings.GRADER_TIMEOUT_S + 3,
        )
        if record is not None:
            if record.request_hash != req_hash:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "This Idempotency-Key was already used with a different request body.",
                )
            return AttemptOutcome(
                status_code=record.status_code,
                body=record.body,
                is_replay=True,
                rate_limit_headers=rl.headers,
            )
        # The in-flight winner never finished within the wait budget (a
        # crashed process, an abnormally slow request): fall through and
        # process normally. The DB advisory lock below is the real
        # backstop against a duplicate attempts row regardless of what
        # happens at this Redis reservation layer.

    try:
        return await _build_and_store_attempt(
            db,
            redis,
            user,
            idempotency_key=idempotency_key,
            payload=payload,
            req_hash=req_hash,
            rl_headers=rl.headers,
        )
    finally:
        if reserved:
            await release_reservation(
                redis,
                namespace=IDEMPOTENCY_NAMESPACE,
                idempotency_key=idempotency_key,
            )


async def _build_and_store_attempt(
    db: AsyncSession,
    redis: Redis,
    user: User,
    *,
    idempotency_key: str,
    payload: AttemptRequest,
    req_hash: str,
    rl_headers: dict[str, str],
) -> AttemptOutcome:
    today, slots = await get_today_slots(db, redis, user)
    slot = next(
        (
            s
            for s in slots
            if s.exercise_id == payload.exercise_id and s.version == payload.exercise_version
        ),
        None,
    )
    if slot is None:
        raise ApiError(
            403,
            "exercise_not_in_session",
            "This exercise is not part of your current session.",
        )

    exercise = await db.scalar(
        select(Exercise).where(
            Exercise.id == payload.exercise_id,
            Exercise.version == payload.exercise_version,
        ),
    )
    if exercise is None:
        raise ApiError(404, "not_found", "Exercise not found.")

    answer_text: str | None = None
    if exercise.type in DETERMINISTIC_TYPES:
        try:
            validate_answer_shape(exercise.type, payload.answer)
        except (AnswerShapeError, UnsupportedExerciseTypeError) as exc:
            raise ApiError(422, "answer_shape_mismatch", str(exc)) from exc
    elif exercise.type == "summarize":
        try:
            answer_text = validate_summarize_answer_shape(exercise, payload.answer)
        except AnswerShapeError as exc:
            raise ApiError(422, "answer_shape_mismatch", str(exc)) from exc
    else:
        raise ApiError(
            422,
            "answer_shape_mismatch",
            f"no grading path for exercise type {exercise.type!r}",
        )

    # Concurrency fix (M7 audit, widened for H1/D-104): the already-attempted
    # check below is a plain SELECT with no row lock, and the partitioned
    # attempts table can't carry a DB unique constraint (D-7). Without
    # serialization here, concurrent submits by the same user on the same day
    # can both pass this check and both run the per-USER stats read-modify-
    # write below.
    #
    # The lock is keyed on (user_id, session_date) -- NOT (user_id,
    # exercise_id, session_date). The stats/streak update
    # (_update_streak_and_attempt_count) mutates per-USER rows (user_stats)
    # and writes at most one streak_events row per user per local day, so the
    # race that corrupts them is ANY two same-day submits by the user, not
    # only two of the SAME exercise. A per-exercise lock left the cross-
    # exercise first-of-day race wide open: two tabs answering two DIFFERENT
    # exercises both saw last_active != today, both took the "extended"
    # branch, and wrote TWO streak_events rows (invariant 5) plus a lost
    # total_attempts increment. A per-(user, day) lock serializes every
    # same-day submit, so the second observes the first's committed stats
    # (last_active == today -> no second transition) and its committed
    # attempt (for the same-exercise case -> correct 409). Still transaction-
    # scoped, released at commit/rollback, no explicit unlock. The partial
    # unique index on streak_events(user_id, local_date) for extended/reset
    # (migration 0007, D-104) is the un-raceable DB backstop underneath this.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_a), hashtext(:lock_b))"),
        {
            "lock_a": str(user.id),
            "lock_b": today.isoformat(),
        },
    )

    already = await db.scalar(
        select(Attempt.id).where(
            Attempt.user_id == user.id,
            Attempt.exercise_id == exercise.id,
            Attempt.session_date == today,
        ),
    )
    if already is not None:
        raise ApiError(409, "already_attempted", "You already submitted this exercise today.")

    now = dt.datetime.now(dt.UTC)

    if exercise.type in DETERMINISTIC_TYPES:
        grading_mode = "deterministic"
        is_skip = is_skip_answer(payload.answer)
        is_correct: bool | None = grade_deterministic(exercise, payload.answer)
        status = "skipped" if is_skip else "graded"
        score: float | None = None
        grader_output_dict: dict | None = None
        # A skip still teaches (docs/08: the app respects, it never scolds) --
        # the same reveal a real answer would get, just no correct/incorrect
        # verdict to show alongside it.
        reveal = build_reveal(exercise)
        graded_at: dt.datetime | None = now
    else:
        grading_mode = "rubric"
        is_skip = False
        is_correct = None
        score = None
        grader_output_dict = None
        reveal = None
        graded_at = None
        try:
            result = await grade_rubric(exercise, answer_text)
        except RubricGradingInvalidResponse:
            # Terminal: the retry job only ever scans status='grading_pending',
            # so a grading_failed row is never re-picked (D-38 confirmation 1).
            status = "grading_failed"
        except RubricGradingTimeout:
            status = "grading_pending"
        else:
            status = "graded"
            is_correct = result.is_correct
            score = result.score
            grader_output_dict = {
                "rubric_hits": result.rubric_hits,
                "rubric_misses": result.rubric_misses,
                "reference_answer": result.reference_answer,
            }
            reveal = build_summarize_reveal(exercise)
            graded_at = now
        if status == "graded":
            await grader_health.mark_success(redis)
        else:
            await grader_health.mark_failure(redis)

    attempt = Attempt(
        user_id=user.id,
        exercise_id=exercise.id,
        exercise_version=exercise.version,
        session_date=today,
        answer=payload.answer,
        grading_mode=grading_mode,
        status=status,
        is_correct=is_correct,
        score=decimal.Decimal(str(score)) if score is not None else None,
        grader_output=grader_output_dict,
        time_taken_ms=payload.time_taken_ms,
        created_at=now,
        graded_at=graded_at,
    )
    db.add(attempt)
    await db.flush()

    # D-19/D-38/D-93: total_attempts + streak count on every submission
    # (including a skip -- it's still a submission). Concept mastery updates
    # on a skip too (the third "skipped" branch), but correctness stats
    # (total_correct/accuracy_by_type) only ever apply to a real verdict --
    # a skip must not inflate that denominator either. A pending/failed
    # summarize gets neither here; jobs/grading_retry.py applies both once
    # (if) it resolves to graded.
    if is_skip:
        await update_concept_state(db, user, list(exercise.concepts), "skipped", now)
    elif is_correct is not None:
        outcome: ConceptOutcome = "correct" if is_correct else "incorrect"
        await update_concept_state(db, user, list(exercise.concepts), outcome, now)
        await update_correctness_stats(db, user, exercise.type, is_correct)

    streak_info = await _update_streak_and_attempt_count(db, user, today)

    remaining = await _remaining_count(db, user, today, slots)
    first_completed_session = False
    if remaining == 0:
        daily_session_row = await db.get(DailySession, (user.id, today))
        if daily_session_row is not None and daily_session_row.completed_at is None:
            daily_session_row.completed_at = now
            # D-93b: count AFTER setting completed_at above (same transaction,
            # so the just-completed row is already included) -- 1 means this
            # attempt is the first daily session this user has ever finished.
            completed_count = await db.scalar(
                select(func.count())
                .select_from(DailySession)
                .where(
                    DailySession.user_id == user.id,
                    DailySession.completed_at.isnot(None),
                ),
            )
            first_completed_session = completed_count == 1

    await db.commit()

    append_attempt_event(
        {
            "event": "attempt_graded",
            "attempt_id": attempt.id,
            "user_id": str(user.id),
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "exercise_type": exercise.type,
            "status": status,
            "is_correct": is_correct,
            "session_date": today.isoformat(),
            "created_at": now.isoformat(),
        },
    )

    percentile = await _read_percentile(db, exercise.id, exercise.version)

    response_body = AttemptResponse(
        attempt_id=attempt.id,
        status=status,
        is_correct=is_correct,
        reveal=reveal,
        score=score,
        grader_output=GraderOutput(**grader_output_dict) if grader_output_dict else None,
        percentile=percentile,
        streak=streak_info,
        session=SessionProgress(
            completed=remaining == 0,
            remaining=remaining,
            first_completed_session=first_completed_session,
        ),
    ).model_dump(mode="json")

    await store_idempotency(
        redis,
        namespace=IDEMPOTENCY_NAMESPACE,
        idempotency_key=idempotency_key,
        request_hash=req_hash,
        status_code=200,
        body=response_body,
    )

    return AttemptOutcome(
        status_code=200,
        body=response_body,
        is_replay=False,
        rate_limit_headers=rl_headers,
    )


async def get_attempt(db: AsyncSession, user: User, attempt_id: int) -> dict | None:
    attempt = await db.scalar(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id),
    )
    if attempt is None:
        return None
    exercise = await db.scalar(
        select(Exercise).where(
            Exercise.id == attempt.exercise_id,
            Exercise.version == attempt.exercise_version,
        ),
    )
    if exercise is None:
        return None

    daily_session_row = await db.get(DailySession, (user.id, attempt.session_date))
    slots = slots_from_dicts(daily_session_row.exercise_list) if daily_session_row else []
    remaining = await _remaining_count(db, user, attempt.session_date, slots)
    if daily_session_row is not None:
        completed = daily_session_row.completed_at is not None
    else:
        completed = remaining == 0

    # grading_pending/grading_failed: no reveal yet. grading_failed is
    # terminal (never retried) and reported gracefully here -- never a 500
    # or a hang -- so the client can tell the user their answer couldn't be
    # graded. skipped (D-93) gets a reveal too -- it's terminal and immediate,
    # same as graded, just with no correct/incorrect verdict alongside it.
    reveal = None
    score: float | None = None
    grader_output: GraderOutput | None = None
    if attempt.status in ("graded", "skipped"):
        if exercise.type in DETERMINISTIC_TYPES:
            reveal = build_reveal(exercise)
        else:
            reveal = build_summarize_reveal(exercise)
            score = float(attempt.score) if attempt.score is not None else None
            if attempt.grader_output:
                grader_output = GraderOutput(**attempt.grader_output)

    percentile = await _read_percentile(db, exercise.id, exercise.version)

    return AttemptResponse(
        attempt_id=attempt.id,
        status=attempt.status,
        is_correct=attempt.is_correct,
        reveal=reveal,
        score=score,
        grader_output=grader_output,
        percentile=percentile,
        streak=None,
        session=SessionProgress(completed=completed, remaining=remaining),
    ).model_dump(mode="json")
