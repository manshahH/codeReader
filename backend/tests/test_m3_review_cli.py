from __future__ import annotations

import pytest
from pipeline.publish import insert_candidate
from pipeline.review_cli import cmd_approve, cmd_fix, cmd_kill, cmd_list, cmd_show
from pipeline.schemas import (
    Choice,
    TraceCandidate,
    TraceDraftExplanation,
    TraceSelfCheck,
    TraceTableEntry,
    WhyWrong,
)
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy.ext.asyncio import AsyncSession


def _spec() -> ExerciseSpec:
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


def _candidate() -> TraceCandidate:
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


@pytest.mark.asyncio
async def test_review_cli_list_shows_in_review_candidates(db_session: AsyncSession) -> None:
    exercise = await insert_candidate(
        db_session,
        _spec(),
        _candidate(),
        final_explanation={"summary": "s"},
        content_hash="abc123",
        validation_report={"template_id": "trace_py_v1"},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )

    queue = await cmd_list(db_session)

    assert any(e.id == exercise.id and e.version == exercise.version for e in queue)


@pytest.mark.asyncio
async def test_review_cli_show_returns_full_receipts(db_session: AsyncSession) -> None:
    exercise = await insert_candidate(
        db_session,
        _spec(),
        _candidate(),
        final_explanation={"summary": "s"},
        content_hash="abc123",
        validation_report={"template_id": "trace_py_v1"},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )

    shown = await cmd_show(db_session, exercise.id, exercise.version)

    assert shown is not None
    assert shown.validation_report_url == exercise.validation_report_url


@pytest.mark.asyncio
async def test_review_cli_approve_writes_live_row_with_report_set(db_session: AsyncSession) -> None:
    exercise = await insert_candidate(
        db_session,
        _spec(),
        _candidate(),
        final_explanation={"summary": "s"},
        content_hash="abc123",
        validation_report={"template_id": "trace_py_v1"},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )

    approved = await cmd_approve(db_session, exercise.id, exercise.version)

    assert approved.status == "live"
    assert approved.validation_report_url is not None


@pytest.mark.asyncio
async def test_review_cli_kill_does_not_go_live(db_session: AsyncSession) -> None:
    exercise = await insert_candidate(
        db_session,
        _spec(),
        _candidate(),
        final_explanation={"summary": "s"},
        content_hash="abc123",
        validation_report={"template_id": "trace_py_v1"},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )

    killed = await cmd_kill(db_session, exercise.id, exercise.version)

    assert killed.status == "retired"
    assert killed.status != "live"


@pytest.mark.asyncio
async def test_review_cli_fix_bumps_version(db_session: AsyncSession) -> None:
    exercise = await insert_candidate(
        db_session,
        _spec(),
        _candidate(),
        final_explanation={"summary": "s"},
        content_hash="abc123",
        validation_report={"template_id": "trace_py_v1"},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )

    bumped = await cmd_fix(
        db_session,
        exercise.id,
        exercise.version,
        {"explanation": {"summary": "fixed summary"}},
    )

    assert bumped.version == exercise.version + 1
    assert bumped.explanation["summary"] == "fixed summary"
