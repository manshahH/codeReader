"""POST/GET /me/review request/response shapes (D-93c)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class ReviewRequest(BaseModel):
    model_config = _STRICT

    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=4000)


class ReviewResponse(BaseModel):
    model_config = _STRICT

    rating: int
    body: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ReviewStatusResponse(BaseModel):
    model_config = _STRICT

    reviewed: bool
    review: ReviewResponse | None
