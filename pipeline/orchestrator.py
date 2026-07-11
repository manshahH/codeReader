"""Content pipeline orchestrator.

SPEC SAMPLER -> GENERATOR -> STATIC GATE -> SANDBOX GATE -> SEMANTIC GATES ->
DEDUP -> EXPLAIN -> REVIEW QUEUE (docs/01). Runs N candidates end to end,
logging per-stage pass/reject counts.

Retry policy (prompts/README.md): a gate rejection regenerates a FRESH
candidate from the SAME spec, up to MAX_ATTEMPTS_PER_SPEC times, before
giving up on that spec (recorded in BatchReport.spec_exhausted) and moving on
to the next sampled spec. Gates never repair (D-10).
"""

from __future__ import annotations

import collections
import dataclasses
import logging
import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline import dedup, static_gate
from pipeline.explain import finalize_stb_explanation, finalize_trace_explanation
from pipeline.generate import generate_candidate
from pipeline.llm_client import LLMClient
from pipeline.publish import (
    fetch_live_pool_hashes,
    insert_candidate,
    seed_recent_bug_mechanisms,
    write_reject_report,
)
from pipeline.sandbox.runner import verify_sandbox_available
from pipeline.sandbox_gate import validate_spot_the_bug, validate_trace
from pipeline.schemas import STBCandidate, TraceCandidate
from pipeline.semantic_gates import GateVerdict, defect_audit, reasons, solver
from pipeline.spec_sampler import ExerciseSpec, sample_spec

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_SPEC = 3


@dataclasses.dataclass
class BatchReport:
    counts: collections.Counter = dataclasses.field(default_factory=collections.Counter)
    published: list[tuple[str, int]] = dataclasses.field(default_factory=list)
    spec_exhausted: list[ExerciseSpec] = dataclasses.field(default_factory=list)

    def log_summary(self) -> None:
        for stage in sorted(self.counts):
            logger.info("orchestrator stage=%-35s count=%d", stage, self.counts[stage])
        logger.info(
            "orchestrator stage=%-35s count=%d",
            "published_in_review",
            len(self.published),
        )
        logger.info(
            "orchestrator stage=%-35s count=%d",
            "spec_exhausted",
            len(self.spec_exhausted),
        )


def _static_gate_check(
    candidate: STBCandidate | TraceCandidate,
    spec: ExerciseSpec,
) -> tuple[bool, list[str]]:
    budget = (spec.line_budget_min, spec.line_budget_max)
    if isinstance(candidate, STBCandidate):
        # The line budget is a UX constraint on what the user READS, which is
        # buggy_code only. The fix may legitimately insert lines (D-46), so
        # fixed_code near the top of the budget must not overflow into a
        # reject (D-51); every non-length check still runs on both snippets.
        buggy = static_gate.check(candidate.buggy_code, line_budget=budget)
        fixed = static_gate.check(candidate.fixed_code, line_budget=None)
        return (buggy.accepted and fixed.accepted), (buggy.violations + fixed.violations)
    trace_result = static_gate.check(candidate.code, line_budget=budget)
    return trace_result.accepted, trace_result.violations


def _candidate_snapshot(candidate: STBCandidate | TraceCandidate) -> dict[str, Any]:
    if isinstance(candidate, STBCandidate):
        return {
            "buggy_code": candidate.buggy_code,
            "fixed_code": candidate.fixed_code,
            "test_code": candidate.test_code,
            "bug_lines": candidate.bug_lines,
        }
    return {"code": candidate.code, "expected_stdout": candidate.expected_stdout}


def _record_reject(
    report: BatchReport,
    spec: ExerciseSpec,
    stage: str,
    validation_report: dict[str, Any],
    candidate: STBCandidate | TraceCandidate,
) -> None:
    """Count a rejection and persist its receipts (D-48).

    The per-check report used to be discarded on any reject, leaving only an
    aggregate counter -- a funnel with no per-check telemetry. Every reject
    now writes the full report (stage, spec, candidate code, and each gate's
    check details including stderr) to validation_reports_dir/rejects.
    """
    report.counts[f"{stage}_rejected"] += 1
    report.counts[f"concept:{spec.concept}:rejected"] += 1
    write_reject_report(
        {
            "stage": stage,
            "spec": dataclasses.asdict(spec),
            "candidate": _candidate_snapshot(candidate),
            **validation_report,
        },
        stage=stage,
        concept=spec.concept,
    )


def _run_stb_semantic_gates(
    candidate: STBCandidate,
    spec: ExerciseSpec,
    gate_client: LLMClient,
    report: dict[str, Any],
    verified_bug_lines: list[int],
) -> tuple[bool, Any]:
    """Returns (survived, defect_audit_outcome) -- the outcome feeds explain.py.

    `verified_bug_lines` is the sandbox gate's diff-derived answer key (D-49),
    not the generator's claim; every downstream gate judges against the
    execution-proven lines.
    """
    has_bug = bool(spec.has_bug)

    defect_outcome = defect_audit(
        candidate.buggy_code,
        has_bug=has_bug,
        bug_lines=verified_bug_lines,
        llm_client=gate_client,
    )
    report["defect_audit"] = defect_outcome.as_report()
    if defect_outcome.verdict == GateVerdict.REJECT:
        return False, defect_outcome

    solver_payload = {
        "code": candidate.buggy_code,
        "context_note": candidate.context_note,
        "reason_options": [o.model_dump() for o in candidate.reason_options],
    }
    has_a_bug_line = has_bug and bool(verified_bug_lines)
    correct_answer = (
        {"line": verified_bug_lines[0], "reason_id": candidate.correct_reason_id}
        if has_a_bug_line
        else {"reason_id": candidate.correct_reason_id}
    )
    solver_outcome = solver(
        solver_payload,
        correct_answer=correct_answer,
        llm_client=gate_client,
        compare_keys=None if has_a_bug_line else {"reason_id"},
        # D-52: every verified bug line is a correct answer for a multi-line
        # bug; keying to one exact line wrongly rejected a solver that named
        # another of them.
        acceptable_lines=verified_bug_lines if has_a_bug_line else None,
    )
    report["solver"] = solver_outcome.as_report()
    if solver_outcome.verdict == GateVerdict.REJECT:
        return False, defect_outcome

    reasons_outcome = reasons(
        candidate.buggy_code,
        reason_options=[o.model_dump() for o in candidate.reason_options],
        correct_reason_id=candidate.correct_reason_id,
        llm_client=gate_client,
    )
    report["reasons"] = reasons_outcome.as_report()
    if reasons_outcome.verdict == GateVerdict.REJECT:
        return False, defect_outcome

    return True, defect_outcome


def _run_trace_semantic_gates(
    candidate: TraceCandidate,
    gate_client: LLMClient,
    report: dict[str, Any],
) -> bool:
    payload = {
        "code": candidate.code,
        "context_note": candidate.context_note,
        "question": candidate.question,
        "choices": [c.model_dump() for c in candidate.choices],
    }
    solver_outcome = solver(
        payload,
        correct_answer={"choice_id": candidate.correct_choice_id},
        llm_client=gate_client,
    )
    report["solver"] = solver_outcome.as_report()
    return solver_outcome.verdict != GateVerdict.REJECT


async def _attempt_one(
    session: AsyncSession,
    spec: ExerciseSpec,
    generator_client: LLMClient,
    gate_client: LLMClient,
    generator_model: str,
    live_pool_hashes: set[str],
    recent_bug_mechanisms: dict[str, list[str]],
    report: BatchReport,
) -> bool:
    """One end-to-end attempt for `spec`. Returns True iff it was published."""
    outcome = generate_candidate(spec, generator_client)
    report.counts["generated_total"] += 1
    if not outcome.survived:
        report.counts[f"generate_discarded:{outcome.discard_reason}"] += 1
        report.counts[f"concept:{spec.concept}:rejected"] += 1
        return False
    report.counts["generate_passed"] += 1
    candidate = outcome.candidate
    assert candidate is not None  # survived implies not None

    static_ok, static_violations = _static_gate_check(candidate, spec)
    validation_report: dict[str, Any] = {
        "template_id": outcome.template_id,
        "static_gate": {"accepted": static_ok, "violations": static_violations},
    }
    if not static_ok:
        _record_reject(report, spec, "static_gate", validation_report, candidate)
        return False
    report.counts["static_gate_passed"] += 1

    captured_stdout: str | None = None
    verified_bug_lines: list[int] | None = None
    defect_audit_outcome = None

    if isinstance(candidate, STBCandidate):
        has_bug = bool(spec.has_bug)
        sandbox_result = validate_spot_the_bug(candidate, has_bug=has_bug)
        validation_report["sandbox_gate"] = sandbox_result.as_report()
        if not sandbox_result.accepted:
            _record_reject(report, spec, "sandbox_gate", validation_report, candidate)
            return False
        report.counts["sandbox_gate_passed"] += 1
        # D-49: the answer key is the diff-derived lines the sandbox verified,
        # never the generator's claim. A claim/diff mismatch on a survivor is
        # a template-quality metric (D-11 style), not a reject.
        verified_bug_lines = sandbox_result.verified_bug_lines or []
        if sandbox_result.bug_lines_claim_mismatch:
            report.counts["stb_bug_lines_claim_mismatch"] += 1

        survived, defect_audit_outcome = _run_stb_semantic_gates(
            candidate,
            spec,
            gate_client,
            validation_report,
            verified_bug_lines,
        )
        if not survived:
            _record_reject(report, spec, "semantic_gate", validation_report, candidate)
            return False
        report.counts["semantic_gate_passed"] += 1

        code_for_dedup = candidate.buggy_code
    else:
        sandbox_result = validate_trace(candidate)
        validation_report["sandbox_gate"] = sandbox_result.as_report()
        if not sandbox_result.accepted:
            _record_reject(report, spec, "sandbox_gate", validation_report, candidate)
            return False
        report.counts["sandbox_gate_passed"] += 1
        captured_stdout = sandbox_result.captured_stdout

        survived = _run_trace_semantic_gates(candidate, gate_client, validation_report)
        if not survived:
            _record_reject(report, spec, "semantic_gate", validation_report, candidate)
            return False
        report.counts["semantic_gate_passed"] += 1

        code_for_dedup = candidate.code

    content_hash = dedup.content_hash(code_for_dedup)
    if dedup.is_duplicate(code_for_dedup, live_pool_hashes):
        _record_reject(report, spec, "dedup", validation_report, candidate)
        return False
    report.counts["dedup_passed"] += 1
    live_pool_hashes.add(content_hash)  # this run's own candidates count too

    if isinstance(candidate, STBCandidate):
        final = finalize_stb_explanation(
            candidate,
            has_bug=bool(spec.has_bug),
            verified_bug_lines=verified_bug_lines or [],
            defect_audit_outcome=defect_audit_outcome,
        )
    else:
        final = finalize_trace_explanation(candidate, captured_stdout=captured_stdout or "")
    validation_report["explanation"] = {
        "mismatch_flagged": final.mismatch_flagged,
        "mismatch_detail": final.mismatch_detail,
    }

    exercise = await insert_candidate(
        session,
        spec,
        candidate,
        final_explanation=final.explanation,
        content_hash=content_hash,
        validation_report=validation_report,
        generator_model=generator_model,
        captured_stdout=captured_stdout,
        verified_bug_lines=verified_bug_lines,
    )
    report.counts["published_in_review"] += 1
    report.counts[f"concept:{spec.concept}:published"] += 1
    report.published.append((str(exercise.id), exercise.version))

    if isinstance(candidate, STBCandidate) and spec.has_bug:
        correct_option = next(
            (o for o in candidate.reason_options if o.id == candidate.correct_reason_id),
            None,
        )
        if correct_option is not None:
            recent_bug_mechanisms.setdefault(spec.concept, []).insert(0, correct_option.text)

    return True


async def run_batch(
    session: AsyncSession,
    n: int,
    *,
    generator_client: LLMClient,
    gate_client: LLMClient,
    generator_model: str,
    rng: random.Random | None = None,
    type_mix: tuple[str, ...] = ("spot_the_bug", "trace"),
    seed_history_from_db: bool = True,
    specs: list[ExerciseSpec] | None = None,
) -> BatchReport:
    """Run n candidates end to end.

    `specs` lets callers (tests) inject exact specs instead of sampling from
    `rng`, so a fixed candidate fixture's line count doesn't have to satisfy
    whatever line budget the RNG happens to sample. Real batches never pass
    it; n and rng drive sampling as usual.
    """
    rng = rng or random.Random()
    report = BatchReport()

    # D-57: prove the sandbox actually executes code before trusting any of
    # this batch's rejections -- see verify_sandbox_available's docstring.
    verify_sandbox_available()

    recent_bug_mechanisms = (
        await seed_recent_bug_mechanisms(session) if seed_history_from_db else {}
    )
    live_pool_hashes = await fetch_live_pool_hashes(session)

    for i in range(n):
        spec = (
            specs[i]
            if specs is not None
            else sample_spec(
                rng,
                type_mix[i % len(type_mix)],
                recent_bug_mechanisms=recent_bug_mechanisms,
            )
        )
        report.counts["specs_sampled"] += 1

        published = False
        for _attempt in range(MAX_ATTEMPTS_PER_SPEC):
            published = await _attempt_one(
                session,
                spec,
                generator_client,
                gate_client,
                generator_model,
                live_pool_hashes,
                recent_bug_mechanisms,
                report,
            )
            if published:
                break
        if not published:
            report.counts[f"concept:{spec.concept}:exhausted"] += 1
            report.spec_exhausted.append(spec)

    report.log_summary()
    return report


def _demo_mock_clients(n: int) -> tuple[LLMClient, LLMClient, list[ExerciseSpec]]:
    """A trivially-passing scripted pair for `--mock` CLI demo runs only.

    Real batches sample specs from the taxonomy via the RNG and wire a real
    client (per GENERATOR_PROVIDER/GATE_PROVIDER, via build_llm_client) for
    both models; tests build their own ScriptedLLMClient
    sequences to exercise specific pass/reject paths. This demo path uses two
    FIXED specs (one per type) sized to match the two fixed demo candidates'
    actual line counts -- sampling real random specs here would size-mismatch
    the fixed candidates against a randomly sampled line budget on every other
    attempt, which defeats the point of a clean illustrative run.
    """
    import json as _json


    stb_spec = ExerciseSpec(
        type="spot_the_bug",
        concept="aliasing-vs-copy",
        difficulty=3,
        domain="checkout service",
        line_budget_min=1,
        line_budget_max=20,
        has_bug=True,
        avoid_patterns=(),
    )
    trace_spec = ExerciseSpec(
        type="trace",
        concept="control_flow",
        difficulty=1,
        domain="checkout service",
        line_budget_min=1,
        line_budget_max=20,
        has_bug=None,
        avoid_patterns=(),
    )
    specs = [stb_spec if i % 2 == 0 else trace_spec for i in range(n)]

    good_stb = {
        "buggy_code": "def apply_discount(prices, discount_pct):\n"
        "    updated = prices\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n",
        "fixed_code": "def apply_discount(prices, discount_pct):\n"
        "    updated = dict(prices)\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n",
        "bug_lines": [2],
        "test_code": "prices = {'A1': 100.0}\n"
        "result = apply_discount(prices, 10)\n"
        "assert result == {'A1': 90.0}\n"
        "assert prices == {'A1': 100.0}, 'input dict was mutated'\n",
        "context_note": "Runs once per order in the checkout worker.",
        "reason_options": [
            {"id": "a", "text": "The input dict is aliased and mutated in place"},
            {"id": "b", "text": "round() drifts here"},
            {"id": "c", "text": "The loop skips the last item"},
            {"id": "d", "text": "The discount is applied twice"},
        ],
        "correct_reason_id": "a",
        "draft_explanation": {
            "summary": "updated = prices aliases the caller's dict instead of copying it.",
            "principle": "Copy a mutable argument before mutating it in place.",
            "line_notes": [{"line": 2, "note": "binds updated to the same dict as prices"}],
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
    good_trace = {
        "code": "print(sum([1, 2, 3]))\n",
        "context_note": "Runs in the nightly reconciliation job.",
        "question": "What does this code print?",
        "expected_stdout": "6",
        "choices": [
            {"id": "a", "text": "6", "misconception": None},
            {"id": "b", "text": "5", "misconception": "miscounted the list"},
            {"id": "c", "text": "1", "misconception": "stopped after the first element"},
            {"id": "d", "text": "0", "misconception": "assumed an explicit start of 1"},
        ],
        "correct_choice_id": "a",
        "draft_explanation": {
            "summary": "sum([1, 2, 3]) prints 6.",
            "principle": "sum() folds left to right over the iterable.",
            "trace_table": [{"line": 1, "state": "n/a"}],
            "why_wrong": [
                {"choice_id": "b", "note": "miscounted the list"},
                {"choice_id": "c", "note": "stopped after the first element"},
                {"choice_id": "d", "note": "assumed an explicit start of 1"},
            ],
        },
        "concepts": ["control_flow"],
        "self_difficulty": 1,
        "self_check": {
            "traced_line_by_line_not_from_memory": True,
            "output_deterministic_and_repr_stable": True,
            "each_distractor_derived_from_named_misconception": True,
            "no_two_choices_identical": True,
        },
    }
    good_stb_2 = {
        **good_stb,
        "buggy_code": good_stb["buggy_code"].replace("apply_discount", "apply_markdown"),
        "fixed_code": good_stb["fixed_code"].replace("apply_discount", "apply_markdown"),
        "test_code": good_stb["test_code"].replace("apply_discount", "apply_markdown"),
    }
    good_trace_2 = {
        **good_trace,
        "code": "print(sum([10, 20, 30]))\n",
        "expected_stdout": "60",
        "choices": [
            {"id": "a", "text": "60", "misconception": None},
            {"id": "b", "text": "50", "misconception": "miscounted the list"},
            {"id": "c", "text": "10", "misconception": "stopped after the first element"},
            {"id": "d", "text": "0", "misconception": "assumed an explicit start of 1"},
        ],
    }

    class _ContentAwareDemoClient:
        """Routes each call by a set of marker substrings that must ALL appear
        in the prompt, cycling through a few content variants per marker set
        so consecutive same-type candidates aren't byte-identical (which
        dedup would, correctly, reject). Solver serves both types from one
        template, so its two entries are disambiguated by a second marker
        that only appears in one type's JSON payload ("reason_options" is
        spot_the_bug-only, "choices" is trace-only).
        """

        def __init__(self, variants_by_markers: dict[tuple[str, ...], list[str]]) -> None:
            self._variants_by_markers = variants_by_markers
            self._counters = dict.fromkeys(variants_by_markers, 0)

        def complete(self, *, system: str, user: str, temperature: float) -> str:  # noqa: ARG002
            for markers, variants in self._variants_by_markers.items():
                if all(marker in user for marker in markers):
                    index = self._counters[markers] % len(variants)
                    self._counters[markers] += 1
                    return variants[index]
            raise RuntimeError(f"no demo response configured for prompt: {user[:80]!r}")

    generator = _ContentAwareDemoClient(
        {
            ('Create one "spot the bug" exercise.',): [
                _json.dumps(good_stb),
                _json.dumps(good_stb_2),
            ],
            ('Create one "trace the output" exercise.',): [
                _json.dumps(good_trace),
                _json.dumps(good_trace_2),
            ],
        },
    )
    gate = _ContentAwareDemoClient(
        {
            ("auditing a piece of Python",): [
                _json.dumps(
                    {
                        "defects": [
                            {
                                "lines": [2],
                                "description": "aliasing",
                                "exposed_by": "mutation test",
                            },
                        ],
                    },
                ),
            ],
            ("For EACH candidate, classify it",): [
                _json.dumps(
                    {
                        "verdicts": [
                            {"id": "a", "classification": "correct", "justification": "j"},
                            {"id": "b", "classification": "wrong", "justification": "j"},
                            {"id": "c", "classification": "wrong", "justification": "j"},
                            {"id": "d", "classification": "wrong", "justification": "j"},
                        ],
                    },
                ),
            ],
            ("taking a code-reading exercise", "reason_options"): [
                _json.dumps(
                    {
                        "answer": {"line": 2, "reason_id": "a"},
                        "confidence": 0.95,
                        "problems_with_the_exercise": [],
                    },
                ),
            ],
            ("taking a code-reading exercise", "choices"): [
                _json.dumps(
                    {
                        "answer": {"choice_id": "a"},
                        "confidence": 0.95,
                        "problems_with_the_exercise": [],
                    },
                ),
            ],
        },
    )
    return generator, gate, specs


def main(argv: list[str] | None = None) -> None:
    import argparse
    import asyncio

    from app.db import create_engine, create_session_factory
    from pipeline.config import get_pipeline_settings
    from pipeline.llm_client import build_llm_client

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="python -m pipeline.orchestrator")
    parser.add_argument("--n", type=int, default=20, help="number of candidates to attempt")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for the spec sampler")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="use a trivially-passing scripted LLM pair instead of the real LLM provider",
    )
    args = parser.parse_args(argv)

    async def _run() -> None:
        settings = get_pipeline_settings()
        specs = None
        if args.mock:
            generator_client, gate_client, specs = _demo_mock_clients(args.n)
            generator_model = "mock-generator"
        else:
            generator_client = build_llm_client(
                settings.GENERATOR_PROVIDER, settings.GENERATOR_MODEL,
            )
            gate_client = build_llm_client(settings.GATE_PROVIDER, settings.GATE_MODEL)
            generator_model = settings.GENERATOR_MODEL

        engine = create_engine(settings.DATABASE_URL)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await run_batch(
                session,
                args.n,
                generator_client=generator_client,
                gate_client=gate_client,
                generator_model=generator_model,
                rng=random.Random(args.seed) if args.seed is not None else None,
                specs=specs,
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
