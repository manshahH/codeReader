"""Exercise spec sampler.

Owns the curriculum distribution (docs/01): the sampler decides concept,
difficulty, type, domain, line budget, has_bug, and avoid_patterns; the
generator LLM only fills in whatever spec it is handed. Pure and seeded via an
injected random.Random so it is unit-testable without any DB or LLM access.
"""

from __future__ import annotations

import dataclasses
import random

from pipeline.taxonomy import Concept, concepts_for_type

DOMAINS: tuple[str, ...] = (
    "checkout service",
    "inventory service",
    "billing reconciliation",
    "order fulfillment",
    "shipping rate calculator",
    "loyalty points ledger",
    "notification dispatcher",
    "search indexing pipeline",
    "user onboarding flow",
    "subscription renewal job",
    "cart abandonment worker",
    "refund processor",
    "warehouse allocation",
    "price markdown engine",
    "fraud scoring service",
    "customer support ticketing",
    "analytics event pipeline",
    "feature flag service",
    "content moderation queue",
    "recommendation ranking",
    "tax calculation service",
    "coupon redemption",
    "session management",
    "rate limiter",
    "audit log writer",
    "webhook delivery",
    "invoice generation",
    "vendor payout batch",
    "catalog sync job",
    "returns processing",
)

_HAS_BUG_FALSE_RATE = 0.15
_AVOID_PATTERNS_HISTORY_DEPTH = 3

# Line budget scales with difficulty; difficulty bands mirror the operational
# scales in the generator templates (1-2 trivial ... 9-10 the trap is control
# flow itself).
_DIFFICULTY_LINE_BUDGETS: tuple[tuple[range, tuple[int, int]], ...] = (
    (range(1, 3), (10, 20)),
    (range(3, 5), (15, 30)),
    (range(5, 7), (20, 45)),
    (range(7, 9), (30, 55)),
    (range(9, 11), (40, 60)),
)


def _line_budget_for_difficulty(difficulty: int) -> tuple[int, int]:
    for band, budget in _DIFFICULTY_LINE_BUDGETS:
        if difficulty in band:
            return budget
    return (20, 60)


@dataclasses.dataclass(frozen=True)
class ExerciseSpec:
    type: str
    concept: str
    difficulty: int
    domain: str
    line_budget_min: int
    line_budget_max: int
    has_bug: bool | None  # None for trace; has_bug is spot_the_bug-only
    avoid_patterns: tuple[str, ...]


def sample_spec(
    rng: random.Random,
    exercise_type: str,
    *,
    recent_bug_mechanisms: dict[str, list[str]] | None = None,
) -> ExerciseSpec:
    if exercise_type not in ("spot_the_bug", "trace"):
        raise ValueError(f"unknown exercise type: {exercise_type!r}")

    concepts = concepts_for_type(exercise_type)
    if not concepts:
        raise ValueError(f"no taxonomy concepts apply to type {exercise_type!r}")
    concept: Concept = rng.choice(concepts)

    difficulty = rng.randint(1, 10)
    domain = rng.choice(DOMAINS)
    line_budget_min, line_budget_max = _line_budget_for_difficulty(difficulty)

    has_bug: bool | None = None
    if exercise_type == "spot_the_bug":
        has_bug = rng.random() >= _HAS_BUG_FALSE_RATE

    history = recent_bug_mechanisms or {}
    avoid_patterns = tuple(history.get(concept.slug, [])[-_AVOID_PATTERNS_HISTORY_DEPTH:])

    return ExerciseSpec(
        type=exercise_type,
        concept=concept.slug,
        difficulty=difficulty,
        domain=domain,
        line_budget_min=line_budget_min,
        line_budget_max=line_budget_max,
        has_bug=has_bug,
        avoid_patterns=avoid_patterns,
    )


def sample_batch(
    rng: random.Random,
    n: int,
    *,
    type_mix: tuple[str, ...] = ("spot_the_bug", "trace"),
    recent_bug_mechanisms: dict[str, list[str]] | None = None,
) -> list[ExerciseSpec]:
    return [
        sample_spec(rng, type_mix[i % len(type_mix)], recent_bug_mechanisms=recent_bug_mechanisms)
        for i in range(n)
    ]
