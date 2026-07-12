from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        ForeignKeyConstraint(
            ["exercise_id", "exercise_version"],
            ["exercises.id", "exercises.version"],
        ),
        CheckConstraint("grading_mode IN ('deterministic','rubric')"),
        CheckConstraint("status IN ('graded','grading_pending','grading_failed','skipped')"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)"),
        CheckConstraint("client IN ('web','pwa')"),
        Index("idx_attempts_user", "user_id", text("created_at DESC")),
        Index("idx_attempts_ex", "exercise_id", "exercise_version", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    exercise_version: Mapped[int] = mapped_column(Integer, nullable=False)
    session_date: Mapped[dt.date] = mapped_column(nullable=False)
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grading_mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'graded'"))
    is_correct: Mapped[bool | None] = mapped_column()
    score: Mapped[decimal.Decimal | None] = mapped_column(Numeric(4, 3))
    grader_output: Mapped[dict | None] = mapped_column(JSONB)
    time_taken_ms: Mapped[int | None] = mapped_column(Integer)
    client: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'web'"))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    graded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class AttemptPartitionMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    exercise_version: Mapped[int] = mapped_column(Integer, nullable=False)
    session_date: Mapped[dt.date] = mapped_column(nullable=False)
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grading_mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column()
    score: Mapped[decimal.Decimal | None] = mapped_column(Numeric(4, 3))
    grader_output: Mapped[dict | None] = mapped_column(JSONB)
    time_taken_ms: Mapped[int | None] = mapped_column(Integer)
    client: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    graded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Attempt202607(AttemptPartitionMixin, Base):
    __tablename__ = "attempts_2026_07"


class Attempt202608(AttemptPartitionMixin, Base):
    __tablename__ = "attempts_2026_08"


class AttemptDefault(AttemptPartitionMixin, Base):
    __tablename__ = "attempts_default"
