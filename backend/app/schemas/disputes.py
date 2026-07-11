"""POST /exercises/{id}/v/{version}/dispute request/response shapes (docs/05 section 6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")

DisputeReason = Literal["wrong_answer", "ambiguous", "broken_code", "bad_explanation", "other"]


class DisputeRequest(BaseModel):
    model_config = _STRICT

    reason: DisputeReason
    body: str | None = Field(default=None, max_length=4000)
    attempt_id: int | None = None


class DisputeResponse(BaseModel):
    model_config = _STRICT

    dispute_id: int
    status: Literal["open", "accepted", "rejected"]
