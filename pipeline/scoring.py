"""Best-of-N quality scoring (D-84).

A published exercise's quality is scored from signals the gate chain ALREADY
collects for free -- no extra LLM call. The score has two uses (D-84 2b):

  1. Select the best survivor when a spec produced more than one.
  2. Calibrate authored difficulty at generation time: a strong gate model that
     solves a "difficulty 8" instantly at high confidence is telling us the
     exercise is boring or mislabeled, so it is flagged for downgrade/review
     BEFORE we have users to measure difficulty_empirical against (D-61 fills
     that column post-launch; this closes the gap earlier).

The strongest free signal is solver confidence vs authored difficulty: genuine
solver STRUGGLE (lower confidence, still correct) on a high-difficulty spec is a
QUALITY MARKER, not a problem; a confident instant solve on a hard spec is the
warning sign. Everything here is a pure function of already-captured signals and
is unit-testable without a DB, LLM, or sandbox.
"""

from __future__ import annotations

import dataclasses

# Higher score is better; the best-scoring survivor of a spec is published.
_BASE_SCORE = 1.0

# Difficulty at/above which a confident instant solve is suspicious and genuine
# struggle is a quality marker.
_HARD_DIFFICULTY = 7
_MID_DIFFICULTY = 6
# Solver confidence thresholds (the solver returns p in [0, 1]).
_BREEZE_CONFIDENCE = 0.90
_STRUGGLE_CONFIDENCE = 0.60

# Penalties / bonuses. Kept as named constants so the policy is explicit and
# tunable (D-84 2c): edit here, no code change elsewhere.
_PENALTY_BREEZED_HARD = 0.40  # aced a hard exercise at high confidence -> boring/mislabeled
_BONUS_STRUGGLE_HARD = 0.15  # solved a hard exercise at low confidence -> genuinely hard
_PENALTY_BUG_IN_FIRST_TWO_LINES = 0.20  # STB: the bug is visible immediately
_PENALTY_SHORT_CODE_AT_HIGH_DIFFICULTY = 0.20  # trivially short code at high difficulty
_PENALTY_CLAIM_MISMATCH = 0.15  # generator mis-stated its own bug_lines / B4 claim
_PENALTY_SEMANTIC_FLAG = 0.25  # survived only with a human-review FLAG

_SHORT_CODE_MAX_LINES = 8


@dataclasses.dataclass(frozen=True)
class QualityScore:
    score: float
    breakdown: dict[str, float]
    difficulty_miscalibrated: bool
    difficulty_empirical_estimate: int


@dataclasses.dataclass(frozen=True)
class ScoreSignals:
    """Everything the scorer reads, all collected for free by the gate chain."""

    exercise_type: str
    authored_difficulty: int
    solver_confidence: float
    solver_matched: bool  # solver's answer matched the key (PASS), vs a survived FLAG
    code_line_count: int
    # spot_the_bug only:
    verified_bug_lines: tuple[int, ...] = ()
    claim_mismatch: bool = False
    # any semantic gate returned FLAG (survived-but-needs-review) rather than PASS
    semantic_flagged: bool = False


def _empirical_difficulty_estimate(confidence: float, matched: bool) -> int:
    """Map solver confidence onto the 1-10 difficulty scale, mirroring D-61's
    percentiles formula (1 + 9*(1 - solve_rate)). A confident solve reads as a
    low empirical difficulty; a miss or low-confidence solve reads as high.
    """
    solved_strength = confidence if matched else 0.0
    return max(1, min(10, round(1 + 9 * (1 - solved_strength))))


def score_survivor(signals: ScoreSignals) -> QualityScore:
    breakdown: dict[str, float] = {}
    score = _BASE_SCORE
    d = signals.authored_difficulty
    c = signals.solver_confidence

    # Solver-vs-difficulty calibration -- the strongest free signal.
    if d >= _HARD_DIFFICULTY and signals.solver_matched and c >= _BREEZE_CONFIDENCE:
        breakdown["breezed_hard"] = -_PENALTY_BREEZED_HARD
        score -= _PENALTY_BREEZED_HARD
    elif d >= _HARD_DIFFICULTY and signals.solver_matched and c <= _STRUGGLE_CONFIDENCE:
        breakdown["genuine_struggle_hard"] = _BONUS_STRUGGLE_HARD
        score += _BONUS_STRUGGLE_HARD

    # A hard exercise the gate model breezed is the mislabel signal (D-84 2b).
    difficulty_miscalibrated = (
        d >= _HARD_DIFFICULTY and signals.solver_matched and c >= _BREEZE_CONFIDENCE
    )

    if signals.exercise_type == "spot_the_bug":
        if signals.verified_bug_lines and min(signals.verified_bug_lines) <= 2:
            breakdown["bug_in_first_two_lines"] = -_PENALTY_BUG_IN_FIRST_TWO_LINES
            score -= _PENALTY_BUG_IN_FIRST_TWO_LINES
        if signals.claim_mismatch:
            breakdown["claim_mismatch"] = -_PENALTY_CLAIM_MISMATCH
            score -= _PENALTY_CLAIM_MISMATCH

    if d >= _MID_DIFFICULTY and signals.code_line_count < _SHORT_CODE_MAX_LINES:
        breakdown["short_code_at_high_difficulty"] = -_PENALTY_SHORT_CODE_AT_HIGH_DIFFICULTY
        score -= _PENALTY_SHORT_CODE_AT_HIGH_DIFFICULTY

    if signals.semantic_flagged:
        breakdown["semantic_flag"] = -_PENALTY_SEMANTIC_FLAG
        score -= _PENALTY_SEMANTIC_FLAG

    score = max(0.0, min(1.0, score))
    return QualityScore(
        score=score,
        breakdown=breakdown,
        difficulty_miscalibrated=difficulty_miscalibrated,
        difficulty_empirical_estimate=_empirical_difficulty_estimate(c, signals.solver_matched),
    )
