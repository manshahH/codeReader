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
import random
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exercises.service import (
    ExerciseImmutableError,
    ExerciseNotFoundError,
    pull_exercise,
    update_exercise_fields,
)
from app.models import Exercise
from pipeline import taxonomy
from pipeline.config import get_pipeline_settings, repo_relative_str
from pipeline.schemas import STBCandidate, TraceCandidate
from pipeline.spec_sampler import ExerciseSpec

__all__ = [
    "ExerciseImmutableError",
    "ExerciseNotFoundError",
    "approve",
    "concept_type_coverage",
    "derived_ptf_exists",
    "fetch_dedup_pool_hashes",
    "fetch_stb_for_ptf_derivation",
    "fix_and_bump",
    "insert_candidate",
    "insert_predict_the_fix",
    "kill",
    "pull",
    "seed_recent_bug_mechanisms",
    "write_reject_report",
    "write_validation_report",
]


def write_validation_report(report: dict[str, Any], exercise_id: uuid.UUID, version: int) -> str:
    """Persist the receipts and return the pointer stored as
    validation_report_url -- repo-relative, so it resolves identically from
    inside the pipeline container and from the host (D-109).
    """
    directory = get_pipeline_settings().validation_reports_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{exercise_id}_v{version}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return repo_relative_str(path)


def write_reject_report(report: dict[str, Any], *, stage: str, concept: str) -> str:
    """Persist a REJECTED candidate's validation report (D-48).

    Before this, only published candidates kept their receipts; a rejected
    one surfaced as a bare counter increment, so diagnosing a bad batch
    meant paying for another probe run. Rejects land under a `rejects/`
    subdirectory of the same reports tree, named by the rejecting stage and
    the spec's concept so a permanently dead concept is visible from a
    directory listing alone.
    """
    directory = get_pipeline_settings().validation_reports_dir / "rejects"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stage}_{concept}_{uuid.uuid4().hex[:12]}.json"
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
            # D-90: the execution-verified fix itself, not just its digest --
            # fixed_code_hash alone cannot be inverted, and this is the one
            # artifact the whole product's trust promise rests on having
            # actually executed. Kept alongside the hash, never in place of it.
            "fixed_code": candidate.fixed_code,
            "fixed_code_hash": hashlib.sha256(candidate.fixed_code.encode("utf-8")).hexdigest(),
            "sandbox_checks": sandbox_report,
        },
    }


def _shuffle_trace_choices(
    candidate: TraceCandidate,
    *,
    captured_stdout: str,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], str, dict[str, str]]:
    """C1 fix: shuffle trace choices and reassign positional ids at publish
    time, mirroring predict_the_fix.derive_artifacts (same rng, same
    shuffle-then-zip-onto-ids pattern). The trace generator prompt pins the
    correct answer to id "a" and nothing downstream reshuffled it, so every
    published trace keyed to "a" -- trivially gameable without reading the
    code. This moves the answer to a random position exactly the way PTF
    already does; the prompt is left alone.

    Returns (choices, correct_choice_id, id_remap old->new). The id_remap lets
    the explanation's why_wrong (which references the pre-shuffle distractor
    ids) move together with the choices, so the answer key can never drift
    apart from the shown options.
    """
    entries: list[dict[str, Any]] = [
        {
            "old_id": choice.id,
            # belt and braces: the correct choice's text is the verified
            # captured output, not the generator's (already-matching) claim.
            "text": captured_stdout if choice.id == candidate.correct_choice_id else choice.text,
            "misconception": choice.misconception,
            "is_correct": choice.id == candidate.correct_choice_id,
        }
        for choice in candidate.choices
    ]
    return reassign_shuffled_choice_ids(entries, rng=rng)


def reassign_shuffled_choice_ids(
    entries: list[dict[str, Any]],
    *,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], str, dict[str, str]]:
    """The single source of truth for the C1 trace shuffle -- used by
    insert_candidate at publish time AND by the one-time migration that
    re-shuffles the already-published rows, so the two can never diverge into
    a second shuffling approach.

    `entries` is [{"old_id","text","misconception","is_correct"}]. Reassigns
    ids over the entries' own id set (sorted, so a/b/c/d stay a/b/c/d),
    positionally onto the shuffled order -- the same reassignment PTF does via
    _CHOICE_IDS, but without assuming a fixed choice count. Returns
    (choices, correct_choice_id, id_remap old->new).
    """
    rng.shuffle(entries)
    id_space = sorted(entry["old_id"] for entry in entries)
    choices: list[dict[str, Any]] = []
    id_remap: dict[str, str] = {}
    correct_choice_id = ""
    for new_id, entry in zip(id_space, entries, strict=True):
        choices.append(
            {"id": new_id, "text": entry["text"], "misconception": entry["misconception"]},
        )
        id_remap[entry["old_id"]] = new_id
        if entry["is_correct"]:
            correct_choice_id = new_id
    return choices, correct_choice_id, id_remap


def _remap_trace_why_wrong(explanation: dict[str, Any], id_remap: dict[str, str]) -> None:
    """Move why_wrong's choice_id references onto the post-shuffle ids so the
    explanation never points at a distractor by its old id (C1)."""
    for entry in explanation.get("why_wrong", []):
        old = entry.get("choice_id")
        if old in id_remap:
            entry["choice_id"] = id_remap[old]


def _trace_payload(
    candidate: TraceCandidate,
    *,
    choices: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "code": candidate.code,
        "context_note": candidate.context_note,
        "question": candidate.question,
        "choices": choices,
    }


def _trace_grading(
    *,
    correct_choice_id: str,
    captured_stdout: str,
    sandbox_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "deterministic",
        "correct_choice_id": correct_choice_id,
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
    origin: str = "llm",
    rng: random.Random | None = None,
) -> Exercise:
    """Insert a candidate that survived every gate as an in_review exercise row.

    `origin` (D-87): "llm" for orchestrator-generated candidates (the
    default, unchanged); pipeline/ingest.py passes "handauthored_claude" so a
    hand-authored candidate that clears the SAME gate chain is still
    permanently distinguishable in `source.origin` from both LLM-generated
    content and the older seed_handauthored content (D-62).
    """
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
        # C1: shuffle the trace choices at publish time (mirrors PTF), so the
        # correct answer is not always id "a". payload.choices,
        # grading.correct_choice_id, and the explanation's why_wrong ids all
        # move together off the single shuffle below.
        choices, correct_choice_id, id_remap = _shuffle_trace_choices(
            candidate,
            captured_stdout=captured_stdout or "",
            rng=rng or random.Random(),
        )
        _remap_trace_why_wrong(final_explanation, id_remap)
        payload = _trace_payload(candidate, choices=choices)
        grading = _trace_grading(
            correct_choice_id=correct_choice_id,
            captured_stdout=captured_stdout or "",
            sandbox_report=validation_report.get("sandbox_gate", {}),
        )

    report_path = write_validation_report(validation_report, exercise_id, version)

    source: dict[str, Any] = {
        "origin": origin,
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


async def insert_predict_the_fix(
    session: AsyncSession,
    *,
    concepts: list[str],
    difficulty_authored: int,
    payload: dict[str, Any],
    grading: dict[str, Any],
    explanation: dict[str, Any],
    content_hash: str,
    validation_report: dict[str, Any],
    generator_model: str,
    derived_from_id: uuid.UUID,
    derived_from_version: int,
    stb_template_id: str | None,
    origin: str = "llm",
) -> Exercise:
    """Insert a predict_the_fix exercise derived from a verified spot_the_bug
    (D-80). Deterministic grading; the correct choice is the execution-proven
    fixed_code (already baked into `grading.correct_choice_id`), never a model
    claim. `source.derived_from` records the parent STB so a reviewer can trace
    both back to the same verified artifacts.

    `origin` (D-91, mirrors `insert_candidate`'s D-87 parameter): "llm" for
    every existing caller (unchanged, orchestrator-derived PTF); the
    hand-authored PTF backfill entrypoint passes "handauthored_claude" so a
    hand-authored derivation is never mislabeled as pipeline-generated -- that
    field is exactly what traces a quality problem back to its source.
    """
    exercise_id = uuid.uuid4()
    version = 1
    report_path = write_validation_report(validation_report, exercise_id, version)

    source: dict[str, Any] = {
        "origin": origin,
        "model": generator_model,
        "prompt_template_id": "ptf_py_v1",
        "stb_prompt_template_id": stb_template_id,
        "content_hash": content_hash,
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
        "derived_from": {"id": str(derived_from_id), "version": derived_from_version},
    }

    exercise = Exercise(
        id=exercise_id,
        version=version,
        language="python",
        type="predict_the_fix",
        grading_mode="deterministic",
        difficulty_authored=difficulty_authored,
        concepts=concepts,
        tags=[],
        status="in_review",
        source=source,
        payload=payload,
        grading=grading,
        explanation=explanation,
        validation_report_url=report_path,
        human_reviewed=False,
    )
    session.add(exercise)
    await session.flush()
    return exercise


async def fetch_stb_for_ptf_derivation(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    version: int,
) -> Exercise | None:
    """Load an ALREADY-PUBLISHED spot_the_bug row to derive a predict_the_fix
    from (D-91's backfill entrypoint), as opposed to a freshly-generated
    in-memory candidate (the orchestrator's `_derive_and_publish_ptf` path).
    Returns None if the row does not exist, is not a spot_the_bug, or has
    left the review queue (killed/retired/pulled) -- deriving new content
    from a row that was pulled from circulation would launder whatever made
    it unfit back into a new exercise.
    """
    exercise = await session.scalar(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.version == version),
    )
    if exercise is None or exercise.type != "spot_the_bug":
        return None
    if exercise.status not in ("in_review", "live"):
        return None
    return exercise


async def derived_ptf_exists(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> bool:
    """True iff a predict_the_fix row already carries
    `source.derived_from == {id: exercise_id, version: version}` -- guards
    the backfill entrypoint against deriving a second PTF for the same
    spot_the_bug on a repeat run over the same batch."""
    rows = await session.scalars(
        select(Exercise.id).where(
            Exercise.type == "predict_the_fix",
            Exercise.source["derived_from"]["id"].astext == str(exercise_id),
            Exercise.source["derived_from"]["version"].astext == str(version),
        ),
    )
    return rows.first() is not None


async def approve(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    now = dt.datetime.now(dt.UTC)
    return await update_exercise_fields(
        session,
        exercise_id,
        version,
        {"status": "live", "human_reviewed": True, "validated_at": now, "published_at": now},
    )


async def kill(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    """Retire a candidate (or, since D-58, a live row -- status is the one
    field a live exercise may change). For a LIVE exercise prefer `pull`:
    kill alone leaves the exercise in already-issued sessions and caches for
    up to 36h; pull purges them."""
    return await update_exercise_fields(session, exercise_id, version, {"status": "retired"})


async def pull(
    session: AsyncSession,
    redis,
    exercise_id: uuid.UUID,
    version: int,
) -> tuple[Exercise, int]:
    """Incident path (D-58): status='pulled' plus purge of every cached/
    persisted daily session still referencing the exercise. Commits."""
    return await pull_exercise(session, redis, exercise_id, version)


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


async def fetch_dedup_pool_hashes(session: AsyncSession) -> set[str]:
    """content_hash values of every live OR in_review exercise, for
    dedup.is_duplicate().

    Was live-only; in_review candidates from an earlier batch that crashed
    or is still awaiting human review were invisible to dedup, so a re-run
    of `python -m pipeline.orchestrator` (the CLAUDE.md M8 resumability ask:
    "make repeated runs additive and idempotent") could pay to regenerate
    and re-validate a near-identical candidate already sitting in the review
    queue. Widening to in_review costs nothing -- a candidate that never
    ships (killed) simply stops contributing its hash on the next run,
    same as it already works for status='retired'.
    """
    rows = await session.scalars(
        select(Exercise.source).where(Exercise.status.in_(("live", "in_review"))),
    )
    return {
        source["content_hash"]
        for source in rows.all()
        if isinstance(source, dict) and source.get("content_hash")
    }


async def concept_type_coverage(session: AsyncSession) -> dict[tuple[str, str], int]:
    """(type, concept_slug) -> count of LIVE exercises carrying that concept.

    Feeds the spec sampler's coverage-driven sampling (CLAUDE.md M8 part 1):
    a 200-exercise corpus should cover the curriculum, not cluster on
    whatever concepts happen to sample easiest. Live only (not in_review):
    a candidate awaiting review hasn't proven it will ship, so it should not
    yet count as "this concept is covered."
    """
    rows = await session.execute(
        select(Exercise.type, Exercise.concepts).where(Exercise.status == "live"),
    )
    counts: collections.Counter[tuple[str, str]] = collections.Counter()
    for exercise_type, concepts in rows.all():
        for concept in concepts:
            counts[(exercise_type, concept)] += 1
    return dict(counts)


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
