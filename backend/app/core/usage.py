"""Record per-feature usage without ever failing the request (D-145(g)).

ONE row per (user, feature, local day) FIRST use. The insert rides the caller's
own transaction (it is one small write and the row is never user-visible) and
ANY failure is caught and logged, never raised: an analytics gap must not fail a
user action.

Two things make "never raises into the request path" true rather than hopeful:

  * ON CONFLICT DO NOTHING means the common case -- already recorded today --
    is a no-op, not an error, so the normal path never raises at all.
  * A SAVEPOINT (begin_nested) wraps the write, so if it DOES raise (a dropped
    connection, a programming error) the rollback is scoped to the savepoint and
    the outer transaction stays usable. Without it a failed statement would
    poison the whole Postgres transaction and take the user's real work down
    with it -- the same reason email verification uses a savepoint.

This module has NO call site yet: it is groundwork that lands before/with A5
(D-145(g) sequencing) so evidence exists before any flip decision.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entitlements import Feature
from app.models import FeatureUsage

logger = logging.getLogger(__name__)


async def record_feature_usage(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    feature: Feature,
    local_date: dt.date,
) -> None:
    """Best-effort record of first use of `feature` by `user_id` on
    `local_date`. Idempotent per that triple; swallows and logs any failure."""

    statement = (
        insert(FeatureUsage)
        .values(user_id=user_id, feature=feature.value, local_date=local_date)
        .on_conflict_do_nothing(index_elements=["user_id", "feature", "local_date"])
    )
    try:
        async with session.begin_nested():
            await session.execute(statement)
    except Exception:  # noqa: BLE001 -- analytics must never fail a user action
        logger.warning("feature_usage_record_failed", exc_info=True)
