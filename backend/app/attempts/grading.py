"""Deterministic grading for spot_the_bug and trace (docs/05 section 5).

Ground truth is whatever the pipeline's sandbox execution verified (D-9);
this module only compares the submitted answer against exercise.grading,
never re-derives correctness itself.
"""

from __future__ import annotations

from typing import Any

from app.models import Exercise
from app.schemas.attempts import (
    LineNote,
    PredictTheFixExplanation,
    PredictTheFixReveal,
    STBExplanation,
    STBReveal,
    TraceExplanation,
    TraceReveal,
    TraceTableEntry,
    WhyWrongEntry,
)

# predict_the_fix (D-80) grades exactly like trace: a single choice_id compared
# against the sandbox-verified correct choice (the choice whose code is the
# execution-proven fixed_code). No LLM grading, no rubric.
DETERMINISTIC_TYPES = ("spot_the_bug", "trace", "predict_the_fix")


class AnswerShapeError(ValueError):
    pass


class UnsupportedExerciseTypeError(ValueError):
    pass


def is_skip_answer(answer: dict[str, Any]) -> bool:
    """D-93: the one honest-skip shape, {"skipped": true} exactly -- same
    strict-key-set discipline as every other answer shape, so a stray extra
    key can't smuggle a skip past validation."""
    return set(answer) == {"skipped"} and answer.get("skipped") is True


def validate_answer_shape(exercise_type: str, answer: dict[str, Any]) -> None:
    if exercise_type == "spot_the_bug":
        if is_skip_answer(answer):
            return
        if set(answer) != {"line", "reason_id"}:
            raise AnswerShapeError("spot_the_bug answer requires exactly {line, reason_id}")
        line_ok = isinstance(answer.get("line"), int)
        reason_ok = isinstance(answer.get("reason_id"), str)
        if not line_ok or not reason_ok:
            raise AnswerShapeError("spot_the_bug answer needs an int line and a string reason_id")
    elif exercise_type in ("trace", "predict_the_fix"):
        if is_skip_answer(answer):
            return
        if set(answer) != {"choice_id"}:
            raise AnswerShapeError(f"{exercise_type} answer requires exactly {{choice_id}}")
        if not isinstance(answer.get("choice_id"), str):
            raise AnswerShapeError(f"{exercise_type} answer requires a string choice_id")
    else:
        raise UnsupportedExerciseTypeError(
            f"deterministic grading does not support exercise type {exercise_type!r}",
        )


def grade_spot_the_bug(answer: dict[str, Any], grading: dict[str, Any]) -> bool:
    return answer["line"] in grading.get("correct_lines", []) and answer[
        "reason_id"
    ] == grading.get("correct_reason_id")


def grade_trace(answer: dict[str, Any], grading: dict[str, Any]) -> bool:
    return grade_choice(answer, grading)


def grade_choice(answer: dict[str, Any], grading: dict[str, Any]) -> bool:
    return answer["choice_id"] == grading.get("correct_choice_id")


def grade_deterministic(exercise: Exercise, answer: dict[str, Any]) -> bool | None:
    """Returns None for an honest skip -- short-circuits before touching
    answer["line"]/answer["choice_id"], which a {"skipped": true} answer
    never carries. None here is never mistaken for "still grading": callers
    key off status="skipped" (attempts/service.py), not this return value
    alone, to tell a skip apart from a rubric attempt still pending (D-93)."""
    if is_skip_answer(answer):
        return None
    if exercise.type == "spot_the_bug":
        return grade_spot_the_bug(answer, exercise.grading)
    if exercise.type in ("trace", "predict_the_fix"):
        return grade_choice(answer, exercise.grading)
    raise UnsupportedExerciseTypeError(
        f"deterministic grading does not support exercise type {exercise.type!r}",
    )


def build_reveal(exercise: Exercise) -> STBReveal | TraceReveal | PredictTheFixReveal:
    explanation = exercise.explanation
    grading = exercise.grading

    if exercise.type == "spot_the_bug":
        return STBReveal(
            correct_lines=list(grading.get("correct_lines", [])),
            correct_reason_id=grading.get("correct_reason_id"),
            explanation=STBExplanation(
                summary=explanation.get("summary", ""),
                principle=explanation.get("principle", ""),
                line_notes=[LineNote(**note) for note in explanation.get("line_notes", [])],
            ),
        )
    if exercise.type == "trace":
        return TraceReveal(
            correct_choice_id=grading.get("correct_choice_id"),
            explanation=TraceExplanation(
                summary=explanation.get("summary", ""),
                principle=explanation.get("principle", ""),
                trace_table=[TraceTableEntry(**e) for e in explanation.get("trace_table", [])],
                why_wrong=[WhyWrongEntry(**e) for e in explanation.get("why_wrong", [])],
            ),
        )
    if exercise.type == "predict_the_fix":
        return PredictTheFixReveal(
            correct_choice_id=grading.get("correct_choice_id"),
            explanation=PredictTheFixExplanation(
                summary=explanation.get("summary", ""),
                principle=explanation.get("principle", ""),
                why_wrong=[WhyWrongEntry(**e) for e in explanation.get("why_wrong", [])],
            ),
        )
    raise UnsupportedExerciseTypeError(
        f"deterministic grading does not support exercise type {exercise.type!r}",
    )
