"""Per-feature usage tracking (D-145(g)).

ONE row per (user, feature, local day) FIRST use. The question this table must
answer LATER is "which features do people use, and which correlate with
returning" -- and returning is measured in DAYS, so the minimal grain that
answers it is one record per user per feature per local day. An event firehose
would add volume and privacy exposure and answer nothing extra.

The PRIMARY KEY (user_id, feature, local_date) IS the once-per-day ceiling,
inserted ON CONFLICT DO NOTHING -- the same construction email_deliveries uses
(D-137): a recorded fact with a uniqueness constraint, never a recomputation.

NO NEW PII (D-145(g), D-120 posture): user_id plus a date is already the shape
of streak_events, daily_sessions and attempts. No free text, no content of what
was saved, no IP, no user agent, no referrer. Rows carry no content, so they
need no export of their own under D-145(e), and they are deleted with the
account by ON DELETE CASCADE.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeatureUsage(Base):
    __tablename__ = "feature_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # A registry key from app.core.entitlements.Feature. Stored as text (the
    # enum VALUE), not an FK: the registry is code, and a key is stable forever
    # by convention (D-145(b)(ii)) precisely so these rows never orphan.
    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    # The user's LOCAL day, the same day notion streaks and daily_sessions use.
    local_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
