"""POST /attempts request/response shapes (docs/05 section 5).

Reveal/explanation models are allowlists too: build_reveal() (attempts/grading.py)
constructs these field-by-field from exercise.grading/exercise.explanation, never
by dumping those JSONB columns wholesale, so pipeline-internal fields
(verified/mismatch_flagged/artifacts) never reach the client.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

_STRICT = ConfigDict(extra="forbid")


class AttemptRequest(BaseModel):
    model_config = _STRICT

    exercise_id: uuid.UUID
    exercise_version: int
    answer: dict[str, Any]
    time_taken_ms: int | None = None


class LineNote(BaseModel):
    model_config = _STRICT

    line: int
    note: str


class STBExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str
    line_notes: list[LineNote]


class STBReveal(BaseModel):
    model_config = _STRICT

    correct_lines: list[int]
    correct_reason_id: str
    explanation: STBExplanation


class TraceTableEntry(BaseModel):
    model_config = _STRICT

    line: int
    state: str


class WhyWrongEntry(BaseModel):
    model_config = _STRICT

    choice_id: str
    note: str


class TraceExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str
    trace_table: list[TraceTableEntry]
    why_wrong: list[WhyWrongEntry]


class TraceReveal(BaseModel):
    model_config = _STRICT

    correct_choice_id: str
    explanation: TraceExplanation


class PredictTheFixExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str
    why_wrong: list[WhyWrongEntry]


class PredictTheFixReveal(BaseModel):
    model_config = _STRICT

    correct_choice_id: str
    explanation: PredictTheFixExplanation


class SummarizeExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str


class SummarizeReveal(BaseModel):
    model_config = _STRICT

    explanation: SummarizeExplanation


class GraderOutput(BaseModel):
    model_config = _STRICT

    rubric_hits: list[str]
    rubric_misses: list[str]
    reference_answer: str


class PercentileInfo(BaseModel):
    model_config = _STRICT

    solve_rate: float
    n: int


class StreakInfo(BaseModel):
    model_config = _STRICT

    current: int
    event: Literal["extended", "reset"]


class SessionProgress(BaseModel):
    model_config = _STRICT

    completed: bool
    remaining: int
    # True only on the single attempt response that flips this session to
    # completed AND is the user's first-ever completed daily_sessions row
    # (D-93b). False on every other response, including replays.
    first_completed_session: bool = False


class AttemptResponse(BaseModel):
    model_config = _STRICT

    attempt_id: int
    # "skipped" (D-93): an honest {"skipped": true} answer. Distinct from
    # grading_pending/grading_failed -- both of those are None-is_correct
    # states waiting on/failed at a real grade; skipped is terminal and
    # immediate, there is simply no grade to give.
    status: Literal["graded", "grading_pending", "grading_failed", "skipped"]
    is_correct: bool | None
    reveal: STBReveal | TraceReveal | PredictTheFixReveal | SummarizeReveal | None
    score: float | None = None
    grader_output: GraderOutput | None = None
    percentile: PercentileInfo | None
    streak: StreakInfo | None
    session: SessionProgress
