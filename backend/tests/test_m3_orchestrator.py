from __future__ import annotations

import json

import pytest
from pipeline.llm_client import ScriptedLLMClient
from pipeline.orchestrator import run_batch
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise

# Explicit specs (rather than rng-sampled ones) so the fixture candidates'
# fixed line counts always satisfy the line budget -- sample_spec ties budget
# to a randomly sampled difficulty, which would otherwise make this fragile.
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

_GOOD_TRACE_JSON = {
    "code": "values = [1, 2, 3]\nprint(sum(values))\n",
    "context_note": "Runs in the nightly reconciliation job.",
    "question": "What does this code print?",
    "expected_stdout": "6",
    "choices": [
        {"id": "a", "text": "6", "misconception": None},
        {"id": "b", "text": "5", "misconception": "miscounted the list length"},
        {"id": "c", "text": "1", "misconception": "stopped after the first element"},
        {"id": "d", "text": "0", "misconception": "believed sum() needs an explicit start of 1"},
    ],
    "correct_choice_id": "a",
    "draft_explanation": {
        "summary": "sum() adds 1 + 2 + 3 to print 6.",
        "principle": "sum() folds left to right over the iterable.",
        "trace_table": [{"line": 2, "state": "values=[1, 2, 3]"}],
        "why_wrong": [
            {"choice_id": "b", "note": "miscounted the list length"},
            {"choice_id": "c", "note": "stopped after the first element"},
            {"choice_id": "d", "note": "believed sum() needs an explicit start of 1"},
        ],
    },
    "concepts": ["control_flow"],
    "self_difficulty": 1,
    "self_check": {
        "traced_line_by_line_not_from_memory": True,
        "output_deterministic_and_repr_stable": True,
        "each_distractor_derived_from_named_misconception": True,
        "no_two_choices_identical": True,
    },
}

_DEFECT_AUDIT_RESPONSE = json.dumps(
    {
        "defects": [
            {
                "lines": [2],
                "description": "aliasing mutates caller's dict",
                "exposed_by": "mutation test",
            },
        ],
    },
)
_STB_SOLVER_RESPONSE = json.dumps(
    {
        "answer": {"line": 2, "reason_id": "a"},
        "confidence": 0.95,
        "problems_with_the_exercise": [],
    },
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
_TRACE_SOLVER_RESPONSE = json.dumps(
    {"answer": {"choice_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
)


@pytest.mark.asyncio
async def test_orchestrator_end_to_end_publishes_all_good_candidates_and_reports_counts(
    db_session: AsyncSession,
) -> None:
    # Two distinct specs (one of each type) rather than 4 with repeats: the
    # orchestrator adds each published candidate's hash to the live pool as it
    # goes, so two IDENTICAL candidates in one batch would (correctly) get
    # the second one rejected as a duplicate of the first.
    generator_client = ScriptedLLMClient(
        [json.dumps(_GOOD_STB_JSON), json.dumps(_GOOD_TRACE_JSON)],
    )
    gate_client = ScriptedLLMClient(
        [_DEFECT_AUDIT_RESPONSE, _STB_SOLVER_RESPONSE, _REASONS_RESPONSE, _TRACE_SOLVER_RESPONSE],
    )

    report = await run_batch(
        db_session,
        2,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC, _TRACE_SPEC],
        seed_history_from_db=False,
    )

    assert report.counts["specs_sampled"] == 2
    assert report.counts["generate_passed"] == 2
    assert report.counts["static_gate_passed"] == 2
    assert report.counts["sandbox_gate_passed"] == 2
    assert report.counts["semantic_gate_passed"] == 2
    assert report.counts["dedup_passed"] == 2
    assert report.counts["published_in_review"] == 2
    assert len(report.published) == 2
    assert report.spec_exhausted == []

    rows = (
        await db_session.scalars(select(Exercise).where(Exercise.status == "in_review"))
    ).all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_orchestrator_exhausts_a_spec_and_records_reject_counts_when_every_attempt_fails(
    db_session: AsyncSession,
) -> None:
    # Every generation call returns unparseable JSON -> 2 llm calls consumed
    # per attempt (1 + the single json-parse retry) x 3 attempts x 1 spec.
    generator_client = ScriptedLLMClient(["not json"] * 6)
    gate_client = ScriptedLLMClient([])

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
    )

    assert report.counts["specs_sampled"] == 1
    assert report.counts["generate_discarded:json_parse_failed"] == 3
    assert report.counts["published_in_review"] == 0
    assert len(report.spec_exhausted) == 1
