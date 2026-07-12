from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_active_local_date: Mapped[dt.date | None] = mapped_column()
    streak_freezes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    accuracy_by_type: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class StreakEvent(Base):
    __tablename__ = "streak_events"
    __table_args__ = (
        CheckConstraint("event IN ('extended','reset','freeze_used','repaired','adjusted')"),
        Index("idx_streak_events_user", "user_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(Text, nullable=False)
    from_value: Mapped[int] = mapped_column(Integer, nullable=False)
    to_value: Mapped[int] = mapped_column(Integer, nullable=False)
    local_date: Mapped[dt.date] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserConceptState(Base):
    __tablename__ = "user_concept_state"
    __table_args__ = (
        CheckConstraint("mastery >= 0 AND mastery <= 1"),
        Index("idx_ucs_due", "user_id", "next_review_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    concept: Mapped[str] = mapped_column(Text, primary_key=True)
    mastery: Mapped[decimal.Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("0"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # D-93: "I don't know" count, distinct from attempts/correct so a skip
    # never inflates the accuracy denominator those two drive.
    declined: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
