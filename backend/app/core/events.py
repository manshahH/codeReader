from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger("app.alerts")
events_logger = logging.getLogger("app.events")


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


def alert_dispute_opened(
    *,
    dispute_id: int,
    exercise_id: uuid.UUID,
    exercise_version: int,
    user_id: uuid.UUID,
    reason: str,
) -> None:
    """docs/03: dispute button -> disputes table + operator alert; pulling
    the exercise stays a manual admin action at MVP.
    """
    logger.warning(
        "dispute_opened",
        extra={
            "event": "dispute_opened",
            "dispute_id": dispute_id,
            "exercise_id": str(exercise_id),
            "exercise_version": exercise_version,
            "user_id": str(user_id),
            "reason": reason,
        },
    )


def append_attempt_event(event: dict[str, Any]) -> None:
    """Best-effort JSONL append of an attempt event.

    TODO(post-M4): upload to S3 (S3_BUCKET/S3_EVENTS_PREFIX) instead of the
    local disk; local-path stub mirrors pipeline/publish.py's
    validation_report_url stub from M3 (D-32 area). Called strictly AFTER the
    attempt transaction commits; a failure here must never fail the request
    or roll back the attempt -- it is an analytics gap, not a user error.
    """
    try:
        directory = Path(get_settings().EVENTS_LOCAL_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        today = dt.datetime.now(dt.UTC).date().isoformat()
        line = json.dumps(event, default=str, separators=(",", ":"))
        with (directory / f"{today}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        events_logger.warning("attempt_event_append_failed", exc_info=True)