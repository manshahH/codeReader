"""GET /me/stats, GET /me/concepts, PATCH /me (docs/05 section 3).

The stats/concepts reads are straight reads of the precomputed
user_stats / user_concept_state tables -- never aggregates attempts at
request time.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.accuracy import project as project_accuracy
from app.core.errors import ApiError
from app.models import User, UserConceptState, UserStats


async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    stats = await db.get(UserStats, user_id)
    if stats is None:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "streak_freezes": 0,
            "total_attempts": 0,
            "total_correct": 0,
            "accuracy_by_type": {},
            "last_active_local_date": None,
        }
    return {
        "current_streak": stats.current_streak,
        "longest_streak": stats.longest_streak,
        "streak_freezes": stats.streak_freezes,
        "total_attempts": stats.total_attempts,
        "total_correct": stats.total_correct,
        "accuracy_by_type": project_accuracy(stats.accuracy_by_type),
        "last_active_local_date": (
            stats.last_active_local_date.isoformat() if stats.last_active_local_date else None
        ),
    }


async def get_concepts(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = await db.execute(
        select(UserConceptState)
        .where(UserConceptState.user_id == user_id)
        .order_by(UserConceptState.mastery.asc()),
    )
    return [
        {
            "concept": row.concept,
            "mastery": float(row.mastery),
            "attempts": row.attempts,
            "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
        }
        for row in rows.scalars().all()
    ]


async def update_me(db: AsyncSession, user_id: uuid.UUID, updates: dict) -> User:
    """Applies only the fields the client actually sent (docs/05: all optional).

    Setting `level` is the onboarding action itself (docs/03: onboarding is
    "level pick, one screen") -- there is no separate "mark onboarded" call.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    if "display_name" in updates:
        user.display_name = updates["display_name"]
    if "timezone" in updates:
        user.timezone = updates["timezone"]
    if "level" in updates:
        user.level = updates["level"]
        user.onboarded = True
    if "reminder_local_time" in updates:
        value = updates["reminder_local_time"]
        user.reminder_local_time = dt.time.fromisoformat(value) if value else None

    await db.flush()
    await db.commit()
    return user
