"""Exercise publishing: the narrow layer.

Per the module boundary law (docs/06), this is the ONLY pipeline module that
imports backend.app -- models and the existing exercises service, never any
other domain. New candidates are inserted as status='in_review' (the review
queue, persisted, not an in-memory list). Approve/kill/fix-and-bump reuse the
existing `app.exercises.service.update_exercise_fields` immutability guard
built in M1: a live version can never be mutated. Fix-and-bump never needs to
retire an already-live old version either -- `exercises_current` already
prefers the highest-version live row for a given id.

The validation report is written to a local JSON file and that path is stored
as validation_report_url. TODO(post-M3): upload to S3 and store the s3://
URL instead once the pipeline has real deploy infrastructure.
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exercises.service import ExerciseImmutableError, ExerciseNotFoundError, update_exercise_fields
from app.models import Exercise
from pipeline import taxonomy
from pipeline.config import get_pipeline_settings
from pipeline.schemas import STBCandidate, TraceCandidate
from pipeline.spec_sampler import ExerciseSpec

__all__ = [
    "ExerciseImmutableError",
    "ExerciseNotFoundError",
    "approve",
    "fetch_live_pool_hashes",
    "fix_and_bump",
    "insert_candidate",
    "kill",
    "seed_recent_bug_mechanisms",
    "write_validation_report",
]


def write_validation_report(report: dict[str, Any], exercise_id: uuid.UUID, version: int) -> str:
    directory = get_pipeline_settings().validation_reports_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{exercise_id}_v{version}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return str(path)


def _stb_payload(candidate: STBCandidate) -> dict[str, Any]:
    return {
        "code": candidate.buggy_code,
        "context_note": candidate.context_note,
        "answer_mode": "line_select_plus_reason",
        "reason_options": [option.model_dump() for option in candidate.reason_options],
    }


def _stb_grading(
    candidate: STBCandidate,
    *,
    verified_bug_lines: list[int],
    sandbox_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "deterministic",
        "correct_lines": verified_bug_lines,
        "correct_reason_id": candidate.correct_reason_id,
        "artifacts": {
            "failing_test": candidate.test_code,
            "fixed_code_hash": hashlib.sha256(candidate.fixed_code.encode("utf-8")).hexdigest(),
            "sandbox_checks": sandbox_report,
        },
    }


def _trace_payload(candidate: TraceCandidate, *, captured_stdout: str) -> dict[str, Any]:
    choices = [
        {
            "id": choice.id,
            # belt and braces: the correct choice's text is the verified
            # captured output, not the generator's (already-matching) claim.
            "text": captured_stdout if choice.id == candidate.correct_choice_id else choice.text,
            "misconception": choice.misconception,
        }
        for choice in candidate.choices
    ]
    return {
        "code": candidate.code,
        "context_note": candidate.context_note,
        "question": candidate.question,
        "choices": choices,
    }


def _trace_grading(
    candidate: TraceCandidate,
    *,
    captured_stdout: str,
    sandbox_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "deterministic",
        "correct_choice_id": candidate.correct_choice_id,
        "captured_stdout": captured_stdout,
        "artifacts": {"sandbox_checks": sandbox_report},
    }


async def insert_candidate(
    session: AsyncSession,
    spec: ExerciseSpec,
    candidate: STBCandidate | TraceCandidate,
    *,
    final_explanation: dict[str, Any],
    content_hash: str,
    validation_report: dict[str, Any],
    generator_model: str,
    captured_stdout: str | None = None,
    verified_bug_lines: list[int] | None = None,
) -> Exercise:
    """Insert a candidate that survived every gate as an in_review exercise row."""
    exercise_id = uuid.uuid4()
    version = 1

    if spec.type == "spot_the_bug":
        payload = _stb_payload(candidate)
        grading = _stb_grading(
            candidate,
            verified_bug_lines=verified_bug_lines or [],
            sandbox_report=validation_report.get("sandbox_gate", {}),
        )
    else:
        payload = _trace_payload(candidate, captured_stdout=captured_stdout or "")
        grading = _trace_grading(
            candidate,
            captured_stdout=captured_stdout or "",
            sandbox_report=validation_report.get("sandbox_gate", {}),
        )

    report_path = write_validation_report(validation_report, exercise_id, version)

    source: dict[str, Any] = {
        "origin": "llm",
        "model": generator_model,
        "prompt_template_id": validation_report.get("template_id"),
        "content_hash": content_hash,
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
    }
    if spec.type == "spot_the_bug" and spec.has_bug and isinstance(candidate, STBCandidate):
        correct_option = next(
            (o for o in candidate.reason_options if o.id == candidate.correct_reason_id),
            None,
        )
        if correct_option is not None:
            source["bug_mechanism"] = correct_option.text

    exercise = Exercise(
        id=exercise_id,
        version=version,
        language="python",
        type=spec.type,
        grading_mode="deterministic",
        difficulty_authored=spec.difficulty,
        concepts=list(candidate.concepts),
        tags=[],
        status="in_review",
        source=source,
        payload=payload,
        grading=grading,
        explanation=final_explanation,
        validation_report_url=report_path,
        human_reviewed=False,
    )
    session.add(exercise)
    await session.flush()
    return exercise


async def approve(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    now = dt.datetime.now(dt.UTC)
    return await update_exercise_fields(
        session,
        exercise_id,
        version,
        {"status": "live", "human_reviewed": True, "validated_at": now, "published_at": now},
    )


async def kill(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    return await update_exercise_fields(session, exercise_id, version, {"status": "retired"})


async def fix_and_bump(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    old_version: int,
    overrides: dict[str, Any],
) -> Exercise:
    """Create version+1 with `overrides` applied on top of the old row.

    Never mutates an already-live old row: exercises_current already prefers
    the highest-version live row for a given id, so a live predecessor simply
    stays live and harmless once the new version goes live too.
    """
    old = await session.scalar(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.version == old_version),
    )
    if old is None:
        raise ExerciseNotFoundError(f"exercise {exercise_id} v{old_version} not found")

    new_version = old_version + 1
    new_exercise = Exercise(
        id=exercise_id,
        version=new_version,
        language=old.language,
        type=old.type,
        grading_mode=old.grading_mode,
        difficulty_authored=overrides.get("difficulty_authored", old.difficulty_authored),
        concepts=overrides.get("concepts", list(old.concepts)),
        tags=overrides.get("tags", list(old.tags)),
        status="in_review",
        source=overrides.get("source", dict(old.source)),
        payload=overrides.get("payload", dict(old.payload)),
        grading=overrides.get("grading", dict(old.grading)),
        explanation=overrides.get("explanation", dict(old.explanation)),
        validation_report_url=old.validation_report_url,
        human_reviewed=False,
    )
    session.add(new_exercise)

    if old.status != "live":
        await update_exercise_fields(session, exercise_id, old_version, {"status": "retired"})

    await session.flush()
    return new_exercise


async def fetch_live_pool_hashes(session: AsyncSession) -> set[str]:
    """content_hash values of every live exercise, for dedup.is_duplicate()."""
    rows = await session.scalars(
        select(Exercise.source).where(Exercise.status == "live"),
    )
    return {
        source["content_hash"]
        for source in rows.all()
        if isinstance(source, dict) and source.get("content_hash")
    }


async def seed_recent_bug_mechanisms(
    session: AsyncSession,
    *,
    limit_per_concept: int = 3,
    scan_limit: int = 500,
) -> dict[str, list[str]]:
    """Cross-run avoid_patterns history for the spec sampler.

    Reads the last `scan_limit` spot_the_bug candidates (live or in_review)
    most-recent-first and collects each concept's most recent
    source.bug_mechanism values, so a fresh orchestrator run still avoids
    repeating bug mechanisms an earlier run already shipped for that concept.
    """
    rows = await session.execute(
        select(Exercise.concepts, Exercise.source)
        .where(Exercise.type == "spot_the_bug", Exercise.status.in_(["live", "in_review"]))
        .order_by(Exercise.created_at.desc())
        .limit(scan_limit),
    )
    history: dict[str, list[str]] = collections.defaultdict(list)
    for concepts, source in rows.all():
        mechanism = source.get("bug_mechanism") if isinstance(source, dict) else None
        if not mechanism:
            continue
        for concept in concepts:
            if len(history[concept]) < limit_per_concept:
                history[concept].append(mechanism)
    return dict(history)
