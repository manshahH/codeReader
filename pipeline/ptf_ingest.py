"""Hand-authored predict_the_fix backfill, derived from an ALREADY-PUBLISHED
spot_the_bug (D-91).

Peer to `pipeline/ingest.py` (D-87): same "reuse the gate chain verbatim,
never build a parallel one" law, applied to the OTHER half of the PTF
contract. Where `ingest.py` hand-authors a spot_the_bug and derives its PTF
in the same batch (via `orchestrator._publish_survivor`), this module skips
generation entirely -- the STB already exists, sandbox-verified, in the
database (D-90 made its `fixed_code` recoverable) -- and derives a PTF from
hand-WRITTEN distractors instead of `generate_wrong_fixes`.

Reused, unmodified:
  * `predict_the_fix.derive_artifacts` -- static_gate + validate_predict_the_fix
    + payload/grading/explanation assembly. Takes no LLM client; nothing here
    calls it differently than the orchestrator does.
  * `orchestrator.BatchReport` / `orchestrator._record_ptf_reject` -- the
    EXACT D-89 reject-report machinery, not a reimplementation.
  * `publish.insert_predict_the_fix` -- now accepting `origin=
    "handauthored_claude"` (D-91) instead of the orchestrator's implicit "llm".

Deliberately NOT touched: `orchestrator._evaluate_candidate` gains no PTF
branch (its STB/trace gate chains -- static+sandbox+semantic -- do not apply
to a PTF derivation, which is static_gate-on-distractors + sandbox only, no
semantic gates at all); `generate_wrong_fixes` is never called (there is no
generation step for hand-authored content).

Input: a JSON array of
  {"stb_exercise_id": "<uuid>", "stb_exercise_version": <int>,
   "prompt_template_id": "handauthored_ptf_v1",
   "wrong_fixes": [{"code": "...", "note": "..."}, ... exactly 3]}
objects. The STB half (buggy_code, fixed_code, test_code, context_note,
explanation summary/principle, concepts) is read from the database, never
from a batch file -- the database is the source of truth (D-90).

Usage: python -m pipeline.ptf_ingest --file <path>
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import random
import uuid
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.orchestrator import BatchReport, _record_ptf_reject
from pipeline.predict_the_fix import derive_artifacts
from pipeline.publish import (
    derived_ptf_exists,
    fetch_stb_for_ptf_derivation,
    insert_predict_the_fix,
    write_reject_report,
)
from pipeline.schemas import PredictFixCandidate
from pipeline.spec_sampler import ExerciseSpec, line_budget_for_difficulty

logger = logging.getLogger(__name__)

# D-91 provenance tags, mirroring ingest.py's D-87 ORIGIN/AUTHOR_LABEL split:
# ORIGIN names the ingestion PATH (permanently distinguishes this from
# orchestrator-derived "llm" PTFs); AUTHOR_LABEL is who/what wrote the
# distractors, stored as the PTF's own source.model (there is no LLM call
# here, so it is never an llm_client model string).
ORIGIN = "handauthored_claude"
AUTHOR_LABEL = "claude"
REQUIRED_TEMPLATE_ID = "handauthored_ptf_v1"
_DEFAULT_DOMAIN = "hand-authored predict_the_fix backfill"


class PTFIngestLoadError(RuntimeError):
    """A batch item, or the spot_the_bug row it points at, could not be
    resolved into something derive_artifacts can run on: bad UUID/shape, an
    unknown/wrong-type/no-longer-published STB id, or (D-90) an STB row
    published before the fixed_code fix and never backfilled."""


@dataclasses.dataclass(frozen=True)
class _DraftExplanationView:
    summary: str
    principle: str


@dataclasses.dataclass(frozen=True)
class _STBView:
    """Duck-typed to exactly the attributes `predict_the_fix.derive_artifacts`
    reads off an STBCandidate: buggy_code, fixed_code, test_code,
    context_note, draft_explanation.{summary,principle}. Reconstructed from an
    ALREADY-PUBLISHED spot_the_bug row -- deliberately NOT a full STBCandidate:
    reason_options/correct_reason_id/bug_lines/self_check/self_difficulty are
    either not persisted or not read by derive_artifacts, so fabricating them
    would only manufacture fake provenance for fields nothing downstream uses.
    """

    buggy_code: str
    fixed_code: str
    test_code: str
    context_note: str
    draft_explanation: _DraftExplanationView


@dataclasses.dataclass(frozen=True)
class PTFIngestItem:
    stb_exercise_id: uuid.UUID
    stb_exercise_version: int
    wrong_fixes: PredictFixCandidate


def _build_stb_view(stb_exercise: Any) -> _STBView:
    payload = stb_exercise.payload
    grading = stb_exercise.grading
    explanation = stb_exercise.explanation
    artifacts = grading.get("artifacts", {}) if isinstance(grading, dict) else {}
    fixed_code = artifacts.get("fixed_code")
    if not fixed_code:
        raise PTFIngestLoadError(
            f"spot_the_bug {stb_exercise.id} v{stb_exercise.version} has no "
            "grading.artifacts.fixed_code -- published before D-90 and never "
            "backfilled (backend/scripts/backfill_stb_fixed_code.py), or an "
            "origin='llm' row whose fixed_code was never recoverable at all",
        )
    return _STBView(
        buggy_code=payload["code"],
        fixed_code=fixed_code,
        test_code=artifacts["failing_test"],
        context_note=payload["context_note"],
        draft_explanation=_DraftExplanationView(
            summary=explanation["summary"],
            principle=explanation["principle"],
        ),
    )


def load_batch(path: Path) -> tuple[list[PTFIngestItem], list[dict[str, Any]]]:
    """Parse and schema-validate every item's `wrong_fixes` (pure, no DB --
    the STB half is resolved against the database in `ingest_batch`).

    Returns (loaded, load_rejects); each load_rejects entry is the report
    already written to validation_reports_dir/rejects/ (stage="load").
    """
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list):
        raise PTFIngestLoadError(f"{path} must contain a JSON array of batch items")

    loaded: list[PTFIngestItem] = []
    rejects: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        try:
            if not isinstance(item, dict):
                raise PTFIngestLoadError(f"item {index} must be a JSON object")
            template_id = item.get("prompt_template_id")
            if template_id != REQUIRED_TEMPLATE_ID:
                raise PTFIngestLoadError(
                    f"prompt_template_id must be {REQUIRED_TEMPLATE_ID!r}, got {template_id!r}",
                )
            raw_id = item.get("stb_exercise_id")
            raw_version = item.get("stb_exercise_version")
            if raw_id is None or raw_version is None:
                raise PTFIngestLoadError(
                    "item missing required key 'stb_exercise_id' or 'stb_exercise_version'",
                )
            try:
                stb_exercise_id = uuid.UUID(str(raw_id))
            except ValueError as exc:
                raise PTFIngestLoadError(f"stb_exercise_id {raw_id!r} is not a valid UUID") from exc
            if "wrong_fixes" not in item:
                raise PTFIngestLoadError("item missing required key 'wrong_fixes'")
            wrong_fixes = PredictFixCandidate.model_validate({"wrong_fixes": item["wrong_fixes"]})
        except (PTFIngestLoadError, ValidationError) as exc:
            detail = str(exc)
            report = {"stage": "load", "index": index, "item": item, "error": detail}
            write_reject_report(report, stage="load", concept="unknown")
            rejects.append(report)
            logger.info("ptf_ingest item=%d stage=load rejected: %s", index, detail)
            continue
        loaded.append(
            PTFIngestItem(
                stb_exercise_id=stb_exercise_id,
                stb_exercise_version=int(raw_version),
                wrong_fixes=wrong_fixes,
            ),
        )
    return loaded, rejects


async def ingest_batch(
    session: AsyncSession,
    items: list[PTFIngestItem],
    *,
    rng: random.Random | None = None,
    commit_after_each: bool = True,
) -> tuple[BatchReport, list[dict[str, Any]]]:
    """Resolve each item's STB source from the database, then run
    static_gate + validate_predict_the_fix (via `derive_artifacts`, untouched)
    against the hand-written distractors, exactly as
    `orchestrator._derive_and_publish_ptf` does for an LLM-generated one --
    minus `generate_wrong_fixes` (nothing to generate) and minus repair/
    best-of-N (one hand-authored candidate per spec, same as ingest.py).
    """
    rng = rng or random.Random()
    report = BatchReport(generator_model=AUTHOR_LABEL, gate_model="")
    item_results: list[dict[str, Any]] = []

    for item in items:
        report.counts["specs_sampled"] += 1
        label = f"{item.stb_exercise_id} v{item.stb_exercise_version}"

        stb_exercise = await fetch_stb_for_ptf_derivation(
            session, item.stb_exercise_id, item.stb_exercise_version,
        )
        if stb_exercise is None:
            detail = f"no in_review/live spot_the_bug row at {label}"
            write_reject_report(
                {"stage": "ptf_stb_not_found", "stb_exercise": label, "error": detail},
                stage="ptf_stb_not_found",
                concept="unknown",
            )
            report.counts["ptf_stb_not_found_rejected"] += 1
            item_results.append({"stb_exercise": label, "outcome": "rejected", "detail": detail})
            continue

        if await derived_ptf_exists(session, item.stb_exercise_id, item.stb_exercise_version):
            logger.info("ptf_ingest stb=%s already has a derived predict_the_fix, skipping", label)
            report.counts["ptf_already_derived_skipped"] += 1
            item_results.append({"stb_exercise": label, "outcome": "skipped_already_derived"})
            continue

        concept = stb_exercise.concepts[0] if stb_exercise.concepts else "unknown"
        line_budget_min, line_budget_max = line_budget_for_difficulty(
            stb_exercise.difficulty_authored,
        )
        spec = ExerciseSpec(
            type="spot_the_bug",
            concept=concept,
            difficulty=stb_exercise.difficulty_authored,
            domain=_DEFAULT_DOMAIN,
            line_budget_min=line_budget_min,
            line_budget_max=line_budget_max,
            has_bug=True,
            avoid_patterns=(),
        )

        try:
            stb_view = _build_stb_view(stb_exercise)
        except PTFIngestLoadError as exc:
            write_reject_report(
                {
                    "stage": "ptf_source_incomplete",
                    "spec": dataclasses.asdict(spec),
                    "error": str(exc),
                },
                stage="ptf_source_incomplete",
                concept=concept,
            )
            report.counts["ptf_source_incomplete_rejected"] += 1
            report.counts[f"concept:{concept}:ptf_rejected"] += 1
            item_results.append({"stb_exercise": label, "outcome": "rejected", "detail": str(exc)})
            continue

        report.counts["ptf_derivation_attempted"] += 1
        ptf = derive_artifacts(
            stb_candidate=stb_view,
            wrong_fixes=item.wrong_fixes,
            rng=rng,
            line_budget_max=line_budget_max,
        )
        if not ptf.survived:
            assert ptf.reject_stage is not None  # not survived implies a reject stage
            _record_ptf_reject(
                report, spec, ptf.reject_stage, ptf.validation_report, stb_view, item.wrong_fixes,
            )
            item_results.append(
                {
                    "stb_exercise": label,
                    "outcome": "rejected",
                    "stage": ptf.reject_stage,
                    "concept": concept,
                },
            )
            if commit_after_each:
                await session.commit()
            continue

        artifacts = ptf.artifacts
        assert artifacts is not None  # survived implies not None
        stb_source = stb_exercise.source if isinstance(stb_exercise.source, dict) else {}
        ptf_exercise = await insert_predict_the_fix(
            session,
            concepts=list(stb_exercise.concepts),
            difficulty_authored=stb_exercise.difficulty_authored,
            payload=artifacts.payload,
            grading=artifacts.grading,
            explanation=artifacts.explanation,
            content_hash=artifacts.content_hash,
            validation_report=ptf.validation_report,
            generator_model=AUTHOR_LABEL,
            derived_from_id=stb_exercise.id,
            derived_from_version=stb_exercise.version,
            stb_template_id=stb_source.get("prompt_template_id"),
            origin=ORIGIN,
        )
        report.counts["ptf_published_in_review"] += 1
        report.counts[f"concept:{concept}:ptf_published"] += 1
        report.ptf_published.append((str(ptf_exercise.id), ptf_exercise.version))
        item_results.append(
            {
                "stb_exercise": label,
                "outcome": "published",
                "predict_the_fix": {"id": str(ptf_exercise.id), "version": ptf_exercise.version},
            },
        )
        if commit_after_each:
            await session.commit()

    report.log_summary()
    return report, item_results


def main(argv: list[str] | None = None) -> None:
    from app.db import create_engine, create_session_factory
    from pipeline.config import get_pipeline_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="python -m pipeline.ptf_ingest")
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="JSON array of {stb_exercise_id, stb_exercise_version, prompt_template_id, "
        "wrong_fixes} objects",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for choice shuffling")
    args = parser.parse_args(argv)

    settings = get_pipeline_settings()
    loaded, load_rejects = load_batch(args.file)
    logger.info("ptf_ingest stage=%-20s count=%d", "load_passed", len(loaded))
    logger.info("ptf_ingest stage=%-20s count=%d", "load_rejected", len(load_rejects))

    engine = create_engine(settings.DATABASE_URL)
    session_factory = create_session_factory(engine)

    async def _run() -> tuple[BatchReport, list[dict[str, Any]]]:
        async with session_factory() as session:
            result = await ingest_batch(
                session,
                loaded,
                rng=random.Random(args.seed) if args.seed is not None else None,
                commit_after_each=True,
            )
            await session.commit()
        await engine.dispose()
        return result

    _report, item_results = asyncio.run(_run())
    for result in item_results:
        logger.info("ptf_ingest item stb=%-40s %s", result["stb_exercise"], json.dumps(result))


if __name__ == "__main__":
    main()
