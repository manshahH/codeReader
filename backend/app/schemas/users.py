"""PATCH /me request shape (docs/05 section 3)."""

from __future__ import annotations

import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

_STRICT = ConfigDict(extra="forbid")


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
