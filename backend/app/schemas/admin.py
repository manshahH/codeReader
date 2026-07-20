"""Admin-only request shapes (mounted outside /v1, D-73 pattern)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class BetaInviteRequest(BaseModel):
    model_config = _STRICT

    github_login: str = Field(min_length=1)


class OutageFreezeRequest(BaseModel):
    model_config = _STRICT

    local_date: dt.date


class RunJobsRequest(BaseModel):
    """Which jobs to run. Omit (or send no body) to run all triggerable ones,
    which is what the scheduled workflow does; naming them is for a human
    running one by hand."""

    model_config = ConfigDict(extra="forbid")

    jobs: list[str] | None = None
