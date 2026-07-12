"""File-provider content ingestion (D-87).

Verifies hand-authored candidates through the SAME, unmodified gate chain the
orchestrator runs for LLM-generated ones: static_gate -> sandbox (real Docker,
canary-checked first per D-57) -> semantic gates (OpenAI path, D-14) -> dedup
-> explain -> publish as in_review. A hand-authored candidate is not a trusted
candidate (CLAUDE.md invariant 1): this module is plumbing and execution, not
judgment -- it reuses orchestrator._evaluate_candidate/_publish_survivor
verbatim rather than re-implementing any gate logic, so there is no risk of a
parallel path quietly diverging from what a sampled spec goes through.

Usage: python -m pipeline.ingest --file <path>

Input: a JSON array of {spec, prompt_template_id, candidate} objects.
  * `spec` carries type (must be "spot_the_bug"), concept, difficulty,
    has_bug, language. domain and line_budget_min/max -- which a sampler run
    would normally produce -- are DERIVED here the same way sample_spec
    derives them (spec_sampler.line_budget_for_difficulty), since a
    hand-authored spec has no sampler run to produce them.
  * `candidate` must validate against schemas.STBCandidate. The B3 free
    static check (claimed buggy_result == fixed_result -> reject) applies
    unchanged: it is a Pydantic model_validator on the schema itself, not
    something a caller can route around.
  * `prompt_template_id` must be exactly "handauthored_stb_v1" -- the
    required provenance tag, not free-form input; anything else is a load
    -time rejection.

No repair, no regeneration: D-83's repair loop and D-84's best-of-N both
assume a generator that can be asked to try again from the same spec. There is
no generator here -- a human already committed to exactly one candidate per
spec -- so a gate rejection is terminal, exactly like the user asked: "if one
fails a gate, it fails," with the same D-48 reject report as any other.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import random
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.orchestrator import (
    BatchReport,
    _evaluate_candidate,
    _publish_survivor,
    _record_reject,
)
from pipeline.publish import fetch_dedup_pool_hashes, write_reject_report
from pipeline.sandbox.runner import verify_sandbox_available
from pipeline.schemas import STBCandidate
from pipeline.spec_sampler import ExerciseSpec, line_budget_for_difficulty
from pipeline.taxonomy import concepts_for_type

logger = logging.getLogger(__name__)

# D-87 provenance tags: permanently distinguish this path's output from
# orchestrator-generated content (source.origin="llm") and from the older
# hand-typed seed content (source.origin="seed_handauthored", D-62).
ORIGIN = "handauthored_claude"
# source.model: who/what actually wrote the code, distinct from source.origin
# (which names the ingestion PATH). Never an LLM_client model string -- no
# generator call produced this candidate.
AUTHOR_LABEL = "claude"
REQUIRED_TEMPLATE_ID = "handauthored_stb_v1"
_DEFAULT_DOMAIN = "hand-authored exercise"

_STB_CONCEPT_SLUGS = frozenset(c.slug for c in concepts_for_type("spot_the_bug"))


class IngestLoadError(RuntimeError):
    """A batch item failed to load: an unsupported spec, an unexpected
    prompt_template_id, or (via STBCandidate.model_validate) a schema/B3
    validation failure on `candidate`. Recorded as a stage="load" rejection
    with a D-48-style reject report, same as any other rejection -- a
    hand-authored candidate does not get to skip the schema."""


@dataclasses.dataclass(frozen=True)
class IngestItem:
    spec: ExerciseSpec
    candidate: STBCandidate


def _build_spec(raw: dict[str, Any]) -> ExerciseSpec:
    exercise_type = raw.get("type")
    if exercise_type != "spot_the_bug":
        raise IngestLoadError(
            f"unsupported spec.type {exercise_type!r}: ingest currently only handles spot_the_bug",
        )
    if raw.get("language", "python") != "python":
        raise IngestLoadError(f"unsupported spec.language {raw.get('language')!r}: python only")
    for key in ("concept", "difficulty", "has_bug"):
        if key not in raw:
            raise IngestLoadError(f"spec missing required key {key!r}")

    concept = raw["concept"]
    if concept not in _STB_CONCEPT_SLUGS:
        raise IngestLoadError(
            f"spec.concept {concept!r} is not a valid, samplable spot_the_bug concept "
            "(unknown slug, or flagged requires_forbidden/stb_unsamplable in pipeline.taxonomy)",
        )

    difficulty = raw["difficulty"]
    if not isinstance(difficulty, int) or not (1 <= difficulty <= 10):
        raise IngestLoadError(f"spec.difficulty must be an int in [1, 10], got {difficulty!r}")

    line_budget_min, line_budget_max = line_budget_for_difficulty(difficulty)
    return ExerciseSpec(
        type="spot_the_bug",
        concept=concept,
        difficulty=difficulty,
        domain=raw.get("domain", _DEFAULT_DOMAIN),
        line_budget_min=line_budget_min,
        line_budget_max=line_budget_max,
        has_bug=bool(raw["has_bug"]),
        avoid_patterns=(),
    )


def load_batch(path: Path) -> tuple[list[IngestItem], list[dict[str, Any]]]:
    """Parse and schema-validate every item in `path`.

    Returns (loaded, load_rejects); each load_rejects entry is the report
    already written to validation_reports_dir/rejects/ (stage="load").
    """
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list):
        raise IngestLoadError(f"{path} must contain a JSON array of batch items")

    loaded: list[IngestItem] = []
    rejects: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        raw_spec = item.get("spec") if isinstance(item, dict) else None
        raw_candidate = item.get("candidate") if isinstance(item, dict) else None
        concept = (raw_spec or {}).get("concept", "unknown")
        try:
            template_id = item.get("prompt_template_id") if isinstance(item, dict) else None
            if template_id != REQUIRED_TEMPLATE_ID:
                raise IngestLoadError(
                    f"prompt_template_id must be {REQUIRED_TEMPLATE_ID!r}, got {template_id!r}",
                )
            if raw_spec is None:
                raise IngestLoadError("item missing required key 'spec'")
            if raw_candidate is None:
                raise IngestLoadError("item missing required key 'candidate'")
            spec = _build_spec(raw_spec)
            candidate = STBCandidate.model_validate(raw_candidate)
        except (IngestLoadError, ValidationError) as exc:
            detail = str(exc)
            report = {
                "stage": "load",
                "index": index,
                "spec": raw_spec,
                "candidate": raw_candidate,
                "error": detail,
            }
            write_reject_report(report, stage="load", concept=concept)
            rejects.append(report)
            logger.info("ingest item=%d stage=load concept=%s rejected: %s", index, concept, detail)
            continue
        loaded.append(IngestItem(spec=spec, candidate=candidate))
    return loaded, rejects


async def ingest_batch(
    session: AsyncSession,
    items: list[IngestItem],
    *,
    gate_client: Any,
    gate_model: str,
    generator_client: Any,
    generator_model: str,
    derive_predict_the_fix: bool = True,
    rng: random.Random | None = None,
    commit_after_each: bool = True,
) -> tuple[BatchReport, list[dict[str, Any]]]:
    """Run every loaded item through static -> sandbox -> semantic -> dedup ->
    explain -> publish, exactly as orchestrator._resolve_spec does for one
    generated candidate, minus generation itself (there is nothing to
    generate; the candidate already exists) and minus repair/best-of-N (there
    is exactly one candidate per spec, so neither applies).
    """
    rng = rng or random.Random()
    report = BatchReport(generator_model=generator_model, gate_model=gate_model)

    # D-57: prove the sandbox actually executes code before trusting a single
    # reject in this batch -- the same canary check a real orchestrator batch
    # runs at the top of run_batch().
    verify_sandbox_available()

    dedup_pool_hashes = await fetch_dedup_pool_hashes(session)
    recent_bug_mechanisms: dict[str, list[str]] = {}
    item_results: list[dict[str, Any]] = []

    for item in items:
        report.counts["specs_sampled"] += 1
        evaluation = _evaluate_candidate(
            item.candidate,
            item.spec,
            gate_client,
            AUTHOR_LABEL,
            REQUIRED_TEMPLATE_ID,
            dedup_pool_hashes,
            report,
            bucket="first_try",
        )

        if evaluation.survivor is None:
            rejection = evaluation.rejection
            assert rejection is not None  # no survivor implies a rejection
            _record_reject(
                report, item.spec, rejection.stage, evaluation.validation_report, item.candidate,
            )
            report.counts[f"concept:{item.spec.concept}:exhausted"] += 1
            report.spec_exhausted.append(item.spec)
            item_results.append(
                {
                    "concept": item.spec.concept,
                    "difficulty": item.spec.difficulty,
                    "outcome": "rejected",
                    "stage": rejection.stage,
                    "check": rejection.check,
                    "detail": rejection.evidence,
                },
            )
            if commit_after_each:
                await session.commit()
            continue

        published_before = len(report.published)
        ptf_before = len(report.ptf_published)
        await _publish_survivor(
            session,
            evaluation.survivor,
            generator_client,
            generator_model,
            dedup_pool_hashes,
            recent_bug_mechanisms,
            report,
            rng=rng,
            derive_predict_the_fix=derive_predict_the_fix,
            origin=ORIGIN,
        )
        stb_ref = (
            report.published[published_before] if len(report.published) > published_before else None
        )
        ptf_ref = (
            report.ptf_published[ptf_before] if len(report.ptf_published) > ptf_before else None
        )
        item_results.append(
            {
                "concept": item.spec.concept,
                "difficulty": item.spec.difficulty,
                "outcome": "published",
                "exercise_id": stb_ref[0] if stb_ref else None,
                "exercise_version": stb_ref[1] if stb_ref else None,
                "predict_the_fix": (
                    {"id": ptf_ref[0], "version": ptf_ref[1]} if ptf_ref else None
                ),
            },
        )
        if commit_after_each:
            await session.commit()

    report.generator_usage = getattr(generator_client, "usage", report.generator_usage)
    report.gate_usage = getattr(gate_client, "usage", report.gate_usage)
    report.log_summary()
    return report, item_results


def main(argv: list[str] | None = None) -> None:
    from app.db import create_engine, create_session_factory
    from pipeline.config import get_pipeline_settings
    from pipeline.llm_client import build_llm_client

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="python -m pipeline.ingest")
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="JSON array of {spec, prompt_template_id, candidate} objects",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for PTF choice shuffling")
    parser.add_argument(
        "--no-ptf",
        action="store_true",
        help="skip predict_the_fix derivation for surviving candidates",
    )
    args = parser.parse_args(argv)

    settings = get_pipeline_settings()
    # D-14 / D-87: these candidates were authored by Claude, so the judge MUST
    # be a genuinely different model family -- never Anthropic -- regardless of
    # what GATE_PROVIDER happens to be configured to for other pipeline runs.
    # Hard fail, not a warning: this is the whole point of the file-provider
    # path, not an optional nicety.
    if settings.GATE_PROVIDER != "openai":
        raise RuntimeError(
            "pipeline.ingest requires GATE_PROVIDER=openai (D-14/D-87: content authored by "
            f"Claude must be judged by a genuinely different model family), got "
            f"{settings.GATE_PROVIDER!r}",
        )
    if settings.GENERATOR_PROVIDER != "openai":
        raise RuntimeError(
            "pipeline.ingest requires GENERATOR_PROVIDER=openai (the predict_the_fix "
            f"distractor step must not route to Anthropic either), got "
            f"{settings.GENERATOR_PROVIDER!r}",
        )

    loaded, load_rejects = load_batch(args.file)
    logger.info(
        "ingest stage=%-20s count=%d",
        "load_passed",
        len(loaded),
    )
    logger.info(
        "ingest stage=%-20s count=%d",
        "load_rejected",
        len(load_rejects),
    )

    gate_client = build_llm_client(settings.GATE_PROVIDER, settings.GATE_MODEL)
    generator_client = build_llm_client(settings.GENERATOR_PROVIDER, settings.GENERATOR_MODEL)

    engine = create_engine(settings.DATABASE_URL)
    session_factory = create_session_factory(engine)

    async def _run() -> tuple[BatchReport, list[dict[str, Any]]]:
        async with session_factory() as session:
            result = await ingest_batch(
                session,
                loaded,
                gate_client=gate_client,
                gate_model=settings.GATE_MODEL,
                generator_client=generator_client,
                generator_model=settings.GENERATOR_MODEL,
                derive_predict_the_fix=not args.no_ptf,
                rng=random.Random(args.seed) if args.seed is not None else None,
                commit_after_each=True,
            )
            await session.commit()
        await engine.dispose()
        return result

    _report, item_results = asyncio.run(_run())
    for result in item_results:
        logger.info("ingest item concept=%-28s %s", result["concept"], json.dumps(result))


if __name__ == "__main__":
    main()
