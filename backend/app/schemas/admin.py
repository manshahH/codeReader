"""Admin-only request shapes (mounted outside /v1, D-73 pattern)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class BetaInviteRequest(BaseModel):
    model_config = _STRICT

    github_login: str = Field(min_length=1)
