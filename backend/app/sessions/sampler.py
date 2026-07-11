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
# D-61: each level samples within a difficulty BAND, not just toward a
# target. With a thin pool, closest-to-target alone served a junior a
# difficulty-8 exercise and a senior a difficulty-2 one -- a churn event in
# both directions.
LEVEL_BANDS = {"junior": (1, 5), "mid": (3, 8), "senior": (5, 10)}
DEFAULT_LEVEL_BAND = (3, 8)
# The boss slot may exceed the band's top by this margin (capped at 10).
BOSS_BAND_MARGIN = 2
MIN_SLOTS = 3
MAX_NON_BOSS_SLOTS = 4
BOSS_DIFFICULTY_FLOOR = 7
# D-61: below this many graded attempts, difficulty_empirical is noise and
# difficulty_authored is used instead.
MIN_EMPIRICAL_N = 30


@dataclasses.dataclass(frozen=True)
class CandidateExercise:
    id: uuid.UUID
    version: int
    type: str
    difficulty_authored: int
    concepts: list[str]
    est_time_s: int
    # Effective difficulty for sampling: difficulty_empirical once >=
    # MIN_EMPIRICAL_N graded attempts back it, else difficulty_authored.
    difficulty: float | None = None

    def __post_init__(self) -> None:
        if self.difficulty is None:
            object.__setattr__(self, "difficulty", float(self.difficulty_authored))


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
    """Live exercises via the exercises_current VIEW (D-16: no standalone read path).

    D-61: joins exercise_stats so sampling can prefer difficulty_empirical
    over difficulty_authored once enough graded attempts (MIN_EMPIRICAL_N)
    back it.
    """
    rows = await session.execute(
        text(
            """
            SELECT ec.id, ec.version, ec.type, ec.difficulty_authored,
                   ec.difficulty_empirical, ec.concepts, ec.est_time_s,
                   coalesce(s.attempts_count, 0) AS attempts_count
            FROM exercises_current ec
            LEFT JOIN exercise_stats s
              ON s.exercise_id = ec.id AND s.exercise_version = ec.version
            WHERE ec.language = :language AND ec.type = ANY(:types)
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
            difficulty=(
                float(row.difficulty_empirical)
                if row.difficulty_empirical is not None and row.attempts_count >= MIN_EMPIRICAL_N
                else float(row.difficulty_authored)
            ),
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
    target_difficulty: float,
) -> list[CandidateExercise]:
    return sorted(candidates, key=lambda c: abs(c.difficulty - target_difficulty))


def build_session_slots(
    *,
    candidates: list[CandidateExercise],
    due_concepts: list[str],
    concept_mastery: dict[str, float],
    recently_seen_ids: set[uuid.UUID],
    level_difficulty: int,
    level_band: tuple[int, int] = DEFAULT_LEVEL_BAND,
) -> list[SessionSlot]:
    """Pure selection: due concepts first, then curriculum fill, then one boss slot.

    D-61: non-boss slots come from the level's difficulty band whenever the
    pool supports it; only when NO in-band candidate remains does selection
    fall back to closest-by-difficulty (graceful degradation beats an empty
    session). The boss slot may exceed the band top by BOSS_BAND_MARGIN,
    capped at 10.

    Degrades gracefully when the live pool is small: never raises, just
    returns fewer slots than the 3-5 target if the pool can't support it.
    """
    band_low, band_high = level_band
    used_ids: set[uuid.UUID] = set()
    selected: list[CandidateExercise] = []

    def in_band(candidate: CandidateExercise) -> bool:
        return band_low <= candidate.difficulty <= band_high

    def pick(pool: list[CandidateExercise]) -> CandidateExercise | None:
        available = [c for c in pool if c.id not in used_ids]
        if not available:
            return None
        fresh = [c for c in available if c.id not in recently_seen_ids]
        chosen = fresh[0] if fresh else available[0]
        used_ids.add(chosen.id)
        return chosen

    # 1. Due concepts first (already ordered most-overdue-first by the caller).
    # A due concept whose only exercises are out of band is skipped, not
    # served out of band: deferring a review beats a churn-risk difficulty.
    for concept in due_concepts:
        if len(selected) >= MAX_NON_BOSS_SLOTS:
            break
        concept_pool = _closest_by_difficulty(
            [c for c in candidates if concept in c.concepts and in_band(c)],
            level_difficulty,
        )
        chosen = pick(concept_pool)
        if chosen is not None:
            selected.append(chosen)

    # 2. Curriculum fill: weakest-mastery concept first among remaining
    # in-band candidates. In-band ONLY -- out-of-band degradation happens in
    # step 4, and only to keep the session above the MIN_SLOTS floor, never
    # to pad an already-viable session with churn-risk difficulties.
    while len(selected) < MAX_NON_BOSS_SLOTS:
        banded = [c for c in candidates if c.id not in used_ids and in_band(c)]
        if not banded:
            break
        remaining_concepts = sorted(
            {concept for c in banded for concept in c.concepts},
            key=lambda concept: concept_mastery.get(concept, 0.0),
        )
        weakest = remaining_concepts[0]
        concept_pool = _closest_by_difficulty(
            [c for c in banded if weakest in c.concepts],
            level_difficulty,
        )
        chosen = pick(concept_pool)
        if chosen is None:
            break
        selected.append(chosen)

    # 3. One boss slot: slightly above the user's level, distinct from the
    # above, never below the band floor nor more than BOSS_BAND_MARGIN above
    # the band top. If no candidate fits that window, the session simply has
    # no boss -- unless it would fall under MIN_SLOTS, in which case
    # closest-to-cap fills in (a degraded session beats a missing one).
    boss_max = min(10, band_high + BOSS_BAND_MARGIN)
    boss_target = min(boss_max, max(BOSS_DIFFICULTY_FLOOR, level_difficulty + 2))
    eligible = sorted(
        (
            c
            for c in candidates
            if c.id not in used_ids and band_low <= c.difficulty <= boss_max
        ),
        key=lambda c: c.difficulty,
        reverse=True,
    )
    hard_enough = [c for c in eligible if c.difficulty >= boss_target]
    boss_candidate = pick(hard_enough) or pick(eligible)
    if boss_candidate is None and len(selected) < MIN_SLOTS:
        boss_candidate = pick(
            _closest_by_difficulty(
                [c for c in candidates if c.id not in used_ids],
                boss_max,
            ),
        )

    # 4. Degradation pad: only when the pool cannot support the band at all
    # does closest-by-difficulty (as before D-61) top the session up to the
    # MIN_SLOTS floor.
    while len(selected) + (1 if boss_candidate else 0) < MIN_SLOTS:
        chosen = pick(
            _closest_by_difficulty(
                [c for c in candidates if c.id not in used_ids],
                level_difficulty,
            ),
        )
        if chosen is None:
            break
        selected.append(chosen)

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
