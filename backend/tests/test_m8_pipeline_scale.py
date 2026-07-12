"""Content pipeline scaling for a long batch run (M8 part 1):

- dedup pool widened to in_review, not just live (repeated batches are
  additive/idempotent instead of re-generating candidates already sitting in
  the review queue).
- coverage-driven concept sampling (a 200-exercise corpus should cover the
  taxonomy, not cluster).
- commit_after_each_spec so a crash mid-batch keeps every already-published
  candidate instead of losing the whole run.
- BatchReport's token/cost and coverage summary wiring.

All LLM calls are ScriptedLLMClient fixtures; no real tokens spent.
"""

from __future__ import annotations

import json
import random

import pytest
from pipeline.llm_client import ScriptedLLMClient
from pipeline.orchestrator import run_batch
from pipeline.publish import (
    approve,
    concept_type_coverage,
    fetch_dedup_pool_hashes,
    insert_candidate,
)
from pipeline.spec_sampler import ExerciseSpec, sample_spec
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise

_STB_SPEC = ExerciseSpec(
    type="spot_the_bug",
    concept="aliasing-vs-copy",
    difficulty=3,
    domain="checkout service",
    line_budget_min=1,
    line_budget_max=20,
    has_bug=True,
    avoid_patterns=(),
)
_STB_SPEC_2 = ExerciseSpec(
    type="spot_the_bug",
    concept="off-by-one",
    difficulty=3,
    domain="inventory service",
    line_budget_min=1,
    line_budget_max=20,
    has_bug=True,
    avoid_patterns=(),
)
_TRACE_SPEC = ExerciseSpec(
    type="trace",
    concept="control_flow",
    difficulty=1,
    domain="checkout service",
    line_budget_min=1,
    line_budget_max=20,
    has_bug=None,
    avoid_patterns=(),
)

_GOOD_STB_JSON = {
    "buggy_code": (
        "def apply_discount(prices, discount_pct):\n"
        "    updated = prices\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n"
    ),
    "fixed_code": (
        "def apply_discount(prices, discount_pct):\n"
        "    updated = dict(prices)\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n"
    ),
    "bug_lines": [2],
    "test_code": (
        "prices = {'A1': 100.0, 'B2': 50.0}\n"
        "result = apply_discount(prices, 10)\n"
        "assert result == {'A1': 90.0, 'B2': 45.0}\n"
        "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n"
    ),
    "context_note": "Runs once per order in the checkout worker.",
    "reason_options": [
        {"id": "a", "text": "The input price dict is mutated in place via aliasing."},
        {"id": "b", "text": "round() introduces floating point drift here."},
        {"id": "c", "text": "The loop skips the last SKU."},
        {"id": "d", "text": "discount_pct is applied twice."},
    ],
    "correct_reason_id": "a",
    "draft_explanation": {
        "summary": "updated = prices aliases the caller's dict instead of copying it.",
        "principle": "Copy a mutable argument before mutating it in place.",
        "line_notes": [{"line": 2, "note": "Binds updated to the same dict object as prices."}],
    },
    "concepts": ["aliasing-vs-copy"],
    "self_difficulty": 3,
    "self_check": {
        "single_bug_confirmed": True,
        "runs_without_error_on_happy_path": True,
        "no_hinting_names_or_comments": True,
        "distractors_verifiably_wrong": True,
    },
}

_DEFECT_AUDIT_RESPONSE = json.dumps(
    {
        "defects": [
            {"lines": [2], "description": "aliasing mutates caller's dict", "exposed_by": "test"},
        ],
    },
)
_STB_SOLVER_RESPONSE = json.dumps(
    {"answer": {"line": 2, "reason_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
)
_REASONS_RESPONSE = json.dumps(
    {
        "verdicts": [
            {"id": "a", "classification": "correct", "justification": "j"},
            {"id": "b", "classification": "wrong", "justification": "j"},
            {"id": "c", "classification": "wrong", "justification": "j"},
            {"id": "d", "classification": "wrong", "justification": "j"},
        ],
    },
)


def _stb_gate_responses() -> list[str]:
    return [_DEFECT_AUDIT_RESPONSE, _STB_SOLVER_RESPONSE, _REASONS_RESPONSE]


async def _insert_stb(session: AsyncSession, *, status: str, concept: str) -> Exercise:
    candidate_json = dict(_GOOD_STB_JSON)
    candidate_json["concepts"] = [concept]
    from pipeline.schemas import STBCandidate

    candidate = STBCandidate.model_validate(candidate_json)
    exercise = await insert_candidate(
        session,
        ExerciseSpec(
            type="spot_the_bug",
            concept=concept,
            difficulty=3,
            domain="checkout service",
            line_budget_min=1,
            line_budget_max=20,
            has_bug=True,
            avoid_patterns=(),
        ),
        candidate,
        final_explanation={"summary": "s"},
        content_hash=f"hash-{concept}-{status}",
        validation_report={"template_id": "stb_py_v2", "sandbox_gate": {"accepted": True}},
        generator_model="generator-model-placeholder",
        verified_bug_lines=[2],
    )
    if status == "live":
        exercise = await approve(session, exercise.id, exercise.version)
    return exercise


@pytest.fixture(autouse=True)
async def _cleanup_exercises():
    """Some tests in this module exercise `commit_after_each_spec=True`,
    which deliberately commits real rows outside the usual rollback-only
    `db_session` isolation -- clean them up so they don't linger in the
    shared dev database for unrelated tests/count assertions.

    Uses its OWN session/engine, never the test's `db_session`: committing
    on a shared `db_session` here would also commit whatever OTHER test in
    this module merely flushed (never intended to commit), leaking it into
    the real live/in_review pool and corrupting dedup for later tests.
    """
    yield
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await session.execute(
            delete(Exercise).where(Exercise.source["content_hash"].astext.like("hash-%")),
        )
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_dedup_pool_hashes_includes_in_review_not_just_live(
    db_session: AsyncSession,
) -> None:
    live = await _insert_stb(db_session, status="live", concept="aliasing-vs-copy")
    in_review = await _insert_stb(db_session, status="in_review", concept="off-by-one")

    hashes = await fetch_dedup_pool_hashes(db_session)

    assert live.source["content_hash"] in hashes
    assert in_review.source["content_hash"] in hashes


@pytest.mark.asyncio
async def test_concept_type_coverage_counts_live_only(db_session: AsyncSession) -> None:
    await _insert_stb(db_session, status="live", concept="aliasing-vs-copy")
    await _insert_stb(db_session, status="in_review", concept="aliasing-vs-copy")

    coverage = await concept_type_coverage(db_session)

    assert coverage[("spot_the_bug", "aliasing-vs-copy")] == 1


def test_sample_spec_prefers_zero_coverage_concept_when_given_coverage() -> None:
    import collections

    from pipeline.taxonomy import concepts_for_type

    all_stb_concepts = concepts_for_type("spot_the_bug")
    heavy_coverage = {("spot_the_bug", c.slug): 50 for c in all_stb_concepts}
    heavy_coverage[("spot_the_bug", "aliasing-vs-copy")] = 0

    rng = random.Random(42)
    picks = [
        sample_spec(rng, "spot_the_bug", concept_coverage=heavy_coverage).concept
        for _ in range(200)
    ]
    counts = collections.Counter(picks)

    # Uniform-over-~35-concepts baseline would land near 1/35 (~3%); the
    # zero-coverage concept must dominate by a wide margin, not just edge
    # out any single other concept.
    assert counts.most_common(1)[0][0] == "aliasing-vs-copy"
    assert counts["aliasing-vs-copy"] / len(picks) > 0.5


def test_sample_spec_uniform_when_no_coverage_given() -> None:
    rng = random.Random(7)
    picks = {sample_spec(rng, "trace").concept for _ in range(50)}
    assert len(picks) > 1  # not pinned to a single concept absent coverage data


@pytest.mark.asyncio
async def test_run_batch_reports_coverage_before_and_after(db_session: AsyncSession) -> None:
    generator_client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])
    gate_client = ScriptedLLMClient(_stb_gate_responses())

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
    )

    key = ("spot_the_bug", "aliasing-vs-copy")
    assert report.coverage_before.get(key, 0) == 0
    assert report.coverage_after.get(key, 0) == 1


@pytest.mark.asyncio
async def test_run_batch_tracks_client_token_usage_in_report(db_session: AsyncSession) -> None:
    generator_client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])
    generator_client.usage.record(prompt_tokens=1234, completion_tokens=321)
    gate_client = ScriptedLLMClient(_stb_gate_responses())

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="gpt-4.1",
        gate_model="gpt-4o-mini",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
    )

    assert report.generator_usage.prompt_tokens == 1234
    assert report.generator_usage.completion_tokens == 321


@pytest.mark.asyncio
async def test_run_batch_commit_after_each_spec_keeps_earlier_publishes_after_a_later_crash(
    db_session: AsyncSession,
) -> None:
    # Only ONE generator response queued: the second spec's generate call
    # exhausts ScriptedLLMClient, which raises RuntimeError -- simulating an
    # unhandled provider error mid-batch (an insufficient_quota, a killed
    # process). With commit_after_each_spec=True, the FIRST spec's publish
    # must already be durably committed before that crash.
    generator_client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])
    gate_client = ScriptedLLMClient(_stb_gate_responses())

    with pytest.raises(RuntimeError, match="exhausted"):
        await run_batch(
            db_session,
            2,
            generator_client=generator_client,
            gate_client=gate_client,
            generator_model="generator-model-placeholder",
            specs=[_STB_SPEC, _STB_SPEC_2],
            seed_history_from_db=False,
            commit_after_each_spec=True,
        )

    # A fresh query on the same session proves the row is committed, not just
    # pending in this session's identity map -- rollback() would not undo it.
    await db_session.rollback()
    hashes = await fetch_dedup_pool_hashes(db_session)
    from pipeline import dedup

    assert dedup.content_hash(_GOOD_STB_JSON["buggy_code"]) in hashes

    await db_session.execute(delete(Exercise).where(Exercise.status == "in_review"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_run_batch_without_commit_after_each_spec_is_rolled_back_by_fixture_teardown(
    db_session: AsyncSession,
) -> None:
    # Sanity check that the default (commit_after_each_spec=False) preserves
    # the existing test-isolation behavior every other M3 orchestrator test
    # relies on -- nothing here needs manual cleanup.
    generator_client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])
    gate_client = ScriptedLLMClient(_stb_gate_responses())

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
    )

    assert report.counts["published_in_review"] == 1
