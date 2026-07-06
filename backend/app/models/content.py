from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint("version >= 1"),
        CheckConstraint("language IN ('python')"),
        CheckConstraint("type IN ('spot_the_bug','trace','summarize')"),
        CheckConstraint("grading_mode IN ('deterministic','rubric')"),
        CheckConstraint("difficulty_authored BETWEEN 1 AND 10"),
        CheckConstraint("cardinality(concepts) >= 1"),
        CheckConstraint("status IN ('draft','in_review','live','pulled','retired')"),
        Index(
            "idx_exercises_serve",
            "language",
            "type",
            "status",
            "difficulty_authored",
            postgresql_where=text("status = 'live'"),
        ),
        Index("idx_exercises_concepts", "concepts", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    language: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    grading_mode: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_authored: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    difficulty_empirical: Mapped[decimal.Decimal | None] = mapped_column(Numeric(4, 2))
    concepts: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )
    est_time_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("90"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grading: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_report_url: Mapped[str | None] = mapped_column(Text)
    human_reviewed: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ExerciseStat(Base):
    __tablename__ = "exercise_stats"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exercise_id", "exercise_version"],
            ["exercises.id", "exercises.version"],
        ),
    )

    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    exercise_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempts_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    solve_rate: Mapped[decimal.Decimal | None] = mapped_column(Numeric(4, 3))
    median_time_ms: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
