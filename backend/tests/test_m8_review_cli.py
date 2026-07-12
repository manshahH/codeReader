"""review_cli at 200-exercise scale (CLAUDE.md M8 part 2):

- `list` shows a per-row quality summary (gate verdicts, solver confidence,
  flags) so a reviewer can triage before opening anything.
- `show` prints the full exercise a reviewer needs: code, answer options,
  the sandbox-verified answer key, explanation, and validation receipts.
- `packet` exports every pending exercise to one markdown file.
"""

from __future__ import annotations

import pytest
from pipeline.publish import insert_candidate
from pipeline.review_cli import (
    build_review_packet,
    cmd_list,
    cmd_packet,
    format_exercise_markdown,
    load_validation_report,
    quality_flags,
    quality_summary,
)
from pipeline.schemas import (
    Choice,
    ReasonOption,
    STBCandidate,
    STBDraftExplanation,
    STBSelfCheck,
    TraceCandidate,
    TraceDraftExplanation,
    TraceSelfCheck,
    TraceTableEntry,
    WhyWrong,
)
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy.ext.asyncio import AsyncSession


def _stb_spec() -> ExerciseSpec:
    return ExerciseSpec(
        type="spot_the_bug",
        concept="aliasing-vs-copy",
        difficulty=3,
        domain="checkout service",
        line_budget_min=1,
        line_budget_max=20,
        has_bug=True,
        avoid_patterns=(),
    )


def _stb_candidate() -> STBCandidate:
    return STBCandidate(
        buggy_code="def f(prices):\n    updated = prices\n    return updated\n",
        fixed_code="def f(prices):\n    updated = dict(prices)\n    return updated\n",
        bug_lines=[2],
        test_code="assert f({'a': 1}) == {'a': 1}\n",
        context_note="Runs in checkout.",
        reason_options=[
            ReasonOption(id="a", text="aliasing"),
            ReasonOption(id="b", text="wrong"),
            ReasonOption(id="c", text="wrong"),
            ReasonOption(id="d", text="wrong"),
        ],
        correct_reason_id="a",
        draft_explanation=STBDraftExplanation(
            summary="updated aliases prices.",
            principle="Copy before mutating.",
            line_notes=[{"line": 2, "note": "binds to the same dict"}],
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


def _trace_spec() -> ExerciseSpec:
    return ExerciseSpec(
        type="trace",
        concept="control_flow",
        difficulty=1,
        domain="checkout service",
        line_budget_min=1,
        line_budget_max=10,
        has_bug=None,
        avoid_patterns=(),
    )


def _trace_candidate() -> TraceCandidate:
    return TraceCandidate(
        code="print(sum([1, 2, 3]))\n",
        context_note="note.",
        question="What does this code print?",
        expected_stdout="6",
        choices=[
            Choice(id="a", text="6", misconception=None),
            Choice(id="b", text="5", misconception="m1"),
            Choice(id="c", text="1", misconception="m2"),
            Choice(id="d", text="0", misconception="m3"),
        ],
        correct_choice_id="a",
        draft_explanation=TraceDraftExplanation(
            summary="sum([1, 2, 3]) prints 6.",
            principle="sum() folds left to right.",
            trace_table=[TraceTableEntry(line=1, state="n/a")],
            why_wrong=[
                WhyWrong(choice_id="b", note="m1"),
                WhyWrong(choice_id="c", note="m2"),
                WhyWrong(choice_id="d", note="m3"),
            ],
        ),
        concepts=["control_flow"],
        self_difficulty=1,
        self_check=TraceSelfCheck(
            traced_line_by_line_not_from_memory=True,
            output_deterministic_and_repr_stable=True,
            each_distractor_derived_from_named_misconception=True,
            no_two_choices_identical=True,
        ),
    )


_CLEAN_VALIDATION_REPORT = {
    "template_id": "stb_py_v2",
    "static_gate": {"accepted": True, "violations": []},
    "sandbox_gate": {
        "accepted": True,
        "checks": [
            {"name": "buggy_fails_test", "passed": True, "detail": ""},
            {"name": "fixed_passes_test", "passed": True, "detail": ""},
        ],
        "captured_stdout": None,
        "verified_bug_lines": [2],
        "bug_lines_claim_mismatch": False,
    },
    "defect_audit": {"verdict": "pass", "detail": "one defect", "raw": {"defects": []}},
    "solver": {"verdict": "pass", "detail": "solved it", "raw": {"confidence": 0.95}},
    "reasons": {"verdict": "pass", "detail": "all correct", "raw": {}},
    "explanation": {"mismatch_flagged": False, "mismatch_detail": None},
}

_FLAGGED_VALIDATION_REPORT = {
    **_CLEAN_VALIDATION_REPORT,
    "sandbox_gate": {**_CLEAN_VALIDATION_REPORT["sandbox_gate"], "bug_lines_claim_mismatch": True},
    "solver": {"verdict": "flag", "detail": "uncertain", "raw": {"confidence": 0.4}},
    "explanation": {"mismatch_flagged": True, "mismatch_detail": "draft never mentions line 2"},
}


async def _insert_stb_with_report(
    session: AsyncSession,
    *,
    validation_report: dict,
    content_hash: str = "abc123",
):
    return await insert_candidate(
        session,
        _stb_spec(),
        _stb_candidate(),
        final_explanation={
            "summary": "s",
            "principle": "p",
            "line_notes": [{"line": 2, "note": "n"}],
            "mismatch_flagged": validation_report["explanation"]["mismatch_flagged"],
            "mismatch_detail": validation_report["explanation"]["mismatch_detail"],
        },
        content_hash=content_hash,
        validation_report=validation_report,
        generator_model="generator-model-placeholder",
        verified_bug_lines=[2],
    )


async def _insert_trace(session: AsyncSession):
    return await insert_candidate(
        session,
        _trace_spec(),
        _trace_candidate(),
        final_explanation={"summary": "sum prints 6.", "principle": "p"},
        content_hash="trace-hash-1",
        validation_report={
            "template_id": "trace_py_v1",
            "sandbox_gate": {"accepted": True, "checks": [], "captured_stdout": "6"},
            "solver": {"verdict": "pass", "detail": "ok", "raw": {"confidence": 0.9}},
            "explanation": {"mismatch_flagged": False, "mismatch_detail": None},
        },
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )


@pytest.mark.asyncio
async def test_quality_summary_reports_clean_for_a_fully_passing_report(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert_stb_with_report(db_session, validation_report=_CLEAN_VALIDATION_REPORT)

    summary = quality_summary(exercise)

    assert "clean" in summary
    assert "solver_confidence=0.95" in summary


@pytest.mark.asyncio
async def test_quality_flags_surfaces_claim_mismatch_and_flagged_gate(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert_stb_with_report(
        db_session,
        validation_report=_FLAGGED_VALIDATION_REPORT,
        content_hash="flagged-hash",
    )

    report = load_validation_report(exercise)
    flags = quality_flags(report)

    assert "bug_lines_claim_mismatch" in flags
    assert "explanation_mismatch" in flags
    assert "solver=flag" in flags


def test_quality_flags_none_report_is_itself_a_flag() -> None:
    assert quality_flags(None) == ["no_validation_report"]


@pytest.mark.asyncio
async def test_format_exercise_markdown_includes_code_answer_key_and_receipts(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert_stb_with_report(db_session, validation_report=_CLEAN_VALIDATION_REPORT)

    markdown = format_exercise_markdown(exercise)

    assert "def f(prices):" in markdown  # the code itself
    assert "correct_lines: [2]" in markdown  # the verified answer key
    assert "correct_reason_id: a" in markdown
    assert "assert f({'a': 1})" in markdown  # the failing-test proof
    assert "buggy_fails_test" in markdown  # sandbox check receipts
    assert "**solver**: pass" in markdown  # semantic gate verdicts
    assert "- summary: s" in markdown  # explanation summary


@pytest.mark.asyncio
async def test_format_exercise_markdown_trace_includes_captured_stdout(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert_trace(db_session)

    markdown = format_exercise_markdown(exercise)

    assert "print(sum([1, 2, 3]))" in markdown
    assert "captured_stdout: '6'" in markdown
    # C1: the correct choice is shuffled at publish time, so it is no longer
    # always "a" -- assert the receipt shows whatever id the shuffle landed on.
    assert f"correct_choice_id: {exercise.grading['correct_choice_id']}" in markdown


@pytest.mark.asyncio
async def test_cmd_packet_bundles_every_pending_exercise_into_one_markdown_file(
    db_session: AsyncSession,
) -> None:
    stb = await _insert_stb_with_report(db_session, validation_report=_CLEAN_VALIDATION_REPORT)
    trace = await _insert_trace(db_session)

    packet = await cmd_packet(db_session, limit=50)

    assert f"{stb.id}" in packet
    assert f"{trace.id}" in packet
    assert "## Contents" in packet
    assert packet.count("### spot_the_bug") + packet.count("### trace") == 2


@pytest.mark.asyncio
async def test_build_review_packet_toc_lists_quality_summary_per_exercise(
    db_session: AsyncSession,
) -> None:
    await _insert_stb_with_report(db_session, validation_report=_FLAGGED_VALIDATION_REPORT)

    exercises = await cmd_list(db_session)
    packet = build_review_packet(exercises)

    assert "FLAGS:" in packet


def test_load_validation_report_returns_none_for_missing_file() -> None:
    from app.models import Exercise

    exercise = Exercise(
        id=None,
        version=1,
        language="python",
        type="trace",
        grading_mode="deterministic",
        difficulty_authored=1,
        concepts=["control_flow"],
        tags=[],
        status="in_review",
        source={},
        payload={},
        grading={},
        explanation={},
        validation_report_url="/definitely/does/not/exist.json",
        human_reviewed=False,
    )

    assert load_validation_report(exercise) is None
