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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import grader_health
from app.core.timezones import local_date_for, local_day_end_utc
from app.models import Attempt, DailySession, Exercise, User, UserConceptState
from app.schemas.session import SessionExercise, SessionExercisePayload, SessionResponse
from app.sessions.sampler import (
    ALL_CANDIDATE_TYPES,
    DETERMINISTIC_TYPES,
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
    # docs/05 section 4: a degraded grader excludes summarize from newly
    # built sessions; already-issued sessions are unaffected since this only
    # runs on first-of-day sampling.
    degraded = await grader_health.is_degraded(redis)
    candidate_types = DETERMINISTIC_TYPES if degraded else ALL_CANDIDATE_TYPES
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
    )

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
        # Two concurrent first-of-day requests raced to insert; the loser
        # falls back to whatever the winner persisted (D-17: the row is truth).
        await db.rollback()
        existing = await db.get(DailySession, (user.id, today))
        if existing is None:
            raise
        return slots_from_dicts(existing.exercise_list)
    return slots


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
        slots = slots_from_dicts(existing.exercise_list)
        await redis.set(cache_key, json.dumps(_slot_dicts(slots)), ex=CACHE_TTL_SECONDS)
        return today, slots

    slots = await _build_and_persist_session(db, redis, user, today)
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
    elif exercise.type == "summarize":
        fields["max_words"] = payload.get("max_words")
    return SessionExercisePayload(**fields)


async def get_today_session(db: AsyncSession, redis: Redis, user: User) -> dict:
    today, slots = await get_today_slots(db, redis, user)
    if not slots:
        empty = SessionResponse(session_date=today, completed=True, exercises=[])
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
