"""Level difficulty bands (audit FIX 5): junior 1-5, mid 3-8, senior 5-10.

Before this, LEVEL_DIFFICULTY was only a TARGET and closest-available won,
so a thin pool could serve a junior a difficulty-8 exercise and a senior a
difficulty-2 one. Non-boss slots must stay in band whenever the pool
supports it; the boss slot may exceed the band top by at most 2 (capped at
10); an unfillable band degrades to closest rather than an empty session.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.percentiles import compute_exercise_stats
from app.models import Attempt, Exercise
from app.sessions.sampler import (
    LEVEL_BANDS,
    LEVEL_DIFFICULTY,
    CandidateExercise,
    build_session_slots,
    fetch_candidates,
)
from tests.factories_m4 import (
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_stb_exercise,
    make_user,
)


def _candidate(difficulty: int, concepts: list[str]) -> CandidateExercise:
    return CandidateExercise(
        id=uuid.uuid4(),
        version=1,
        type="spot_the_bug",
        difficulty_authored=difficulty,
        concepts=concepts,
        est_time_s=90,
    )


def _build(candidates: list[CandidateExercise], level: str, due: list[str] | None = None):
    return build_session_slots(
        candidates=candidates,
        due_concepts=due or [],
        concept_mastery={},
        recently_seen_ids=set(),
        level_difficulty=LEVEL_DIFFICULTY[level],
        level_band=LEVEL_BANDS[level],
    )


def _difficulties(slots, candidates) -> dict[bool, list[float]]:
    by_id = {c.id: c for c in candidates}
    out: dict[bool, list[float]] = {False: [], True: []}
    for slot in slots:
        out[slot.is_boss].append(by_id[slot.exercise_id].difficulty)
    return out


def test_junior_never_receives_an_out_of_band_non_boss_when_the_pool_supports_the_band():
    candidates = [
        _candidate(2, ["mutable-default-arg"]),
        _candidate(3, ["off-by-one"]),
        _candidate(4, ["aliasing-vs-copy"]),
        _candidate(5, ["closure-late-binding"]),
        _candidate(8, ["shared-class-attribute"]),
        _candidate(9, ["variable-shadowing"]),
    ]

    slots = _build(candidates, "junior")

    difficulties = _difficulties(slots, candidates)
    assert difficulties[False], "expected non-boss slots"
    assert all(1 <= d <= 5 for d in difficulties[False]), difficulties[False]


def test_junior_due_concept_with_only_out_of_band_exercises_is_deferred_not_served():
    """Negative test for the band: the due concept's only exercise is
    difficulty 9, so it is skipped (deferred), never served to a junior as a
    non-boss slot."""
    hard_due = _candidate(9, ["concurrency-conceptual"])
    candidates = [
        hard_due,
        _candidate(3, ["off-by-one"]),
        _candidate(4, ["aliasing-vs-copy"]),
    ]

    slots = _build(candidates, "junior", due=["concurrency-conceptual"])

    non_boss_ids = {s.exercise_id for s in slots if not s.is_boss}
    assert hard_due.id not in non_boss_ids


def test_senior_never_receives_a_trivial_exercise_when_the_pool_supports_the_band():
    candidates = [
        _candidate(2, ["mutable-default-arg"]),
        _candidate(2, ["off-by-one"]),
        _candidate(6, ["aliasing-vs-copy"]),
        _candidate(7, ["closure-late-binding"]),
        _candidate(8, ["shared-class-attribute"]),
        _candidate(9, ["variable-shadowing"]),
    ]

    slots = _build(candidates, "senior")

    difficulties = _difficulties(slots, candidates)
    assert difficulties[False]
    assert all(5 <= d <= 10 for d in difficulties[False]), difficulties[False]


def test_boss_slot_may_exceed_the_band_top_by_two_but_no_more():
    """Junior band tops at 5, so the boss may reach 7. With both a 7 and a 9
    available, the 9 is over the cap and the 7 must win."""
    boss_ok = _candidate(7, ["shared-class-attribute"])
    boss_too_hard = _candidate(9, ["variable-shadowing"])
    candidates = [
        _candidate(3, ["mutable-default-arg"]),
        _candidate(4, ["off-by-one"]),
        boss_ok,
        boss_too_hard,
    ]

    slots = _build(candidates, "junior")

    boss = [s for s in slots if s.is_boss]
    assert boss and boss[0].exercise_id == boss_ok.id


def test_band_that_cannot_be_filled_degrades_to_closest_not_an_empty_session():
    candidates = [
        _candidate(9, ["mutable-default-arg"]),
        _candidate(9, ["off-by-one"]),
        _candidate(10, ["aliasing-vs-copy"]),
    ]

    slots = _build(candidates, "junior")

    assert slots, "an unfillable band must degrade, not produce an empty session"


def test_empirical_difficulty_overrides_authored_for_band_placement():
    """An exercise authored at 3 that plays like an 8 (difficulty=8.0 from
    stats) must not land in a junior's non-boss slots."""
    plays_hard = CandidateExercise(
        id=uuid.uuid4(),
        version=1,
        type="spot_the_bug",
        difficulty_authored=3,
        concepts=["mutable-default-arg"],
        est_time_s=90,
        difficulty=8.0,
    )
    easy = _candidate(3, ["off-by-one"])

    slots = _build([plays_hard, easy], "junior")

    non_boss_ids = {s.exercise_id for s in slots if not s.is_boss}
    assert plays_hard.id not in non_boss_ids
    assert easy.id in non_boss_ids


@pytest.mark.asyncio
async def test_fetch_candidates_prefers_empirical_difficulty_once_n_reaches_30(
    db_session: AsyncSession,
) -> None:
    """End to end through the stats job: 30 graded attempts with a 0%
    solve rate push difficulty_empirical to 10, and fetch_candidates serves
    the empirical value; a second exercise below the threshold keeps its
    authored difficulty.
    """
    user = await make_user(db_session)
    hard_in_practice = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        difficulty_authored=2,
    )
    too_few_attempts = await make_stb_exercise(
        db_session,
        concepts=["off-by-one"],
        difficulty_authored=4,
    )
    now = dt.datetime.now(dt.UTC)
    for exercise, count in ((hard_in_practice, 30), (too_few_attempts, 10)):
        for _ in range(count):
            db_session.add(
                Attempt(
                    user_id=user.id,
                    exercise_id=exercise.id,
                    exercise_version=exercise.version,
                    session_date=now.date(),
                    answer={"line": 2, "reason_id": "b"},
                    grading_mode="deterministic",
                    status="graded",
                    is_correct=False,
                    time_taken_ms=1000,
                ),
            )
    await db_session.commit()

    await compute_exercise_stats(db_session)

    stored = await db_session.scalar(
        select(Exercise.difficulty_empirical).where(Exercise.id == hard_in_practice.id),
    )
    assert stored is not None and float(stored) == 10.0

    candidates = {c.id: c for c in await fetch_candidates(db_session)}
    assert candidates[hard_in_practice.id].difficulty == 10.0
    assert candidates[too_few_attempts.id].difficulty == 4.0
