"""Hand-authored predict_the_fix backfill (D-91): pipeline/ptf_ingest.py
derives a predict_the_fix from an ALREADY-PUBLISHED spot_the_bug using
hand-authored distractors instead of generate_wrong_fixes.

Per the house rule that a reporting path never observed to fire is not a
reporting path: a hand-authored distractor identical to the verified
fixed_code is not a distractor at all (a second correct answer), and the
ptf_sandbox_gate is right to reject it. This file proves that rejection
actually happens end to end, through the real database, and that it writes
its D-89 reject report.
"""

from __future__ import annotations

import json
import random

import pytest
from pipeline.llm_client import ScriptedLLMClient
from pipeline.orchestrator import run_batch
from pipeline.ptf_ingest import PTFIngestItem, ingest_batch
from pipeline.schemas import PredictFixCandidate
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise

_STB_SPEC = ExerciseSpec(
    type="spot_the_bug",
    concept="aliasing-vs-copy",
    difficulty=3,
    domain="checkout service",
    line_budget_min=1,
    line_budget_max=20,
    has_bug=True,
    avoid_patterns=(),
)

_BUGGY = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_FIXED = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_TEST = (
    "prices = {'A1': 100.0, 'B2': 50.0}\n"
    "result = apply_discount(prices, 10)\n"
    "assert result == {'A1': 90.0, 'B2': 45.0}\n"
    "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n"
)

_GOOD_STB_JSON = {
    "buggy_code": _BUGGY,
    "fixed_code": _FIXED,
    "bug_lines": [2],
    "test_code": _TEST,
    "context_note": "Runs once per order in the checkout worker.",
    "reason_options": [
        {"id": "a", "text": "The input price dict is mutated in place via aliasing."},
        {"id": "b", "text": "round() introduces floating point drift here."},
        {"id": "c", "text": "The loop skips the last SKU."},
        {"id": "d", "text": "discount_pct is applied twice."},
    ],
    "correct_reason_id": "a",
    "draft_explanation": {
        "summary": "updated = prices aliases the caller's dict instead of copying it.",
        "principle": "Copy a mutable argument before mutating it in place.",
        "line_notes": [{"line": 2, "note": "Binds updated to the same dict object as prices."}],
    },
    "concepts": ["aliasing-vs-copy"],
    "self_difficulty": 3,
    "self_check": {
        "single_bug_confirmed": True,
        "runs_without_error_on_happy_path": True,
        "no_hinting_names_or_comments": True,
        "distractors_verifiably_wrong": True,
    },
}
_DEFECT_AUDIT_RESPONSE = json.dumps(
    {
        "defects": [
            {
                "lines": [2],
                "description": "aliasing mutates caller's dict",
                "exposed_by": "mutation test",
            },
        ],
    },
)
_STB_SOLVER_RESPONSE = json.dumps(
    {"answer": {"line": 2, "reason_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
)
_REASONS_RESPONSE = json.dumps(
    {
        "verdicts": [
            {"id": "a", "classification": "correct", "justification": "j"},
            {"id": "b", "classification": "wrong", "justification": "j"},
            {"id": "c", "classification": "wrong", "justification": "j"},
            {"id": "d", "classification": "wrong", "justification": "j"},
        ],
    },
)

# Two genuinely plausible wrong fixes (still fail the test) plus one
# distractor that is byte-identical to _FIXED -- not wrong at all.
_WRONG_STILL_ALIASES = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in list(updated):\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_WRONG_DIRECTION = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 + discount_pct / 100), 2)\n"
    "    return updated\n"
)


async def _publish_stb(db_session: AsyncSession) -> Exercise:
    """Publish a real spot_the_bug row (derive_predict_the_fix=False, so no
    PTF is auto-derived) -- the already-published row the backfill entrypoint
    is meant to run against."""
    generator_client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])
    gate_client = ScriptedLLMClient(
        [_DEFECT_AUDIT_RESPONSE, _STB_SOLVER_RESPONSE, _REASONS_RESPONSE],
    )
    report = await run_batch(
        db_session,
        1,
        generator_client=generator_client,
        gate_client=gate_client,
        generator_model="generator-model-placeholder",
        specs=[_STB_SPEC],
        seed_history_from_db=False,
        derive_predict_the_fix=False,
    )
    assert report.counts["published_in_review"] == 1
    exercise_id, version = report.published[0]
    stb = await db_session.get(Exercise, (exercise_id, version))
    assert stb is not None
    return stb


@pytest.mark.asyncio
async def test_ptf_ingest_rejects_a_distractor_identical_to_fixed_code_and_writes_a_reject_report(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pipeline.config import PipelineSettings

    settings = PipelineSettings(VALIDATION_REPORTS_DIR=str(tmp_path))
    monkeypatch.setattr("pipeline.publish.get_pipeline_settings", lambda: settings)

    stb = await _publish_stb(db_session)
    # Task 1 (D-90) precondition: the database, not a batch file, is the
    # source of truth for fixed_code.
    assert stb.grading["artifacts"]["fixed_code"] == _FIXED

    bad_wrong_fixes = PredictFixCandidate(
        wrong_fixes=[
            {"code": _WRONG_STILL_ALIASES, "note": "still aliases and mutates the caller's dict"},
            {"code": _FIXED, "note": "actually correct"},
            {"code": _WRONG_DIRECTION, "note": "applies the discount in the wrong direction"},
        ],
    )
    item = PTFIngestItem(
        stb_exercise_id=stb.id,
        stb_exercise_version=stb.version,
        wrong_fixes=bad_wrong_fixes,
    )

    report, item_results = await ingest_batch(
        db_session, [item], rng=random.Random(0), commit_after_each=False,
    )

    assert report.counts["ptf_published_in_review"] == 0
    assert report.ptf_published == []
    assert report.counts["ptf_sandbox_gate_rejected"] == 1
    assert report.counts["concept:aliasing-vs-copy:ptf_rejected"] == 1
    assert item_results[0]["outcome"] == "rejected"
    assert item_results[0]["stage"] == "ptf_sandbox_gate"

    # No predict_the_fix row was actually created.
    ptf_rows = (
        await db_session.scalars(select(Exercise).where(Exercise.type == "predict_the_fix"))
    ).all()
    assert ptf_rows == []

    reject_files = sorted(
        (tmp_path / "rejects").glob("ptf_sandbox_gate_aliasing-vs-copy_*.json"),
    )
    assert len(reject_files) == 1
    payload = json.loads(reject_files[0].read_text(encoding="utf-8"))
    assert payload["stage"] == "ptf_sandbox_gate"
    assert payload["spec"]["concept"] == "aliasing-vs-copy"
    assert payload["candidate"]["buggy_code"] == _BUGGY
    assert payload["candidate"]["fixed_code"] == _FIXED
    assert any(w["code"] == _FIXED for w in payload["candidate"]["wrong_fixes"])
    checks = {c["name"]: c["passed"] for c in payload["sandbox_gate"]["checks"]}
    # The identical-to-fixed_code distractor is index 1 (0-indexed) in
    # wrong_fixes; it passes the test, so "still fails" is false.
    assert checks["distractor_1_still_fails_test"] is False
    # The other two genuinely-wrong distractors still fail as expected.
    assert checks["distractor_0_still_fails_test"] is True
    assert checks["distractor_2_still_fails_test"] is True


@pytest.mark.asyncio
async def test_ptf_ingest_publishes_a_ptf_from_hand_authored_distractors(
    db_session: AsyncSession,
) -> None:
    stb = await _publish_stb(db_session)

    good_wrong_fixes = PredictFixCandidate(
        wrong_fixes=[
            {"code": _WRONG_STILL_ALIASES, "note": "still aliases and mutates the caller's dict"},
            {"code": _WRONG_DIRECTION, "note": "applies the discount in the wrong direction"},
            {
                "code": (
                    "def apply_discount(prices, discount_pct):\n"
                    "    updated = dict(prices)\n"
                    "    for sku in updated:\n"
                    "        updated[sku] = round(updated[sku] - discount_pct, 2)\n"
                    "    return updated\n"
                ),
                "note": "subtracts the raw percentage number instead of scaling by price",
            },
        ],
    )
    item = PTFIngestItem(
        stb_exercise_id=stb.id,
        stb_exercise_version=stb.version,
        wrong_fixes=good_wrong_fixes,
    )

    report, item_results = await ingest_batch(
        db_session, [item], rng=random.Random(0), commit_after_each=False,
    )

    assert report.counts["ptf_published_in_review"] == 1
    assert len(report.ptf_published) == 1
    assert item_results[0]["outcome"] == "published"

    ptf = (
        await db_session.scalars(select(Exercise).where(Exercise.type == "predict_the_fix"))
    ).one()
    assert ptf.source["origin"] == "handauthored_claude"
    assert ptf.source["model"] == "claude"
    assert ptf.source["derived_from"]["id"] == str(stb.id)
    correct_id = ptf.grading["correct_choice_id"]
    correct_choice = next(c for c in ptf.payload["choices"] if c["id"] == correct_id)
    assert correct_choice["text"] == _FIXED
