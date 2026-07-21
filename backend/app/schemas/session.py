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


class CodeDocument(BaseModel):
    """D-129 decision 4: a code payload is a LIST of documents, even when the
    list has one element.

    This is a WIRE shape only. The stored JSONB is untouched (invariant 3:
    exercises are immutable per (id, version), and the 109 published payloads
    are not migrated), so this is built by _serialize_payload when reading --
    never written back.
    """

    model_config = _STRICT

    id: str
    role: Literal["primary", "failing_test", "choice"]
    code: str
    language: str
    label: str | None = None


class SessionExercisePayload(BaseModel):
    model_config = _STRICT

    code: str
    # D-129: `code` above stays on the wire alongside `documents`. It is the
    # same string as the `primary` document, duplicated deliberately -- dropping
    # it would be a client-visible contract break for a refactor that is
    # supposed to have none, and it keeps a cached or older client rendering.
    documents: list[CodeDocument] = []
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


class TomorrowTeaser(BaseModel):
    """A4 "peek at tomorrow" (D-142): the hook shown on the Dashboard's
    completed state.

    Derived from user_concept_state.next_review_at falling within the user's
    LOCAL day after today -- real spaced-repetition data already present, never
    a persisted "tomorrow's session" (which cannot exist before today's answers
    land; see D-142). At most one concept: a hook, not a chore.
    `first_completed_session` mirrors POST /attempts' field (D-95), recomputed
    here because A4 renders on the Dashboard, so the client can warm the copy on
    the user's first-ever finished day. No grading/explanation field could ever
    live here, so invariant 1 stays structurally enforced.
    """

    model_config = _STRICT

    concept: str
    first_completed_session: bool = False
    # A4 D-142 Addendum 5: on a user's FIRST-EVER completed day the strict
    # tomorrow window is usually empty (all first-corrects schedule 7 days out),
    # so the highest-value impression would render nothing. When that happens we
    # fall back to the weakest-mastery concept. `is_fallback` is true only then,
    # and it means the copy must NOT claim a date (the concept is not scheduled
    # for tomorrow). It is only ever set alongside first_completed_session.
    is_fallback: bool = False


class SessionResponse(BaseModel):
    model_config = _STRICT

    session_date: dt.date
    completed: bool
    exercises: list[SessionExercise]
    # A4 (D-142): null unless `completed` is true AND a concept is due tomorrow.
    # The Dashboard's completed state renders it; every other state ignores it.
    tomorrow: TomorrowTeaser | None = None


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
