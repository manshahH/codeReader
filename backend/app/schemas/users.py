"""PATCH /me request shape, GET /me/activity response shape (docs/05 section 3)."""

from __future__ import annotations

import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

_STRICT = ConfigDict(extra="forbid")


class ActivityDay(BaseModel):
    """One row of the contribution-grid data (D-94). `completed` distinguishes
    a day the user opened the app but didn't finish from one they finished --
    a date with no entry at all means they never opened the app that day."""

    model_config = _STRICT

    session_date: dt.date
    completed: bool


class MeSessionSummary(BaseModel):
    """One row of GET /me/sessions: a daily_sessions row joined against that
    day's attempts. `exercise_count` is every exercise assigned that day
    (the full daily_sessions.exercise_list), not just the ones answered so
    far -- for an in-progress session this is deliberately the target, not
    the current count. `concepts` is the union across every exercise
    assigned, so it answers "what did/does this session cover" regardless
    of completion state."""

    model_config = _STRICT

    session_date: dt.date
    completed: bool
    exercise_count: int
    correct_count: int
    skipped_count: int
    concepts: list[str]


class AccuracyHistoryDay(BaseModel):
    """One row of GET /me/accuracy-history: a day's correct/total ratio
    across every deterministically-resolved attempt (is_correct is not
    NULL), bucketed by `attempts.session_date` -- the same local-day field
    every other date-sensitive read in this app already uses, not a
    re-derivation from created_at."""

    model_config = _STRICT

    date: dt.date
    accuracy: float
    attempts: int


class UpdateMeRequest(BaseModel):
    model_config = _STRICT

    display_name: str | None = None
    timezone: str | None = None
    level: Literal["junior", "mid", "senior"] | None = None
    reminder_local_time: str | None = None

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @field_validator("reminder_local_time")
    @classmethod
    def _validate_reminder_local_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            dt.time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("reminder_local_time must be HH:MM") from exc
        return value
