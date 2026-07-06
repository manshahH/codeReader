from __future__ import annotations

import logging
import uuid

logger = logging.getLogger("app.alerts")


def alert_refresh_reuse(
    *,
    token_id: uuid.UUID | None,
    family_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    request_id: str,
) -> None:
    logger.warning(
        "refresh_token_reuse_detected",
        extra={
            "event": "refresh_token_reuse_detected",
            "token_id": str(token_id) if token_id else None,
            "family_id": str(family_id) if family_id else None,
            "user_id": str(user_id) if user_id else None,
            "request_id": request_id,
        },
    )