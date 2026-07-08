"""Strict Pydantic schemas for generator output.

These mirror the JSON shapes in prompts/generator_spot_the_bug_python_v1.md and
prompts/generator_trace_python_v1.md exactly. `extra="forbid"` is deliberate:
a schema violation (missing key, wrong type, or an unexpected extra key) is a
semantic failure per the retry policy in prompts/README.md, not a JSON-parse
failure, so it is never retried -- the candidate is simply discarded.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid")


class AbortSignal(BaseModel):
    model_config = _STRICT

    abort: Literal[True]
    reason: str


class ReasonOption(BaseModel):
    model_config = _STRICT

    id: str
    text: str


class LineNote(BaseModel):
    model_config = _STRICT

    line: int
    note: str


class STBDraftExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str
    line_notes: list[LineNote]


class STBSelfCheck(BaseModel):
    model_config = _STRICT

    single_bug_confirmed: bool
    runs_without_error_on_happy_path: bool
    no_hinting_names_or_comments: bool
    distractors_verifiably_wrong: bool


class STBCandidate(BaseModel):
    model_config = _STRICT

    buggy_code: str
    fixed_code: str
    bug_lines: list[int]
    test_code: str
    context_note: str
    reason_options: list[ReasonOption] = Field(min_length=4, max_length=4)
    correct_reason_id: str
    draft_explanation: STBDraftExplanation
    concepts: list[str] = Field(min_length=1)
    self_difficulty: int = Field(ge=1, le=10)
    self_check: STBSelfCheck


class Choice(BaseModel):
    model_config = _STRICT

    id: str
    text: str
    misconception: str | None = None


class TraceTableEntry(BaseModel):
    model_config = _STRICT

    line: int
    state: str


class WhyWrong(BaseModel):
    model_config = _STRICT

    choice_id: str
    note: str


class TraceDraftExplanation(BaseModel):
    model_config = _STRICT

    summary: str
    principle: str
    trace_table: list[TraceTableEntry]
    why_wrong: list[WhyWrong]


class TraceSelfCheck(BaseModel):
    model_config = _STRICT

    traced_line_by_line_not_from_memory: bool
    output_deterministic_and_repr_stable: bool
    each_distractor_derived_from_named_misconception: bool
    no_two_choices_identical: bool


class TraceCandidate(BaseModel):
    model_config = _STRICT

    code: str
    context_note: str
    question: str
    expected_stdout: str
    choices: list[Choice] = Field(min_length=4, max_length=4)
    correct_choice_id: str
    draft_explanation: TraceDraftExplanation
    concepts: list[str] = Field(min_length=1)
    self_difficulty: int = Field(ge=1, le=10)
    self_check: TraceSelfCheck

    @model_validator(mode="after")
    def _why_wrong_covers_exactly_the_distractors(self) -> TraceCandidate:
        distractor_ids = {c.id for c in self.choices if c.id != self.correct_choice_id}
        why_wrong_ids = {w.choice_id for w in self.draft_explanation.why_wrong}
        if why_wrong_ids != distractor_ids:
            raise ValueError(
                f"draft_explanation.why_wrong covers {sorted(why_wrong_ids)}, expected exactly "
                f"the distractor ids {sorted(distractor_ids)}",
            )
        return self
