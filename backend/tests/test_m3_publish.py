from __future__ import annotations

import pytest
from pipeline.publish import approve, fix_and_bump, insert_candidate, kill
from pipeline.schemas import (
    Choice,
    TraceCandidate,
    TraceDraftExplanation,
    TraceSelfCheck,
    TraceTableEntry,
    WhyWrong,
)
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exercises.service import ExerciseImmutableError
from app.models import Exercise


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


async def _insert(session: AsyncSession) -> Exercise:
    return await insert_candidate(
        session,
        _trace_spec(),
        _trace_candidate(),
        final_explanation={"summary": "s", "verified": {"captured_stdout": "6"}},
        content_hash="deadbeef",
        validation_report={"template_id": "trace_py_v1", "sandbox_gate": {"accepted": True}},
        generator_model="generator-model-placeholder",
        captured_stdout="6",
    )


@pytest.mark.asyncio
async def test_insert_candidate_writes_in_review_row_with_validation_report(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert(db_session)

    assert exercise.status == "in_review"
    assert exercise.human_reviewed is False
    assert exercise.validation_report_url is not None
    # correct choice's text is replaced with the captured stdout
    assert exercise.payload["choices"][0]["text"] == "6"
    assert exercise.source["content_hash"] == "deadbeef"


@pytest.mark.asyncio
async def test_approve_writes_a_live_row(db_session: AsyncSession) -> None:
    exercise = await _insert(db_session)

    approved = await approve(db_session, exercise.id, exercise.version)

    assert approved.status == "live"
    assert approved.human_reviewed is True
    assert approved.published_at is not None


@pytest.mark.asyncio
async def test_kill_sets_retired_and_does_not_go_live(db_session: AsyncSession) -> None:
    exercise = await _insert(db_session)

    killed = await kill(db_session, exercise.id, exercise.version)

    assert killed.status == "retired"


@pytest.mark.asyncio
async def test_fix_and_bump_creates_new_version_and_retires_the_non_live_old_one(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert(db_session)

    bumped = await fix_and_bump(
        db_session,
        exercise.id,
        exercise.version,
        {"explanation": {"summary": "corrected summary"}},
    )

    assert bumped.version == exercise.version + 1
    assert bumped.status == "in_review"
    assert bumped.explanation["summary"] == "corrected summary"

    old = await db_session.get(Exercise, (exercise.id, exercise.version))
    assert old is not None
    assert old.status == "retired"


@pytest.mark.asyncio
async def test_fix_and_bump_of_a_live_exercise_leaves_the_live_row_untouched(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert(db_session)
    await approve(db_session, exercise.id, exercise.version)

    bumped = await fix_and_bump(
        db_session,
        exercise.id,
        exercise.version,
        {"explanation": {"summary": "corrected summary"}},
    )

    assert bumped.version == exercise.version + 1
    old = await db_session.get(Exercise, (exercise.id, exercise.version))
    assert old is not None
    assert old.status == "live"  # never mutated -- exercises_current prefers the new version


@pytest.mark.asyncio
async def test_approve_of_an_already_live_version_is_blocked_by_the_immutability_guard(
    db_session: AsyncSession,
) -> None:
    """approve writes human_reviewed/validated_at/published_at, which are
    content-adjacent columns -- still refused on a live row (D-58 permits
    STATUS transitions only)."""
    exercise = await _insert(db_session)
    await approve(db_session, exercise.id, exercise.version)

    with pytest.raises(ExerciseImmutableError):
        await approve(db_session, exercise.id, exercise.version)


@pytest.mark.asyncio
async def test_kill_of_a_live_version_retires_it(db_session: AsyncSession) -> None:
    """D-58: status is the one field a live row may change -- before, kill()
    on a live exercise raised and there was NO code path to take a bad live
    exercise out of circulation."""
    exercise = await _insert(db_session)
    await approve(db_session, exercise.id, exercise.version)

    killed = await kill(db_session, exercise.id, exercise.version)

    assert killed.status == "retired"


@pytest.mark.asyncio
async def test_exercises_current_view_prefers_the_bumped_live_version(
    db_session: AsyncSession,
) -> None:
    exercise = await _insert(db_session)
    await approve(db_session, exercise.id, exercise.version)
    bumped = await fix_and_bump(
        db_session,
        exercise.id,
        exercise.version,
        {"explanation": {"summary": "v2 summary"}},
    )
    await approve(db_session, exercise.id, bumped.version)

    current = await db_session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise.id)
        .order_by(Exercise.version.desc())
        .limit(1),
    )
    assert current is not None
    assert current.version == bumped.version
    assert current.explanation["summary"] == "v2 summary"
