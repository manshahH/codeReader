"""GET /session/today: build-on-request (D-23), persist (D-17), cache in Redis.

Payload-only serialization: SessionResponse/SessionExercise (schemas/session.py)
have no field that could carry `grading` or `explanation` -- exercise rows are
never dumped wholesale, only named columns/keys are copied across (invariant 1).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

from redis.asyncio import Redis
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.grading import DETERMINISTIC_TYPES as GRADED_DETERMINISTIC_TYPES
from app.attempts.grading import build_reveal
from app.attempts.rubric import build_summarize_reveal
from app.config import get_settings
from app.core import grader_health
from app.core.metrics import record_outcome
from app.core.timezones import local_date_for, local_day_end_utc
from app.models import Attempt, DailySession, Exercise, User, UserConceptState
from app.schemas.session import (
    SessionExercise,
    SessionExercisePayload,
    SessionResponse,
    SessionReviewExercise,
    SessionReviewResponse,
)
from app.sessions.sampler import (
    ALL_CANDIDATE_TYPES,
    DEFAULT_LEVEL_BAND,
    DETERMINISTIC_TYPES,
    LEVEL_BANDS,
    LEVEL_DIFFICULTY,
    SessionSlot,
    build_session_slots,
    difficulty_band,
    fetch_candidates,
)

CACHE_TTL_SECONDS = 36 * 60 * 60
RECENTLY_SEEN_WINDOW_DAYS = 14


def _cache_key(user_id: uuid.UUID, session_date: dt.date) -> str:
    return f"session:{user_id}:{session_date.isoformat()}"


def _slot_dicts(slots: list[SessionSlot]) -> list[dict]:
    return [
        {
            "slot": s.slot,
            "exercise_id": str(s.exercise_id),
            "version": s.version,
            "is_boss": s.is_boss,
        }
        for s in slots
    ]


def slots_from_dicts(items: list[dict]) -> list[SessionSlot]:
    return [
        SessionSlot(
            slot=item["slot"],
            exercise_id=uuid.UUID(item["exercise_id"]),
            version=item["version"],
            is_boss=item.get("is_boss", False),
        )
        for item in items
    ]


async def _build_and_persist_session(
    db: AsyncSession,
    redis: Redis,
    user: User,
    today: dt.date,
) -> list[SessionSlot]:
    # D-104's lock class, applied to first-of-day SESSION CREATION (D-122).
    #
    # Two concurrent first-of-day requests both found no daily_sessions row,
    # both sampled, and both INSERTed. The loser hit the daily_sessions_pkey
    # unique violation, and the IntegrityError recovery below -- which was
    # written for exactly this case -- then failed on its own re-read, so the
    # request 500d. This lock makes that race unreachable rather than trying to
    # make the recovery survivable.
    #
    # DOUBLE-CHECKED, deliberately. The caller already returned on a Redis hit
    # or an existing row, so the hot path (every request after the first of the
    # day) never reaches this and never pays for a lock. The re-read below is
    # what closes the window between the caller's check and this acquisition:
    # the loser blocks here until the winner commits, and Postgres READ
    # COMMITTED then gives its re-read a fresh snapshot containing the winner's
    # row.
    #
    # Keyed per-(user, day), NOT per-user: a lock held across a day boundary
    # would serialize unrelated days, and the thing being protected is exactly
    # one row per (user_id, session_date). Transaction-scoped, released at the
    # commit below (or on rollback); no explicit unlock.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_a), hashtext(:lock_b))"),
        {"lock_a": str(user.id), "lock_b": f"session_build:{today.isoformat()}"},
    )
    winner = await db.get(DailySession, (user.id, today))
    if winner is not None and winner.exercise_list:
        # Someone built it while we waited. Their row is the truth (D-17), and
        # returning it is what makes both concurrent callers see the IDENTICAL
        # session rather than two independently sampled ones.
        return slots_from_dicts(winner.exercise_list)

    # D-123: summarize is OFF by default (D-115) and this is where that is
    # ENFORCED, not merely intended. This line used to read
    #   candidate_types = DETERMINISTIC_TYPES if degraded else ALL_CANDIDATE_TYPES
    # so a healthy grader pulled summarize into the candidate pool, and a single
    # live summarize row was enough to serve one. D-115 asserted the sampler
    # already excluded it; that was never true.
    #
    # The exclusion is applied to the SQL type filter in fetch_candidates, so it
    # holds regardless of what is in the exercises table: a live summarize row is
    # simply never a candidate. The degraded-grader rule (docs/05 section 4) still
    # applies on top, for the case where summarize is deliberately enabled.
    # Already-issued sessions are unaffected either way; this only runs on
    # first-of-day sampling.
    degraded = await grader_health.is_degraded(redis)
    summarize_allowed = get_settings().SUMMARIZE_ENABLED and not degraded
    candidate_types = ALL_CANDIDATE_TYPES if summarize_allowed else DETERMINISTIC_TYPES
    candidates = await fetch_candidates(db, types=candidate_types)

    due_cutoff = local_day_end_utc(user.timezone, today)
    due_rows = await db.execute(
        select(UserConceptState.concept)
        .where(
            UserConceptState.user_id == user.id,
            UserConceptState.next_review_at < due_cutoff,
        )
        .order_by(UserConceptState.next_review_at.asc()),
    )
    due_concepts = [row[0] for row in due_rows.all()]

    mastery_rows = await db.execute(
        select(UserConceptState.concept, UserConceptState.mastery).where(
            UserConceptState.user_id == user.id,
        ),
    )
    concept_mastery = {concept: float(mastery) for concept, mastery in mastery_rows.all()}

    recent_cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=RECENTLY_SEEN_WINDOW_DAYS)
    recent_rows = await db.execute(
        select(Attempt.exercise_id).where(
            Attempt.user_id == user.id,
            Attempt.created_at >= recent_cutoff,
        ),
    )
    recently_seen_ids = {row[0] for row in recent_rows.all()}

    slots = build_session_slots(
        candidates=candidates,
        due_concepts=due_concepts,
        concept_mastery=concept_mastery,
        recently_seen_ids=recently_seen_ids,
        level_difficulty=LEVEL_DIFFICULTY.get(user.level, 5),
        level_band=LEVEL_BANDS.get(user.level, DEFAULT_LEVEL_BAND),
    )

    if not slots:
        # D-59: an empty live pool must stay transient. Persisting (or
        # caching) [] would lock the user into an empty "completed" day for
        # up to 36h even after content is restored; returning without
        # persisting means the very next fetch retries the build.
        # M8 beta readiness: this is exactly "empty-session occurrences",
        # one of the things to watch during the beta week -- recorded here
        # (the only place a build is attempted) via the same total/error
        # counter shape as the other golden signals, surfaced as
        # empty_session_rate on GET /admin/metrics.
        await record_outcome(redis, "session_build", is_error=True)
        return []
    await record_outcome(redis, "session_build", is_error=False)

    daily_session = DailySession(
        user_id=user.id,
        session_date=today,
        exercise_list=_slot_dicts(slots),
    )
    db.add(daily_session)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        # Now UNREACHABLE via the concurrent path: the advisory lock above
        # serializes first-of-day builds, so a loser returns the winner's row
        # before ever reaching this insert. Kept as the un-raceable DB backstop
        # underneath the lock, exactly as the partial unique index on
        # streak_events sits under the attempts lock (D-104).
        #
        # NOTE (D-119/D-122): this recovery path is ALSO the one that used to
        # 500. The `db.get` below raised MissingGreenlet from the connection
        # pool's pre-ping after the rollback, and that behaviour is still
        # unexplained and unfixed. It is not fixed here on purpose -- catching
        # MissingGreenlet would paper over the wrong layer. The lock is what
        # makes it unreachable. If this branch ever fires again, that is a
        # signal the lock was bypassed, not a licence to catch the symptom.
        await db.rollback()
        existing = await db.get(DailySession, (user.id, today))
        if existing is None:
            raise
        return slots_from_dicts(existing.exercise_list)
    return slots


async def purge_sessions_referencing(
    db: AsyncSession,
    redis: Redis,
    exercise_id: uuid.UUID,
) -> int:
    """Remove every still-in-flight daily session that references an exercise
    (D-58, the pull path). Deletes the daily_sessions rows, commits (together
    with whatever the caller flushed, e.g. the status flip), THEN deletes the
    Redis keys -- in that order, so a concurrent GET racing the purge cannot
    re-cache a row that is about to disappear.

    Two conditions bound what is purged (D-102):
    - `session_date >= yesterday`: older rows can no longer be served (the
      cache TTL is 36h and keys are per-date) and stay as durable history.
    - `completed_at IS NULL`: a COMPLETED session is never served for
      answering again, so pulling content out of it protects the user from
      nothing -- it only erases a day they already finished from their history
      (session count, heatmap, streak evidence). The pull's job is to stop
      an IN-FLIGHT session from serving bad content; a finished one has
      nothing left to serve. The pulled exercise row still exists (status
      flips to 'pulled', the row is not deleted), so a kept completed session
      still renders its already-answered exercise on the review screen.
    """
    servable_cutoff = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1)
    rows = (
        await db.execute(
            select(DailySession.user_id, DailySession.session_date).where(
                DailySession.session_date >= servable_cutoff,
                DailySession.completed_at.is_(None),
                DailySession.exercise_list.contains([{"exercise_id": str(exercise_id)}]),
            ),
        )
    ).all()

    for user_id, session_date in rows:
        await db.execute(
            delete(DailySession).where(
                DailySession.user_id == user_id,
                DailySession.session_date == session_date,
            ),
        )
    await db.commit()

    for user_id, session_date in rows:
        await redis.delete(_cache_key(user_id, session_date))
    return len(rows)


async def get_today_slots(
    db: AsyncSession,
    redis: Redis,
    user: User,
) -> tuple[dt.date, list[SessionSlot]]:
    """Redis cache -> daily_sessions row (Redis-flush fallback, D-17) -> build fresh."""
    today = local_date_for(user.timezone)
    cache_key = _cache_key(user.id, today)

    cached = await redis.get(cache_key)
    if cached is not None:
        return today, slots_from_dicts(json.loads(cached))

    existing = await db.get(DailySession, (user.id, today))
    if existing is not None:
        if existing.exercise_list:
            slots = slots_from_dicts(existing.exercise_list)
            await redis.set(cache_key, json.dumps(_slot_dicts(slots)), ex=CACHE_TTL_SECONDS)
            return today, slots
        # Heal a pre-D-59 empty row: it should never have been persisted and
        # would otherwise pin the user to an empty day. The delete commits
        # together with the rebuilt session below (or rolls back harmlessly
        # if the pool is still empty).
        await db.delete(existing)
        await db.flush()

    slots = await _build_and_persist_session(db, redis, user, today)
    if slots:
        await redis.set(cache_key, json.dumps(_slot_dicts(slots)), ex=CACHE_TTL_SECONDS)
    return today, slots


def _serialize_payload(exercise: Exercise) -> SessionExercisePayload:
    payload = exercise.payload
    fields: dict = {
        "code": payload.get("code"),
        "context_note": payload.get("context_note"),
    }
    if exercise.type == "spot_the_bug":
        fields["answer_mode"] = payload.get("answer_mode")
        fields["reason_options"] = [
            {"id": option["id"], "text": option["text"]}
            for option in payload.get("reason_options", [])
        ]
    elif exercise.type == "trace":
        fields["question"] = payload.get("question")
        # Deliberately drop `misconception`: it tags distractors only, so its
        # presence/absence would let a client infer the correct choice_id
        # without answering.
        fields["choices"] = [
            {"id": choice["id"], "text": choice["text"]} for choice in payload.get("choices", [])
        ]
    elif exercise.type == "predict_the_fix":
        # D-80: buggy code + the failing test and its output; choices are the
        # candidate fixes (id + code). No answer-key field is ever copied --
        # correct_choice_id lives only in exercise.grading.
        fields["answer_mode"] = payload.get("answer_mode")
        fields["question"] = payload.get("question")
        fields["failing_test"] = payload.get("failing_test")
        fields["test_output"] = payload.get("test_output")
        fields["choices"] = [
            {"id": choice["id"], "text": choice["text"]} for choice in payload.get("choices", [])
        ]
    elif exercise.type == "summarize":
        fields["max_words"] = payload.get("max_words")
    return SessionExercisePayload(**fields)


async def get_today_session(db: AsyncSession, redis: Redis, user: User) -> dict:
    today, slots = await get_today_slots(db, redis, user)
    if not slots:
        # D-59: "no content yet", NOT a completed day -- completed=True here
        # would tell the client the user is done and lock the day shut.
        empty = SessionResponse(session_date=today, completed=False, exercises=[])
        return empty.model_dump(mode="json")

    exercise_ids = {s.exercise_id for s in slots}
    rows = await db.execute(select(Exercise).where(Exercise.id.in_(exercise_ids)))
    exercise_by_key = {(row.id, row.version): row for row in rows.scalars().all()}

    # D-38: any submitted attempt counts as "attempted", regardless of
    # status -- a pending-grade summarize submission must not look
    # unattempted just because the grade hasn't resolved yet.
    attempted_rows = await db.execute(
        select(Attempt.exercise_id).where(
            Attempt.user_id == user.id,
            Attempt.session_date == today,
        ),
    )
    attempted_ids = {row[0] for row in attempted_rows.all()}

    exercises: list[SessionExercise] = []
    for slot in slots:
        exercise = exercise_by_key.get((slot.exercise_id, slot.version))
        if exercise is None:
            continue
        exercises.append(
            SessionExercise(
                slot=slot.slot,
                exercise_id=exercise.id,
                version=exercise.version,
                type=exercise.type,
                concepts=list(exercise.concepts),
                language=exercise.language,
                difficulty_band=difficulty_band(exercise.difficulty_authored, is_boss=slot.is_boss),
                est_time_s=exercise.est_time_s,
                is_boss=slot.is_boss,
                attempted=exercise.id in attempted_ids,
                payload=_serialize_payload(exercise),
            ),
        )

    completed = len(slots) > 0 and attempted_ids.issuperset(s.exercise_id for s in slots)

    return SessionResponse(
        session_date=today,
        completed=completed,
        exercises=exercises,
    ).model_dump(mode="json")


def _review_verdict(attempt: Attempt) -> str:
    if attempt.status == "graded":
        return "correct" if attempt.is_correct else "incorrect"
    return attempt.status  # 'skipped' | 'grading_pending' | 'grading_failed'


def _review_reveal(exercise: Exercise, attempt: Attempt):
    # D-93d: reused verbatim from the same builders POST /attempts and
    # GET /attempts/{id} call -- never reimplemented here. A skip gets a
    # reveal too (it's terminal, same as graded); pending/failed do not.
    if attempt.status not in ("graded", "skipped"):
        return None
    if exercise.type in GRADED_DETERMINISTIC_TYPES:
        return build_reveal(exercise)
    return build_summarize_reveal(exercise)


async def get_today_review(db: AsyncSession, redis: Redis, user: User) -> dict:
    """GET /session/today/review (D-93d): every exercise from today's
    session the user has actually submitted an answer for, with their
    answer, the verdict, and the full reveal -- the teaching moment for a
    session already played. Exercises not yet attempted are omitted; there
    is nothing to review about them yet.
    """
    today, slots = await get_today_slots(db, redis, user)
    if not slots:
        return SessionReviewResponse(session_date=today, exercises=[]).model_dump(mode="json")

    exercise_ids = {s.exercise_id for s in slots}
    exercise_rows = await db.execute(select(Exercise).where(Exercise.id.in_(exercise_ids)))
    exercise_by_key = {(row.id, row.version): row for row in exercise_rows.scalars().all()}

    attempt_rows = await db.execute(
        select(Attempt).where(Attempt.user_id == user.id, Attempt.session_date == today),
    )
    attempt_by_exercise = {a.exercise_id: a for a in attempt_rows.scalars().all()}

    exercises: list[SessionReviewExercise] = []
    for slot in slots:
        attempt = attempt_by_exercise.get(slot.exercise_id)
        if attempt is None:
            continue
        exercise = exercise_by_key.get((slot.exercise_id, slot.version))
        if exercise is None:
            continue

        exercises.append(
            SessionReviewExercise(
                slot=slot.slot,
                exercise_id=exercise.id,
                version=exercise.version,
                type=exercise.type,
                concepts=list(exercise.concepts),
                code=exercise.payload.get("code", ""),
                context_note=exercise.payload.get("context_note", ""),
                answer=attempt.answer,
                verdict=_review_verdict(attempt),
                reveal=_review_reveal(exercise, attempt),
            ),
        )

    return SessionReviewResponse(session_date=today, exercises=exercises).model_dump(mode="json")
