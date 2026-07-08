"""Session sampler: due concepts -> curriculum fill -> one boss slot.

D-37 (superseded by M5): the candidate pool used to be hard-restricted to
spot_the_bug/trace because POST /attempts only graded deterministic types.
M5 ships rubric grading, so summarize is now a normal candidate type; the
caller (sessions/service.py) decides whether to include it based on grader
health (docs/05 section 4: degraded grader -> summarize excluded from newly
built sessions; already-issued sessions are unchanged).
"""

from __future__ import annotations

import dataclasses
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DETERMINISTIC_TYPES = ("spot_the_bug", "trace")
ALL_CANDIDATE_TYPES = (*DETERMINISTIC_TYPES, "summarize")
LEVEL_DIFFICULTY = {"junior": 3, "mid": 5, "senior": 7}
MIN_SLOTS = 3
MAX_NON_BOSS_SLOTS = 4
BOSS_DIFFICULTY_FLOOR = 7


@dataclasses.dataclass(frozen=True)
class CandidateExercise:
    id: uuid.UUID
    version: int
    type: str
    difficulty_authored: int
    concepts: list[str]
    est_time_s: int


@dataclasses.dataclass(frozen=True)
class SessionSlot:
    slot: int
    exercise_id: uuid.UUID
    version: int
    is_boss: bool


async def fetch_candidates(
    session: AsyncSession,
    *,
    language: str = "python",
    types: tuple[str, ...] = DETERMINISTIC_TYPES,
) -> list[CandidateExercise]:
    """Live exercises via the exercises_current VIEW (D-16: no standalone read path)."""
    rows = await session.execute(
        text(
            """
            SELECT id, version, type, difficulty_authored, concepts, est_time_s
            FROM exercises_current
            WHERE language = :language AND type = ANY(:types)
            """,
        ),
        {"language": language, "types": list(types)},
    )
    return [
        CandidateExercise(
            id=row.id,
            version=row.version,
            type=row.type,
            difficulty_authored=row.difficulty_authored,
            concepts=list(row.concepts),
            est_time_s=row.est_time_s,
        )
        for row in rows
    ]


def difficulty_band(difficulty_authored: int, *, is_boss: bool) -> str:
    """D-35: display-layer mapping; clients never see raw difficulty (D-20)."""
    if is_boss:
        return "boss"
    if difficulty_authored <= 3:
        return "easy"
    if difficulty_authored <= 6:
        return "medium"
    return "hard"


def _closest_by_difficulty(
    candidates: list[CandidateExercise],
    target_difficulty: int,
) -> list[CandidateExercise]:
    return sorted(candidates, key=lambda c: abs(c.difficulty_authored - target_difficulty))


def build_session_slots(
    *,
    candidates: list[CandidateExercise],
    due_concepts: list[str],
    concept_mastery: dict[str, float],
    recently_seen_ids: set[uuid.UUID],
    level_difficulty: int,
) -> list[SessionSlot]:
    """Pure selection: due concepts first, then curriculum fill, then one boss slot.

    Degrades gracefully when the live pool is small: never raises, just
    returns fewer slots than the 3-5 target if the pool can't support it.
    """
    used_ids: set[uuid.UUID] = set()
    selected: list[CandidateExercise] = []

    def pick(pool: list[CandidateExercise]) -> CandidateExercise | None:
        available = [c for c in pool if c.id not in used_ids]
        if not available:
            return None
        fresh = [c for c in available if c.id not in recently_seen_ids]
        chosen = fresh[0] if fresh else available[0]
        used_ids.add(chosen.id)
        return chosen

    # 1. Due concepts first (already ordered most-overdue-first by the caller).
    for concept in due_concepts:
        if len(selected) >= MAX_NON_BOSS_SLOTS:
            break
        concept_pool = _closest_by_difficulty(
            [c for c in candidates if concept in c.concepts],
            level_difficulty,
        )
        chosen = pick(concept_pool)
        if chosen is not None:
            selected.append(chosen)

    # 2. Curriculum fill: weakest-mastery concept first among remaining candidates.
    while len(selected) < MAX_NON_BOSS_SLOTS:
        remaining = [c for c in candidates if c.id not in used_ids]
        if not remaining:
            break
        remaining_concepts = sorted(
            {concept for c in remaining for concept in c.concepts},
            key=lambda concept: concept_mastery.get(concept, 0.0),
        )
        if remaining_concepts:
            weakest = remaining_concepts[0]
            concept_pool = _closest_by_difficulty(
                [c for c in remaining if weakest in c.concepts],
                level_difficulty,
            )
        else:
            concept_pool = _closest_by_difficulty(remaining, level_difficulty)
        chosen = pick(concept_pool)
        if chosen is None:
            break
        selected.append(chosen)

    # 3. One boss slot: slightly above the user's level, distinct from the above.
    boss_target = max(BOSS_DIFFICULTY_FLOOR, level_difficulty + 2)
    boss_pool = sorted(
        (c for c in candidates if c.id not in used_ids),
        key=lambda c: c.difficulty_authored,
        reverse=True,
    )
    hard_enough = [c for c in boss_pool if c.difficulty_authored >= boss_target]
    boss_candidate = pick(hard_enough) or pick(boss_pool)

    slots: list[SessionSlot] = [
        SessionSlot(slot=i + 1, exercise_id=c.id, version=c.version, is_boss=False)
        for i, c in enumerate(selected)
    ]
    if boss_candidate is not None:
        slots.append(
            SessionSlot(
                slot=len(slots) + 1,
                exercise_id=boss_candidate.id,
                version=boss_candidate.version,
                is_boss=True,
            ),
        )

    return slots
