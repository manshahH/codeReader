"""GET /session/today response shapes (docs/05 section 4).

extra="forbid" everywhere: these are allowlists. `grading` and `explanation`
are structurally absent -- there is no field on any model here that could
carry them, so the CI leak test (invariant 1) has something real to enforce.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

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


class SessionExercise(BaseModel):
    model_config = _STRICT

    slot: int
    exercise_id: uuid.UUID
    version: int
    type: Literal["spot_the_bug", "trace", "summarize"]
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
