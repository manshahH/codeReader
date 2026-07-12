"""predict_the_fix (D-80) and the per-type STB generator routing (D-80).

The sandbox-gate invariant (a distractor must STILL FAIL the test) is proven in
test_m3_sandbox.py against real Docker; this file covers the derivation flow
(generate -> assemble), the orchestrator integration (an STB survivor spawns a
predict_the_fix), the STB generator-model routing, and the backend grading /
serving path (deterministic choice grading, allowlist serialization).
"""

from __future__ import annotations

import json
import random
import uuid

import pytest
from pipeline.llm_client import ScriptedLLMClient
from pipeline.orchestrator import run_batch
from pipeline.predict_the_fix import derive_artifacts, generate_wrong_fixes
from pipeline.schemas import (
    LineNote,
    PredictFixCandidate,
    ReasonOption,
    STBCandidate,
    STBDraftExplanation,
    STBSelfCheck,
)
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.grading import (
    build_reveal,
    grade_deterministic,
    validate_answer_shape,
)
from app.models import Exercise
from app.schemas.attempts import PredictTheFixReveal
from app.sessions.service import _serialize_payload

# --- the aliasing bug reused across pipeline layers --------------------------

_BUGGY = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_FIXED = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_TEST = (
    "prices = {'A1': 100.0, 'B2': 50.0}\n"
    "result = apply_discount(prices, 10)\n"
    "assert result == {'A1': 90.0, 'B2': 45.0}\n"
    "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n"
)

# Three plausible wrong fixes, each STILL failing the strong test above.
_WRONG_A = (  # still aliases -> mutates the input dict (second assert fails)
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in list(updated):\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_WRONG_B = (  # returns a copy but mutated the caller's dict along the way
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return dict(updated)\n"
)
_WRONG_C = (  # copies (no mutation) but applies the discount the wrong way
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 + discount_pct / 100), 2)\n"
    "    return updated\n"
)

_STB_CANDIDATE = STBCandidate(
    buggy_code=_BUGGY,
    fixed_code=_FIXED,
    bug_lines=[2],
    test_code=_TEST,
    context_note="Runs once per order in the checkout worker.",
    reason_options=[
        ReasonOption(id="a", text="The input dict is mutated in place via aliasing."),
        ReasonOption(id="b", text="round() drifts here."),
        ReasonOption(id="c", text="The loop skips the last SKU."),
        ReasonOption(id="d", text="The discount is applied twice."),
    ],
    correct_reason_id="a",
    draft_explanation=STBDraftExplanation(
        summary="updated = prices aliases the caller's dict instead of copying it.",
        principle="Copy a mutable argument before mutating it in place.",
        line_notes=[LineNote(line=2, note="binds updated to the same dict as prices")],
    ),
    concepts=["aliasing-vs-copy"],
    self_difficulty=3,
    self_check=STBSelfCheck(
        single_bug_confirmed=True,
        runs_without_error_on_happy_path=True,
        no_hinting_names_or_comments=True,
        distractors_verifiably_wrong=True,
    ),
)

_WRONG_FIXES = PredictFixCandidate(
    wrong_fixes=[
        {"code": _WRONG_A, "note": "still aliases and mutates the caller's dict"},
        {"code": _WRONG_B, "note": "returns a copy but mutated the input first"},
        {"code": _WRONG_C, "note": "applies the discount in the wrong direction"},
    ],
)


# --- generate_wrong_fixes: parse policy -------------------------------------


def test_generate_wrong_fixes_parses_clean_json() -> None:
    client = ScriptedLLMClient([_WRONG_FIXES.model_dump_json()])

    candidate, discard = generate_wrong_fixes(
        buggy_code=_BUGGY,
        fixed_code=_FIXED,
        test_code=_TEST,
        concept="aliasing-vs-copy",
        domain="checkout service",
        llm_client=client,
    )

    assert discard is None
    assert candidate is not None
    assert len(candidate.wrong_fixes) == 3
    # the STB artifacts are actually injected into the prompt
    assert _BUGGY in client.calls[0]["user"]
    assert _TEST in client.calls[0]["user"]


def test_generate_wrong_fixes_returns_none_on_abort() -> None:
    client = ScriptedLLMClient([json.dumps({"abort": True, "reason": "cannot"})])

    candidate, discard = generate_wrong_fixes(
        buggy_code=_BUGGY,
        fixed_code=_FIXED,
        test_code=_TEST,
        concept="aliasing-vs-copy",
        domain="checkout service",
        llm_client=client,
    )

    assert candidate is None
    assert discard is not None and discard.startswith("generator_aborted")


# --- derive_artifacts: sandbox-grounded assembly (real Docker) --------------


def test_derive_artifacts_assembles_choices_with_the_verified_fix_as_correct() -> None:
    outcome = derive_artifacts(
        stb_candidate=_STB_CANDIDATE,
        wrong_fixes=_WRONG_FIXES,
        rng=random.Random(0),
        line_budget_max=20,
    )

    assert outcome.survived, outcome.validation_report
    artifacts = outcome.artifacts
    assert artifacts is not None
    # exactly 4 choices, and the correct one's code is the execution-proven fix.
    choices = artifacts.payload["choices"]
    assert len(choices) == 4
    correct = next(c for c in choices if c["id"] == artifacts.correct_choice_id)
    assert correct["text"] == _FIXED
    # grading points at that same choice; 3 why-wrong notes cover the distractors.
    assert artifacts.grading["correct_choice_id"] == artifacts.correct_choice_id
    assert len(artifacts.explanation["why_wrong"]) == 3
    # the payload never leaks the answer key.
    assert "correct_choice_id" not in artifacts.payload
    assert artifacts.payload["failing_test"] == _TEST
    assert "AssertionError" in artifacts.payload["test_output"]


def test_derive_artifacts_rejects_when_a_distractor_actually_passes_the_test() -> None:
    # One "wrong" fix IS the correct fix -> it passes the test -> not a valid
    # distractor -> the whole predict_the_fix is rejected.
    bad = PredictFixCandidate(
        wrong_fixes=[
            {"code": _WRONG_A, "note": "n"},
            {"code": _FIXED, "note": "actually correct"},
            {"code": _WRONG_C, "note": "n"},
        ],
    )

    outcome = derive_artifacts(
        stb_candidate=_STB_CANDIDATE,
        wrong_fixes=bad,
        rng=random.Random(0),
        line_budget_max=20,
    )

    assert not outcome.survived
    assert outcome.reject_stage == "ptf_sandbox_gate"


# --- orchestrator integration: an STB survivor spawns a predict_the_fix ------

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
_DEFECT_AUDIT = json.dumps(
    {"defects": [{"lines": [2], "description": "aliasing", "exposed_by": "mutation test"}]},
)
_STB_SOLVER = json.dumps(
    {"answer": {"line": 2, "reason_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
)
_REASONS = json.dumps(
    {
        "verdicts": [
            {"id": "a", "classification": "correct", "justification": "j"},
            {"id": "b", "classification": "wrong", "justification": "j"},
            {"id": "c", "classification": "wrong", "justification": "j"},
            {"id": "d", "classification": "wrong", "justification": "j"},
        ],
    },
)


@pytest.mark.asyncio
async def test_run_batch_derives_a_predict_the_fix_from_a_published_stb(
    db_session: AsyncSession,
) -> None:
    generator_client = ScriptedLLMClient(
        [_STB_CANDIDATE.model_dump_json(), _WRONG_FIXES.model_dump_json()],
    )
    gate_client = ScriptedLLMClient([_DEFECT_AUDIT, _STB_SOLVER, _REASONS])

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
        derive_predict_the_fix=True,
    )

    assert report.counts["published_in_review"] == 1
    assert report.counts["ptf_published_in_review"] == 1
    assert len(report.ptf_published) == 1

    ptf = (
        await db_session.scalars(
            select(Exercise).where(Exercise.type == "predict_the_fix"),
        )
    ).one()
    assert ptf.grading_mode == "deterministic"
    assert ptf.source["derived_from"]["id"] is not None
    correct_id = ptf.grading["correct_choice_id"]
    correct_choice = next(c for c in ptf.payload["choices"] if c["id"] == correct_id)
    assert correct_choice["text"] == _FIXED


@pytest.mark.asyncio
async def test_run_batch_default_does_not_derive_predict_the_fix(
    db_session: AsyncSession,
) -> None:
    # Off by default: the scripted client queues only the STB primary path, so
    # no extra wrong-fix call is made and no predict_the_fix row is created.
    generator_client = ScriptedLLMClient([_STB_CANDIDATE.model_dump_json()])
    gate_client = ScriptedLLMClient([_DEFECT_AUDIT, _STB_SOLVER, _REASONS])

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
    assert report.counts["ptf_published_in_review"] == 0
    assert report.ptf_published == []


@pytest.mark.asyncio
async def test_run_batch_writes_a_reject_report_when_ptf_derivation_is_rejected(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # D-89: a rejected predict_the_fix derivation used to vanish into a bare
    # counter increment -- ptf.validation_report (the sandbox's per-check
    # detail) was thrown away. It must now land on disk via the SAME
    # write_reject_report machinery the STB path already uses. One wrong fix
    # here IS the correct fix (_FIXED), so it passes the test -- not a valid
    # distractor -- which the ptf_sandbox_gate correctly rejects.
    from pipeline.config import PipelineSettings

    settings = PipelineSettings(VALIDATION_REPORTS_DIR=str(tmp_path))
    monkeypatch.setattr("pipeline.publish.get_pipeline_settings", lambda: settings)

    bad_wrong_fixes = PredictFixCandidate(
        wrong_fixes=[
            {"code": _WRONG_A, "note": "still aliases and mutates the caller's dict"},
            {"code": _FIXED, "note": "actually correct"},
            {"code": _WRONG_C, "note": "applies the discount in the wrong direction"},
        ],
    )
    generator_client = ScriptedLLMClient(
        [_STB_CANDIDATE.model_dump_json(), bad_wrong_fixes.model_dump_json()],
    )
    gate_client = ScriptedLLMClient([_DEFECT_AUDIT, _STB_SOLVER, _REASONS])

    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
        derive_predict_the_fix=True,
    )

    assert report.counts["published_in_review"] == 1
    assert report.counts["ptf_published_in_review"] == 0
    assert report.counts["ptf_sandbox_gate_rejected"] == 1
    assert report.counts["concept:aliasing-vs-copy:ptf_rejected"] == 1

    reject_files = sorted(
        (tmp_path / "rejects").glob("ptf_sandbox_gate_aliasing-vs-copy_*.json"),
    )
    assert len(reject_files) == 1
    payload = json.loads(reject_files[0].read_text(encoding="utf-8"))
    assert payload["stage"] == "ptf_sandbox_gate"
    assert payload["spec"]["concept"] == "aliasing-vs-copy"
    assert payload["candidate"]["buggy_code"] == _BUGGY
    assert payload["candidate"]["fixed_code"] == _FIXED
    assert any(w["code"] == _FIXED for w in payload["candidate"]["wrong_fixes"])
    checks = {c["name"]: c["passed"] for c in payload["sandbox_gate"]["checks"]}
    assert checks["distractor_1_still_fails_test"] is False


# --- D-80: per-type STB generator routing -----------------------------------

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
_GOOD_TRACE = {
    "code": "values = [1, 2, 3]\nprint(sum(values))\n",
    "context_note": "Runs in the nightly reconciliation job.",
    "question": "What does this code print?",
    "expected_stdout": "6",
    "choices": [
        {"id": "a", "text": "6", "misconception": None},
        {"id": "b", "text": "5", "misconception": "miscounted"},
        {"id": "c", "text": "1", "misconception": "stopped early"},
        {"id": "d", "text": "0", "misconception": "assumed start 1"},
    ],
    "correct_choice_id": "a",
    "draft_explanation": {
        "summary": "sum() adds 1 + 2 + 3 to print 6.",
        "principle": "sum() folds left to right.",
        "trace_table": [{"line": 2, "state": "values=[1, 2, 3]"}],
        "why_wrong": [
            {"choice_id": "b", "note": "miscounted"},
            {"choice_id": "c", "note": "stopped early"},
            {"choice_id": "d", "note": "assumed start 1"},
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
_TRACE_SOLVER = json.dumps(
    {"answer": {"choice_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
)


@pytest.mark.asyncio
async def test_run_batch_routes_only_stb_generation_to_the_override_client(
    db_session: AsyncSession,
) -> None:
    base_generator = ScriptedLLMClient([json.dumps(_GOOD_TRACE)])
    stb_generator = ScriptedLLMClient([_STB_CANDIDATE.model_dump_json()])
    gate_client = ScriptedLLMClient([_DEFECT_AUDIT, _STB_SOLVER, _REASONS, _TRACE_SOLVER])

    report = await run_batch(
        db_session,
        2,
        generator_client=base_generator,
        gate_client=gate_client,
        generator_model="base-generator",
        specs=[_STB_SPEC, _TRACE_SPEC],
        seed_history_from_db=False,
        stb_generator_client=stb_generator,
        stb_generator_model="stb-override-generator",
    )

    assert report.counts["published_in_review"] == 2
    # STB generation went to the override; trace generation went to the base.
    assert len(stb_generator.calls) == 1
    assert 'Create one "spot the bug" exercise.' in stb_generator.calls[0]["user"]
    assert len(base_generator.calls) == 1
    assert 'Create one "trace the output" exercise.' in base_generator.calls[0]["user"]

    stb_row = (
        await db_session.scalars(
            select(Exercise).where(Exercise.type == "spot_the_bug"),
        )
    ).one()
    assert stb_row.source["model"] == "stb-override-generator"


# --- backend: deterministic grading + allowlist serialization ---------------


def _ptf_exercise() -> Exercise:
    return Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="predict_the_fix",
        grading_mode="deterministic",
        difficulty_authored=3,
        concepts=["aliasing-vs-copy"],
        tags=[],
        status="live",
        source={"origin": "llm"},
        payload={
            "code": _BUGGY,
            "context_note": "note.",
            "question": "Which change makes the test pass?",
            "failing_test": _TEST,
            "test_output": "AssertionError: input dict was mutated",
            "answer_mode": "choose_fix",
            "choices": [
                {"id": "a", "text": _WRONG_A},
                {"id": "b", "text": _FIXED},
                {"id": "c", "text": _WRONG_C},
                {"id": "d", "text": _WRONG_B},
            ],
        },
        grading={"mode": "deterministic", "correct_choice_id": "b"},
        explanation={
            "summary": "s",
            "principle": "p",
            "why_wrong": [
                {"choice_id": "a", "note": "still aliases"},
                {"choice_id": "c", "note": "wrong direction"},
                {"choice_id": "d", "note": "mutated first"},
            ],
        },
        validation_report_url=None,
        human_reviewed=True,
    )


def test_predict_the_fix_answer_shape_validation() -> None:
    validate_answer_shape("predict_the_fix", {"choice_id": "b"})
    with pytest.raises(Exception):  # noqa: B017, PT011 -- AnswerShapeError
        validate_answer_shape("predict_the_fix", {"line": 2, "reason_id": "a"})


def test_predict_the_fix_grades_deterministically_by_choice_id() -> None:
    exercise = _ptf_exercise()
    assert grade_deterministic(exercise, {"choice_id": "b"}) is True
    assert grade_deterministic(exercise, {"choice_id": "a"}) is False


def test_predict_the_fix_build_reveal_returns_the_verified_choice_and_notes() -> None:
    reveal = build_reveal(_ptf_exercise())
    assert isinstance(reveal, PredictTheFixReveal)
    assert reveal.correct_choice_id == "b"
    assert {w.choice_id for w in reveal.explanation.why_wrong} == {"a", "c", "d"}


def test_predict_the_fix_serialized_payload_never_leaks_the_answer_key() -> None:
    payload = _serialize_payload(_ptf_exercise())
    dumped = payload.model_dump()
    assert "correct_choice_id" not in dumped
    assert dumped["failing_test"] == _TEST
    assert dumped["test_output"].startswith("AssertionError")
    # choices carry only id + text, never a note/misconception tag.
    assert all(set(c) == {"id", "text"} for c in dumped["choices"])
