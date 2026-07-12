"""GET /session/today response shapes (docs/05 section 4).

extra="forbid" everywhere: these are allowlists. `grading` and `explanation`
are structurally absent -- there is no field on any model here that could
carry them, so the CI leak test (invariant 1) has something real to enforce.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.attempts import (
    PredictTheFixReveal,
    STBReveal,
    SummarizeReveal,
    TraceReveal,
)

_STRICT = ConfigDict(extra="forbid")


class ReasonOption(BaseModel):
    model_config = _STRICT

    id: str
    text: str


class TraceChoice(BaseModel):
    model_config = _STRICT

    id: str
    text: str


class SessionExercisePayload(BaseModel):
    model_config = _STRICT

    code: str
    context_note: str
    answer_mode: str | None = None
    reason_options: list[ReasonOption] | None = None
    question: str | None = None
    choices: list[TraceChoice] | None = None
    max_words: int | None = None
    # predict_the_fix (D-80): the failing test and its captured output shown to
    # the user; `choices` carries the candidate fixes (id + code), same allowlist
    # shape as trace choices (no answer key leaks -- correct_choice_id lives in
    # grading, never here).
    failing_test: str | None = None
    test_output: str | None = None


class SessionExercise(BaseModel):
    model_config = _STRICT

    slot: int
    exercise_id: uuid.UUID
    version: int
    type: Literal["spot_the_bug", "trace", "summarize", "predict_the_fix"]
    concepts: list[str]
    language: str
    difficulty_band: Literal["easy", "medium", "hard", "boss"]
    est_time_s: int
    is_boss: bool
    attempted: bool
    payload: SessionExercisePayload


class SessionResponse(BaseModel):
    model_config = _STRICT

    session_date: dt.date
    completed: bool
    exercises: list[SessionExercise]


class SessionReviewExercise(BaseModel):
    """"Review today's session" (D-93d): only exercises the user actually
    attempted appear here -- an unattempted exercise has no answer/verdict to
    review. `reveal` is reused verbatim from build_reveal()/
    build_summarize_reveal() (attempts/grading.py, attempts/rubric.py), never
    reconstructed here, so this endpoint can never drift from the reveal a
    live attempt would have shown."""

    model_config = _STRICT

    slot: int
    exercise_id: uuid.UUID
    version: int
    type: Literal["spot_the_bug", "trace", "summarize", "predict_the_fix"]
    concepts: list[str]
    code: str
    context_note: str
    answer: dict[str, Any]
    verdict: Literal["correct", "incorrect", "skipped", "grading_pending", "grading_failed"]
    reveal: STBReveal | TraceReveal | PredictTheFixReveal | SummarizeReveal | None


class SessionReviewResponse(BaseModel):
    model_config = _STRICT

    session_date: dt.date
    exercises: list[SessionReviewExercise]
