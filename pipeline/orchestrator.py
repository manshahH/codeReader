"""Content pipeline orchestrator.

SPEC SAMPLER -> GENERATOR -> STATIC GATE -> SANDBOX GATE -> SEMANTIC GATES ->
DEDUP -> EXPLAIN -> REVIEW QUEUE (docs/01). Runs N candidates end to end,
logging per-stage pass/reject counts.

Retry policy: on a gate rejection the orchestrator either REPAIRS the candidate
(D-83, when the rejection is REPAIRABLE and repair is enabled -- feed it back to
the generator with the failure evidence and re-run the FULL gate chain) or
regenerates a FRESH candidate from the SAME spec. Both draw from one budget of
MAX_ATTEMPTS_PER_SPEC total generation calls; when it is spent the spec is given
up (recorded in BatchReport.spec_exhausted). Where budget allows, best-of-N
(D-84) collects more than one survivor and publishes the highest-scoring. D-83
supersedes the original blind-regeneration-only policy (D-10); the trust
guarantee is untouched -- nothing publishes without execution proof, and a
FUNDAMENTAL rejection is never repaired.
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
from pipeline.llm_client import LLMClient, TokenUsage, estimate_cost_usd
from pipeline.predict_the_fix import derive_artifacts, generate_wrong_fixes
from pipeline.publish import (
    concept_type_coverage,
    fetch_dedup_pool_hashes,
    insert_candidate,
    insert_predict_the_fix,
    seed_recent_bug_mechanisms,
    write_reject_report,
)
from pipeline.repair import (
    Rejection,
    classify_fundamental,
    classify_sandbox,
    classify_static,
    repair_candidate,
)
from pipeline.sandbox.runner import verify_sandbox_available
from pipeline.sandbox_gate import validate_spot_the_bug, validate_trace
from pipeline.schemas import PredictFixCandidate, STBCandidate, TraceCandidate
from pipeline.scoring import QualityScore, ScoreSignals, score_survivor
from pipeline.semantic_gates import GateVerdict, defect_audit, reasons, solver
from pipeline.spec_sampler import ExerciseSpec, sample_spec
from pipeline.taxonomy import concepts_for_type

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_SPEC = 3
MAX_REPAIR_ROUNDS = 2


@dataclasses.dataclass(frozen=True)
class LoopPolicy:
    """The per-spec generation policy (D-83 repair + D-84 best-of-N).

    Defaults reproduce the pre-upgrade behavior EXACTLY: repair off, best-of-N
    off, up to MAX_ATTEMPTS_PER_SPEC fresh candidates, publish the first
    survivor. Every existing test that does not pass a policy is therefore
    unchanged. The real batch CLI builds a policy from PipelineSettings that
    turns both on. All thresholds are explicit and tunable (D-84 2c).
    """

    repair_enabled: bool = False
    best_of_n_enabled: bool = False
    max_attempts_per_spec: int = MAX_ATTEMPTS_PER_SPEC
    max_repair_rounds: int = MAX_REPAIR_ROUNDS
    best_of_n_max_survivors: int = 2
    best_of_n_score_threshold: float = 0.70
    best_of_n_coverage_threshold: int = 2


# A frozen, immutable singleton -- safe to share as the run_batch default (the
# pre-upgrade behavior); avoids a per-call construction in the signature default.
_DEFAULT_POLICY = LoopPolicy()


@dataclasses.dataclass
class _AttemptBudget:
    """Mutable per-spec counter: total LLM generation calls (fresh + repair)
    consumed against LoopPolicy.max_attempts_per_spec. Repairs draw from the
    same budget as fresh generations (D-83 1c), so the loop can never exceed
    this cap per spec however repair/best-of-N interleave.
    """

    used: int = 0
    max: int = MAX_ATTEMPTS_PER_SPEC

    @property
    def remaining(self) -> int:
        return self.max - self.used


def _usage_snapshot(client: LLMClient) -> TokenUsage:
    usage = getattr(client, "usage", None)
    return dataclasses.replace(usage) if usage is not None else TokenUsage()


def _accumulate_delta(target: TokenUsage, client: LLMClient, before: TokenUsage) -> None:
    """Add the tokens `client` spent since the `before` snapshot into `target`,
    so the batch report can attribute the MARGINAL cost of repair (D-83 1d)."""
    now = _usage_snapshot(client)
    delta = now.delta_since(before)
    target.prompt_tokens += delta.prompt_tokens
    target.completion_tokens += delta.completion_tokens
    target.cached_prompt_tokens += delta.cached_prompt_tokens
    target.calls += delta.calls


@dataclasses.dataclass
class BatchReport:
    counts: collections.Counter = dataclasses.field(default_factory=collections.Counter)
    published: list[tuple[str, int]] = dataclasses.field(default_factory=list)
    # D-80: predict_the_fix exercises derived from published STB survivors,
    # tracked separately so they never inflate the sampled-spec coverage counts.
    ptf_published: list[tuple[str, int]] = dataclasses.field(default_factory=list)
    spec_exhausted: list[ExerciseSpec] = dataclasses.field(default_factory=list)
    coverage_before: dict[tuple[str, str], int] = dataclasses.field(default_factory=dict)
    coverage_after: dict[tuple[str, str], int] = dataclasses.field(default_factory=dict)
    generator_model: str = ""
    gate_model: str = ""
    generator_usage: TokenUsage = dataclasses.field(default_factory=TokenUsage)
    gate_usage: TokenUsage = dataclasses.field(default_factory=TokenUsage)
    coverage_driven_sampling: bool = False
    # D-80: set only when the per-type STB generator override is active; the STB
    # generation calls run on this model, the base generator_usage covers trace
    # and the predict_the_fix distractor step.
    stb_generator_model: str = ""
    stb_generator_usage: TokenUsage = dataclasses.field(default_factory=TokenUsage)
    # D-83: the MARGINAL token cost of repair -- the extra generation calls and
    # the extra gate passes re-validating repaired candidates -- so log_summary
    # can answer "did repair pay for itself?" honestly, priced with the right
    # model each (generator vs gate).
    repair_generator_usage: TokenUsage = dataclasses.field(default_factory=TokenUsage)
    repair_gate_usage: TokenUsage = dataclasses.field(default_factory=TokenUsage)

    def _log_coverage_gaps(self, coverage: dict[tuple[str, str], int], label: str) -> None:
        zero = sorted(
            f"{exercise_type}:{concept.slug}"
            for exercise_type in ("spot_the_bug", "trace")
            for concept in concepts_for_type(exercise_type)
            if coverage.get((exercise_type, concept.slug), 0) == 0
        )
        logger.info(
            "orchestrator coverage(%s) zero_count=%d zero=%s",
            label,
            len(zero),
            zero,
        )

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
        logger.info(
            "orchestrator stage=%-35s count=%d",
            "predict_the_fix_published_in_review",
            len(self.ptf_published),
        )
        if self.coverage_driven_sampling:
            self._log_coverage_gaps(self.coverage_before, "before")
            self._log_coverage_gaps(self.coverage_after, "after")
        self._log_cost("generator", self.generator_model, self.generator_usage)
        if self.stb_generator_model:
            self._log_cost("generator_stb", self.stb_generator_model, self.stb_generator_usage)
        self._log_cost("gate", self.gate_model, self.gate_usage)
        self._log_repair_economics()
        self._log_cache_savings()
        total_cost = self._total_cost()
        if total_cost is not None:
            logger.info(
                "orchestrator cost total_estimated_usd=%.4f published=%d "
                "per_published_usd=%s",
                total_cost,
                len(self.published),
                f"{total_cost / len(self.published):.4f}" if self.published else "n/a",
            )

    def _log_repair_economics(self) -> None:
        """Instrumentation for D-83 1d: is repair paying for itself? The marginal
        repair spend (extra generation + extra gate passes) against the count of
        candidates it rescued that would otherwise have been lost."""
        via_repair = self.counts.get("published_via_repair", 0)
        first_try = self.counts.get("published_first_try", 0)
        gen_cost = estimate_cost_usd(self.generator_model, self.repair_generator_usage)
        gate_cost = estimate_cost_usd(self.gate_model, self.repair_gate_usage)
        repair_cost = (gen_cost or 0.0) + (gate_cost or 0.0)
        logger.info(
            "orchestrator repair published_via_repair=%d published_first_try=%d "
            "attempted=%d succeeded=%d failed=%d",
            via_repair,
            first_try,
            self.counts.get("repair_attempted", 0),
            self.counts.get("repair_succeeded", 0),
            self.counts.get("repair_failed", 0),
        )
        if self.repair_generator_usage.calls or self.repair_gate_usage.calls:
            logger.info(
                "orchestrator repair marginal_gen_tokens=%d marginal_gate_tokens=%d "
                "marginal_estimated_usd=%s per_rescued_usd=%s",
                self.repair_generator_usage.total_tokens,
                self.repair_gate_usage.total_tokens,
                f"{repair_cost:.4f}",
                f"{repair_cost / via_repair:.4f}" if via_repair else "n/a",
            )

    def _log_cache_savings(self) -> None:
        """D-85: report how much of the generator's prompt-token spend was served
        from OpenAI's prompt cache (the static template prefix) vs billed fresh."""
        usages = [("generator", self.generator_model, self.generator_usage)]
        if self.stb_generator_model:
            usages.append(("generator_stb", self.stb_generator_model, self.stb_generator_usage))
        for role, model, usage in usages:
            if not usage.prompt_tokens:
                continue
            fraction = usage.cached_prompt_tokens / usage.prompt_tokens
            uncached = estimate_cost_usd(
                model,
                dataclasses.replace(usage, cached_prompt_tokens=0),
            )
            actual = estimate_cost_usd(model, usage)
            saved = (uncached - actual) if (uncached is not None and actual is not None) else None
            logger.info(
                "orchestrator cache role=%-12s prompt_tokens=%d cached=%d cached_fraction=%.2f "
                "estimated_saved_usd=%s",
                role,
                usage.prompt_tokens,
                usage.cached_prompt_tokens,
                fraction,
                f"{saved:.4f}" if saved is not None else "unknown",
            )

    def _log_cost(self, role: str, model: str, usage: TokenUsage) -> None:
        cost = estimate_cost_usd(model, usage) if model else None
        logger.info(
            "orchestrator tokens role=%-9s model=%-24s calls=%d prompt=%d completion=%d "
            "estimated_usd=%s",
            role,
            model,
            usage.calls,
            usage.prompt_tokens,
            usage.completion_tokens,
            f"{cost:.4f}" if cost is not None else "unknown",
        )

    def _total_cost(self) -> float | None:
        generator_cost = estimate_cost_usd(self.generator_model, self.generator_usage)
        gate_cost = estimate_cost_usd(self.gate_model, self.gate_usage)
        stb_cost = (
            estimate_cost_usd(self.stb_generator_model, self.stb_generator_usage)
            if self.stb_generator_model
            else None
        )
        if generator_cost is None and gate_cost is None and stb_cost is None:
            return None
        return (generator_cost or 0.0) + (gate_cost or 0.0) + (stb_cost or 0.0)


def _static_gate_check(
    candidate: STBCandidate | TraceCandidate,
    spec: ExerciseSpec,
) -> tuple[bool, list[str]]:
    # D-80: MAX-ONLY budget. Every budget reject in the reject reports was code
    # UNDER the min (a minimal clear bug is naturally 5-8 lines at difficulty
    # 1-2; the model cannot pad to 40-60 at difficulty 9-10) except two STB
    # cases over the max -- so the min was almost pure false-reject while the
    # max still earns its keep protecting readability. Applied to trace too:
    # 100% of trace budget rejects were under-min, zero over-max.
    max_only = (None, spec.line_budget_max)
    if isinstance(candidate, STBCandidate):
        # The line budget is a UX constraint on what the user READS, which is
        # buggy_code only. The fix may legitimately insert lines (D-46), so
        # fixed_code is length-unchecked (D-51); every non-length check still
        # runs on both snippets.
        buggy = static_gate.check(candidate.buggy_code, line_budget=max_only)
        fixed = static_gate.check(candidate.fixed_code, line_budget=None)
        return (buggy.accepted and fixed.accepted), (buggy.violations + fixed.violations)
    trace_result = static_gate.check(candidate.code, line_budget=max_only)
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


def _ptf_candidate_snapshot(
    stb_candidate: STBCandidate,
    wrong_fixes: PredictFixCandidate,
) -> dict[str, Any]:
    return {
        "buggy_code": stb_candidate.buggy_code,
        "fixed_code": stb_candidate.fixed_code,
        "test_code": stb_candidate.test_code,
        "wrong_fixes": [
            {"code": variant.code, "note": variant.note} for variant in wrong_fixes.wrong_fixes
        ],
    }


def _record_ptf_reject(
    report: BatchReport,
    spec: ExerciseSpec,
    stage: str,
    validation_report: dict[str, Any],
    stb_candidate: STBCandidate,
    wrong_fixes: PredictFixCandidate,
) -> None:
    """PTF mirror of `_record_reject` (D-89): a rejected predict_the_fix
    derivation used to just increment a counter and throw away
    ptf.validation_report -- the STB path's per-check sandbox detail with
    nowhere to land. Reuses write_reject_report EXACTLY as the STB path does
    (never a parallel writer, per D-87), fed the PTF derivation's own
    candidate shape (the STB triple plus the rejected wrong-fix variants).
    """
    report.counts[f"{stage}_rejected"] += 1
    report.counts[f"concept:{spec.concept}:ptf_rejected"] += 1
    write_reject_report(
        {
            "stage": stage,
            "spec": dataclasses.asdict(spec),
            "candidate": _ptf_candidate_snapshot(stb_candidate, wrong_fixes),
            **validation_report,
        },
        stage=stage,
        concept=spec.concept,
    )


@dataclasses.dataclass
class _SemanticOutcome:
    """The result of a type's semantic-gate chain, carrying the scoring signals
    (solver confidence, whether it matched the key, whether any gate FLAGGED)
    the best-of-N scorer reads for free (D-84)."""

    survived: bool
    reject_gate: str = ""
    reject_detail: str = ""
    solver_confidence: float = 0.0
    solver_matched: bool = False
    flagged: bool = False
    defect_audit_outcome: Any = None


def _run_stb_semantic_gates(
    candidate: STBCandidate,
    spec: ExerciseSpec,
    gate_client: LLMClient,
    report: dict[str, Any],
    verified_bug_lines: list[int],
) -> _SemanticOutcome:
    """defect_audit -> solver -> reasons.

    `verified_bug_lines` is the sandbox gate's diff-derived answer key (D-49),
    not the generator's claim; every downstream gate judges against the
    execution-proven lines. A REJECT from any gate is FUNDAMENTAL (the exercise
    idea is bad); a FLAG survives but is a quality-score penalty (D-84).
    """
    has_bug = bool(spec.has_bug)
    outcome = _SemanticOutcome(survived=False)

    defect_result = defect_audit(
        candidate.buggy_code,
        has_bug=has_bug,
        bug_lines=verified_bug_lines,
        llm_client=gate_client,
    )
    report["defect_audit"] = defect_result.as_report()
    outcome.defect_audit_outcome = defect_result
    outcome.flagged = outcome.flagged or defect_result.verdict == GateVerdict.FLAG
    if defect_result.verdict == GateVerdict.REJECT:
        outcome.reject_gate = "defect_audit"
        outcome.reject_detail = defect_result.detail
        return outcome

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
    solver_result = solver(
        solver_payload,
        correct_answer=correct_answer,
        llm_client=gate_client,
        compare_keys=None if has_a_bug_line else {"reason_id"},
        # D-52: every verified bug line is a correct answer for a multi-line
        # bug; keying to one exact line wrongly rejected a solver that named
        # another of them.
        acceptable_lines=verified_bug_lines if has_a_bug_line else None,
    )
    report["solver"] = solver_result.as_report()
    outcome.solver_confidence = float((solver_result.raw or {}).get("confidence", 0.0))
    outcome.solver_matched = solver_result.verdict == GateVerdict.PASS
    outcome.flagged = outcome.flagged or solver_result.verdict == GateVerdict.FLAG
    if solver_result.verdict == GateVerdict.REJECT:
        outcome.reject_gate = "solver"
        outcome.reject_detail = solver_result.detail
        return outcome

    reasons_result = reasons(
        candidate.buggy_code,
        reason_options=[o.model_dump() for o in candidate.reason_options],
        correct_reason_id=candidate.correct_reason_id,
        llm_client=gate_client,
    )
    report["reasons"] = reasons_result.as_report()
    if reasons_result.verdict == GateVerdict.REJECT:
        outcome.reject_gate = "reasons"
        outcome.reject_detail = reasons_result.detail
        return outcome

    outcome.survived = True
    return outcome


def _run_trace_semantic_gates(
    candidate: TraceCandidate,
    gate_client: LLMClient,
    report: dict[str, Any],
) -> _SemanticOutcome:
    payload = {
        "code": candidate.code,
        "context_note": candidate.context_note,
        "question": candidate.question,
        "choices": [c.model_dump() for c in candidate.choices],
    }
    solver_result = solver(
        payload,
        correct_answer={"choice_id": candidate.correct_choice_id},
        llm_client=gate_client,
    )
    report["solver"] = solver_result.as_report()
    outcome = _SemanticOutcome(
        survived=solver_result.verdict != GateVerdict.REJECT,
        solver_confidence=float((solver_result.raw or {}).get("confidence", 0.0)),
        solver_matched=solver_result.verdict == GateVerdict.PASS,
        flagged=solver_result.verdict == GateVerdict.FLAG,
    )
    if solver_result.verdict == GateVerdict.REJECT:
        outcome.reject_gate = "solver"
        outcome.reject_detail = solver_result.detail
    return outcome


@dataclasses.dataclass
class _Survivor:
    """A candidate that cleared the FULL gate chain, ready to publish. Best-of-N
    (D-84) collects these per spec and publishes the highest-scoring one; a
    repaired candidate carries `published_via_repair` for the instrumentation."""

    spec: ExerciseSpec
    candidate: STBCandidate | TraceCandidate
    gen_model: str
    validation_report: dict[str, Any]
    content_hash: str
    verified_bug_lines: list[int] | None
    captured_stdout: str | None
    defect_audit_outcome: Any
    score: QualityScore
    published_via_repair: bool = False


@dataclasses.dataclass
class _Evaluation:
    survivor: _Survivor | None = None
    rejection: Rejection | None = None
    validation_report: dict[str, Any] = dataclasses.field(default_factory=dict)


def _resolve_gen_client(
    spec: ExerciseSpec,
    generator_client: LLMClient,
    generator_model: str,
    stb_generator_client: LLMClient | None,
    stb_generator_model: str,
) -> tuple[LLMClient, str]:
    """D-80: route spot_the_bug generation (and its repairs) to the per-type
    override when configured; everything else uses the base generator."""
    if spec.type == "spot_the_bug" and stb_generator_client is not None:
        return stb_generator_client, stb_generator_model
    return generator_client, generator_model


def _evaluate_candidate(
    candidate: STBCandidate | TraceCandidate,
    spec: ExerciseSpec,
    gate_client: LLMClient,
    gen_model: str,
    template_id: str,
    dedup_pool_hashes: set[str],
    report: BatchReport,
    *,
    bucket: str,
) -> _Evaluation:
    """Run one candidate through static -> sandbox -> semantic -> dedup and
    return either a scored `_Survivor` or a classified `Rejection` (D-83). Does
    NOT publish and does NOT mutate the dedup pool -- best-of-N (D-84) must be
    able to evaluate several survivors of the same spec without them deduping
    against each other; the winner's hash is added at publish time.

    `bucket` is "first_try" or "repair"; a "repair" evaluation attributes its
    gate-model spend to the marginal repair cost (D-83 1d).
    """
    static_ok, static_violations = _static_gate_check(candidate, spec)
    validation_report: dict[str, Any] = {
        "template_id": template_id,
        "static_gate": {"accepted": static_ok, "violations": static_violations},
    }
    if not static_ok:
        return _Evaluation(
            rejection=classify_static(static_violations),
            validation_report=validation_report,
        )
    report.counts["static_gate_passed"] += 1

    captured_stdout: str | None = None
    verified_bug_lines: list[int] | None = None
    claim_mismatch = False

    if isinstance(candidate, STBCandidate):
        sandbox_result = validate_spot_the_bug(candidate, has_bug=bool(spec.has_bug))
        validation_report["sandbox_gate"] = sandbox_result.as_report()
        if not sandbox_result.accepted:
            return _Evaluation(
                rejection=classify_sandbox(sandbox_result),
                validation_report=validation_report,
            )
        report.counts["sandbox_gate_passed"] += 1
        # D-49: the answer key is the diff-derived lines the sandbox verified,
        # never the generator's claim. A claim/diff mismatch on a survivor is
        # a template-quality metric (D-11 style), not a reject.
        verified_bug_lines = sandbox_result.verified_bug_lines or []
        claim_mismatch = sandbox_result.bug_lines_claim_mismatch
        if claim_mismatch:
            report.counts["stb_bug_lines_claim_mismatch"] += 1

        gate_before = _usage_snapshot(gate_client)
        semantic = _run_stb_semantic_gates(
            candidate, spec, gate_client, validation_report, verified_bug_lines,
        )
        if bucket == "repair":
            _accumulate_delta(report.repair_gate_usage, gate_client, gate_before)
        if not semantic.survived:
            return _Evaluation(
                rejection=classify_fundamental(
                    "semantic_gate", semantic.reject_gate, semantic.reject_detail,
                ),
                validation_report=validation_report,
            )
        report.counts["semantic_gate_passed"] += 1
        code_for_dedup = candidate.buggy_code
        code_line_count = len(candidate.buggy_code.splitlines())
    else:
        sandbox_result = validate_trace(candidate)
        validation_report["sandbox_gate"] = sandbox_result.as_report()
        if not sandbox_result.accepted:
            return _Evaluation(
                rejection=classify_sandbox(sandbox_result),
                validation_report=validation_report,
            )
        report.counts["sandbox_gate_passed"] += 1
        captured_stdout = sandbox_result.captured_stdout

        gate_before = _usage_snapshot(gate_client)
        semantic = _run_trace_semantic_gates(candidate, gate_client, validation_report)
        if bucket == "repair":
            _accumulate_delta(report.repair_gate_usage, gate_client, gate_before)
        if not semantic.survived:
            return _Evaluation(
                rejection=classify_fundamental(
                    "semantic_gate", semantic.reject_gate, semantic.reject_detail,
                ),
                validation_report=validation_report,
            )
        report.counts["semantic_gate_passed"] += 1
        code_for_dedup = candidate.code
        code_line_count = len(candidate.code.splitlines())

    content_hash = dedup.content_hash(code_for_dedup)
    if dedup.is_duplicate(code_for_dedup, dedup_pool_hashes):
        return _Evaluation(
            rejection=classify_fundamental("dedup", "dedup", "duplicate of an existing candidate"),
            validation_report=validation_report,
        )
    report.counts["dedup_passed"] += 1

    score = score_survivor(
        ScoreSignals(
            exercise_type=spec.type,
            authored_difficulty=spec.difficulty,
            solver_confidence=semantic.solver_confidence,
            solver_matched=semantic.solver_matched,
            code_line_count=code_line_count,
            verified_bug_lines=tuple(verified_bug_lines or ()),
            claim_mismatch=claim_mismatch,
            semantic_flagged=semantic.flagged,
        ),
    )
    validation_report["quality_score"] = {
        "score": score.score,
        "breakdown": score.breakdown,
        "difficulty_miscalibrated": score.difficulty_miscalibrated,
        "difficulty_empirical_estimate": score.difficulty_empirical_estimate,
    }

    survivor = _Survivor(
        spec=spec,
        candidate=candidate,
        gen_model=gen_model,
        validation_report=validation_report,
        content_hash=content_hash,
        verified_bug_lines=verified_bug_lines,
        captured_stdout=captured_stdout,
        defect_audit_outcome=semantic.defect_audit_outcome,
        score=score,
    )
    return _Evaluation(survivor=survivor, validation_report=validation_report)


def _run_lineage(
    spec: ExerciseSpec,
    candidate: STBCandidate | TraceCandidate,
    template_id: str,
    gen_client: LLMClient,
    gen_model: str,
    gate_client: LLMClient,
    dedup_pool_hashes: set[str],
    report: BatchReport,
    policy: LoopPolicy,
    budget: _AttemptBudget,
) -> _Survivor | None:
    """Evaluate one fresh candidate and, on a REPAIRABLE rejection, feed it back
    for a targeted fix and re-evaluate -- up to policy.max_repair_rounds, never
    the same check twice, never past the shared attempt budget (D-83 1c). A
    FUNDAMENTAL rejection ends the lineage immediately (never repaired). Returns
    a survivor or None. Every rejection still writes its D-48 receipt."""
    current = candidate
    current_template_id = template_id
    used_repair = False
    repair_rounds = 0
    checks_triggered: set[str] = set()
    last_repair_check: str | None = None
    bucket = "first_try"

    while True:
        evaluation = _evaluate_candidate(
            current, spec, gate_client, gen_model, current_template_id,
            dedup_pool_hashes, report, bucket=bucket,
        )
        if evaluation.survivor is not None:
            if last_repair_check is not None:
                report.counts["repair_succeeded"] += 1
                report.counts[f"repair_succeeded:{last_repair_check}"] += 1
            evaluation.survivor.published_via_repair = used_repair
            return evaluation.survivor

        rejection = evaluation.rejection
        assert rejection is not None  # no survivor implies a rejection
        _record_reject(report, spec, rejection.stage, evaluation.validation_report, current)
        if last_repair_check is not None:
            report.counts["repair_failed"] += 1
            report.counts[f"repair_failed:{last_repair_check}"] += 1
            last_repair_check = None

        if not policy.repair_enabled or not rejection.repairable:
            return None
        if repair_rounds >= policy.max_repair_rounds:
            report.counts["repair_stopped_max_rounds"] += 1
            return None
        if rejection.check in checks_triggered:
            # Failed the SAME check twice after repair -- it can't get there (D-83 1c).
            report.counts["repair_stopped_same_check"] += 1
            report.counts[f"repair_stopped_same_check:{rejection.check}"] += 1
            return None
        if budget.remaining <= 0:
            report.counts["repair_stopped_budget"] += 1
            return None

        checks_triggered.add(rejection.check)
        report.counts["repair_attempted"] += 1
        report.counts[f"repair_attempted:{rejection.check}"] += 1
        gen_before = _usage_snapshot(gen_client)
        outcome = repair_candidate(
            exercise_type=spec.type,
            candidate=current,
            rejection=rejection,
            llm_client=gen_client,
        )
        _accumulate_delta(report.repair_generator_usage, gen_client, gen_before)
        budget.used += 1
        repair_rounds += 1
        used_repair = True
        bucket = "repair"
        last_repair_check = rejection.check

        if not outcome.survived:
            report.counts[f"repair_discarded:{outcome.discard_reason}"] += 1
            report.counts["repair_failed"] += 1
            report.counts[f"repair_failed:{last_repair_check}"] += 1
            return None
        assert outcome.candidate is not None
        current = outcome.candidate
        current_template_id = outcome.template_id


def _want_more_survivors(
    survivors: list[_Survivor],
    spec: ExerciseSpec,
    coverage: dict[tuple[str, str], int],
    budget: _AttemptBudget,
    policy: LoopPolicy,
) -> bool:
    """Best-of-N cost control (D-84 2c): pursue another survivor ONLY when the
    best so far scores below threshold OR the concept is under-covered, and
    budget remains and the per-spec survivor cap is not hit. Never
    blanket-multiplies cost."""
    if len(survivors) >= policy.best_of_n_max_survivors:
        return False
    if budget.remaining <= 0:
        return False
    best_score = max(s.score.score for s in survivors)
    under_covered = (
        coverage.get((spec.type, spec.concept), 0) < policy.best_of_n_coverage_threshold
    )
    return best_score < policy.best_of_n_score_threshold or under_covered


async def _publish_survivor(
    session: AsyncSession,
    survivor: _Survivor,
    generator_client: LLMClient,
    generator_model: str,
    dedup_pool_hashes: set[str],
    recent_bug_mechanisms: dict[str, list[str]],
    report: BatchReport,
    *,
    rng: random.Random,
    derive_predict_the_fix: bool,
    origin: str = "llm",
) -> None:
    """Publish the chosen survivor as an in_review row and record its receipts,
    the repair/first-try split, the difficulty-calibration flag, and (for a
    has_bug STB) the derived predict_the_fix (D-80).

    `origin` (D-87): passed straight through to publish.insert_candidate;
    "llm" for every existing caller (unchanged), "handauthored_claude" for
    pipeline/ingest.py's file-provider path.
    """
    spec = survivor.spec
    candidate = survivor.candidate
    if isinstance(candidate, STBCandidate):
        final = finalize_stb_explanation(
            candidate,
            has_bug=bool(spec.has_bug),
            verified_bug_lines=survivor.verified_bug_lines or [],
            defect_audit_outcome=survivor.defect_audit_outcome,
        )
    else:
        final = finalize_trace_explanation(
            candidate, captured_stdout=survivor.captured_stdout or "",
        )
    validation_report = survivor.validation_report
    validation_report["explanation"] = {
        "mismatch_flagged": final.mismatch_flagged,
        "mismatch_detail": final.mismatch_detail,
    }

    exercise = await insert_candidate(
        session,
        spec,
        candidate,
        final_explanation=final.explanation,
        content_hash=survivor.content_hash,
        validation_report=validation_report,
        generator_model=survivor.gen_model,
        captured_stdout=survivor.captured_stdout,
        verified_bug_lines=survivor.verified_bug_lines,
        origin=origin,
        rng=rng,
    )
    dedup_pool_hashes.add(survivor.content_hash)  # this run's own candidates count too
    report.counts["published_in_review"] += 1
    report.counts[f"concept:{spec.concept}:published"] += 1
    report.published.append((str(exercise.id), exercise.version))
    if survivor.published_via_repair:
        report.counts["published_via_repair"] += 1
    else:
        report.counts["published_first_try"] += 1
    if survivor.score.difficulty_miscalibrated:
        # D-84 2b: a hard-authored exercise the gate model breezed -- flag for
        # downgrade/review before we have users to measure difficulty_empirical.
        report.counts["difficulty_miscalibrated"] += 1
        report.counts[f"difficulty_miscalibrated:{spec.type}:{spec.concept}"] += 1

    if isinstance(candidate, STBCandidate) and spec.has_bug:
        correct_option = next(
            (o for o in candidate.reason_options if o.id == candidate.correct_reason_id),
            None,
        )
        if correct_option is not None:
            recent_bug_mechanisms.setdefault(spec.concept, []).insert(0, correct_option.text)

        # D-80: seed a predict_the_fix from this verified STB's proven
        # (buggy, fixed, test) triple. Additive: base generator client, never
        # the STB override; a derivation failure leaves the STB published.
        if derive_predict_the_fix and survivor.verified_bug_lines:
            await _derive_and_publish_ptf(
                session,
                spec,
                candidate,
                exercise,
                generator_client,
                generator_model,
                rng,
                report,
            )


async def _resolve_spec(
    session: AsyncSession,
    spec: ExerciseSpec,
    generator_client: LLMClient,
    gate_client: LLMClient,
    generator_model: str,
    dedup_pool_hashes: set[str],
    recent_bug_mechanisms: dict[str, list[str]],
    report: BatchReport,
    coverage: dict[tuple[str, str], int],
    *,
    rng: random.Random,
    policy: LoopPolicy,
    stb_generator_client: LLMClient | None,
    stb_generator_model: str,
    derive_predict_the_fix: bool,
) -> bool:
    """Resolve one spec end to end: generate fresh candidates (each with its own
    bounded repair lineage) until one publishes, collecting extra survivors for
    best-of-N where the policy allows, then publish the highest-scoring survivor.
    Returns True iff something published. Total generation calls (fresh + repair)
    are capped by policy.max_attempts_per_spec."""
    gen_client, gen_model = _resolve_gen_client(
        spec, generator_client, generator_model, stb_generator_client, stb_generator_model,
    )
    budget = _AttemptBudget(max=policy.max_attempts_per_spec)
    survivors: list[_Survivor] = []

    while budget.remaining > 0:
        outcome = generate_candidate(spec, gen_client)
        budget.used += 1
        report.counts["generated_total"] += 1
        if not outcome.survived:
            report.counts[f"generate_discarded:{outcome.discard_reason}"] += 1
            report.counts[f"concept:{spec.concept}:rejected"] += 1
            continue
        report.counts["generate_passed"] += 1
        assert outcome.candidate is not None
        survivor = _run_lineage(
            spec, outcome.candidate, outcome.template_id, gen_client, gen_model,
            gate_client, dedup_pool_hashes, report, policy, budget,
        )
        if survivor is not None:
            survivors.append(survivor)
            if not (
                policy.best_of_n_enabled
                and _want_more_survivors(survivors, spec, coverage, budget, policy)
            ):
                break

    if not survivors:
        return False

    best = max(survivors, key=lambda s: s.score.score)
    if len(survivors) > 1:
        report.counts["best_of_n_pursued"] += 1
        report.counts["best_of_n_extra_survivors"] += len(survivors) - 1
        if best is not survivors[0]:
            report.counts["best_of_n_selected_better"] += 1
    await _publish_survivor(
        session, best, generator_client, generator_model, dedup_pool_hashes,
        recent_bug_mechanisms, report, rng=rng, derive_predict_the_fix=derive_predict_the_fix,
    )
    return True


async def _derive_and_publish_ptf(
    session: AsyncSession,
    spec: ExerciseSpec,
    stb_candidate: STBCandidate,
    stb_exercise: Any,
    generator_client: LLMClient,
    generator_model: str,
    rng: random.Random,
    report: BatchReport,
) -> None:
    """Derive + publish a predict_the_fix from a just-published STB (D-80).

    One extra generator call (the wrong-fix distractors) plus a sandbox pass
    proving each distractor still fails the test. Every failure mode is a plain
    skip -- the STB is already published and never affected.
    """
    report.counts["ptf_derivation_attempted"] += 1
    wrong_fixes, discard_reason = generate_wrong_fixes(
        buggy_code=stb_candidate.buggy_code,
        fixed_code=stb_candidate.fixed_code,
        test_code=stb_candidate.test_code,
        concept=spec.concept,
        domain=spec.domain,
        llm_client=generator_client,
    )
    if wrong_fixes is None:
        report.counts[f"ptf_generate_discarded:{discard_reason}"] += 1
        return

    ptf = derive_artifacts(
        stb_candidate=stb_candidate,
        wrong_fixes=wrong_fixes,
        rng=rng,
        line_budget_max=spec.line_budget_max,
    )
    if not ptf.survived:
        assert ptf.reject_stage is not None  # not survived implies a reject stage
        _record_ptf_reject(
            report, spec, ptf.reject_stage, ptf.validation_report, stb_candidate, wrong_fixes,
        )
        return

    artifacts = ptf.artifacts
    assert artifacts is not None  # survived implies not None
    stb_source = stb_exercise.source if isinstance(stb_exercise.source, dict) else {}
    ptf_exercise = await insert_predict_the_fix(
        session,
        concepts=list(stb_candidate.concepts),
        difficulty_authored=spec.difficulty,
        payload=artifacts.payload,
        grading=artifacts.grading,
        explanation=artifacts.explanation,
        content_hash=artifacts.content_hash,
        validation_report=ptf.validation_report,
        generator_model=generator_model,
        derived_from_id=stb_exercise.id,
        derived_from_version=stb_exercise.version,
        stb_template_id=stb_source.get("prompt_template_id"),
    )
    report.counts["ptf_published_in_review"] += 1
    report.counts[f"concept:{spec.concept}:ptf_published"] += 1
    report.ptf_published.append((str(ptf_exercise.id), ptf_exercise.version))


async def run_batch(
    session: AsyncSession,
    n: int,
    *,
    generator_client: LLMClient,
    gate_client: LLMClient,
    generator_model: str,
    gate_model: str = "",
    rng: random.Random | None = None,
    type_mix: tuple[str, ...] = ("spot_the_bug", "trace"),
    seed_history_from_db: bool = True,
    specs: list[ExerciseSpec] | None = None,
    coverage_driven_sampling: bool = True,
    commit_after_each_spec: bool = False,
    stb_generator_client: LLMClient | None = None,
    stb_generator_model: str = "",
    derive_predict_the_fix: bool = False,
    policy: LoopPolicy = _DEFAULT_POLICY,
) -> BatchReport:
    """Run n candidates end to end.

    `policy` (D-83 repair + D-84 best-of-N): the per-spec generation policy. Its
    default reproduces the pre-upgrade behavior EXACTLY (repair off, best-of-N
    off, publish the first survivor), so every caller that does not pass one is
    unchanged; the real batch CLI builds a policy from settings that turns both
    on.

    `specs` lets callers (tests) inject exact specs instead of sampling from
    `rng`, so a fixed candidate fixture's line count doesn't have to satisfy
    whatever line budget the RNG happens to sample. Real batches never pass
    it; n and rng drive sampling as usual.

    `commit_after_each_spec` (CLAUDE.md M8: resumability) commits after every
    spec is resolved (published or exhausted), so a crash mid-batch -- an
    unhandled OpenAI error, a killed process -- only loses the one spec in
    flight, never every candidate published before it. Off by default so
    tests keep their existing rollback-only isolation (`db_session`
    fixture); the real CLI entry point turns it on.

    `stb_generator_client`/`stb_generator_model` (D-80): a per-type generator
    override for spot_the_bug only (the flagship). Off by default (None); when
    set, STB generation runs on that client while trace and the
    predict_the_fix distractor step stay on the base generator.

    `derive_predict_the_fix` (D-80): after publishing a has_bug spot_the_bug
    survivor, also derive a predict_the_fix from its verified (buggy, fixed,
    test) triple. Off by default so existing tests -- whose scripted clients
    queue exactly the primary-path responses -- are unaffected; the real CLI
    entry point turns it on.
    """
    rng = rng or random.Random()
    report = BatchReport(
        generator_model=generator_model,
        gate_model=gate_model,
        coverage_driven_sampling=coverage_driven_sampling,
        stb_generator_model=stb_generator_model,
    )

    # D-57: prove the sandbox actually executes code before trusting any of
    # this batch's rejections -- see verify_sandbox_available's docstring.
    verify_sandbox_available()

    recent_bug_mechanisms = (
        await seed_recent_bug_mechanisms(session) if seed_history_from_db else {}
    )
    dedup_pool_hashes = await fetch_dedup_pool_hashes(session)
    coverage = await concept_type_coverage(session) if coverage_driven_sampling else {}
    report.coverage_before = dict(coverage)

    for i in range(n):
        spec = (
            specs[i]
            if specs is not None
            else sample_spec(
                rng,
                type_mix[i % len(type_mix)],
                recent_bug_mechanisms=recent_bug_mechanisms,
                concept_coverage=coverage if coverage_driven_sampling else None,
            )
        )
        report.counts["specs_sampled"] += 1

        published = await _resolve_spec(
            session,
            spec,
            generator_client,
            gate_client,
            generator_model,
            dedup_pool_hashes,
            recent_bug_mechanisms,
            report,
            coverage,
            rng=rng,
            policy=policy,
            stb_generator_client=stb_generator_client,
            stb_generator_model=stb_generator_model,
            derive_predict_the_fix=derive_predict_the_fix,
        )
        if published:
            coverage_key = (spec.type, spec.concept)
            coverage[coverage_key] = coverage.get(coverage_key, 0) + 1
        else:
            report.counts[f"concept:{spec.concept}:exhausted"] += 1
            report.spec_exhausted.append(spec)

        if commit_after_each_spec:
            await session.commit()

    report.coverage_after = dict(coverage)
    report.generator_usage = getattr(generator_client, "usage", TokenUsage())
    report.gate_usage = getattr(gate_client, "usage", TokenUsage())
    if stb_generator_client is not None:
        report.stb_generator_usage = getattr(stb_generator_client, "usage", TokenUsage())
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
    parser.add_argument(
        "--type-mix",
        type=str,
        default=None,
        help=(
            "comma-separated exercise types to cycle through per candidate "
            "(run_batch's type_mix, e.g. 'trace' or 'spot_the_bug,trace'); "
            "defaults to run_batch's own default of spot_the_bug,trace"
        ),
    )
    args = parser.parse_args(argv)
    type_mix = (
        tuple(t.strip() for t in args.type_mix.split(",") if t.strip())
        if args.type_mix is not None
        else None
    )

    async def _run() -> None:
        settings = get_pipeline_settings()
        specs = None
        gate_model = ""
        stb_generator_client = None
        stb_generator_model = ""
        # The --mock demo path keeps the pre-upgrade policy (default: repair off,
        # best-of-N off, publish first survivor) so its trivially-passing scripted
        # pair needs no repair/extra-survivor responses; the real batch turns both
        # on from settings (D-83/D-84).
        policy = LoopPolicy()
        if args.mock:
            generator_client, gate_client, specs = _demo_mock_clients(args.n)
            generator_model = "mock-generator"
        else:
            policy = LoopPolicy(
                repair_enabled=settings.REPAIR_ENABLED,
                best_of_n_enabled=settings.BEST_OF_N_ENABLED,
                max_attempts_per_spec=settings.MAX_ATTEMPTS_PER_SPEC,
                max_repair_rounds=settings.MAX_REPAIR_ROUNDS,
                best_of_n_max_survivors=settings.BEST_OF_N_MAX_SURVIVORS,
                best_of_n_score_threshold=settings.BEST_OF_N_SCORE_THRESHOLD,
                best_of_n_coverage_threshold=settings.BEST_OF_N_COVERAGE_THRESHOLD,
            )
            generator_client = build_llm_client(
                settings.GENERATOR_PROVIDER, settings.GENERATOR_MODEL,
            )
            gate_client = build_llm_client(settings.GATE_PROVIDER, settings.GATE_MODEL)
            generator_model = settings.GENERATOR_MODEL
            gate_model = settings.GATE_MODEL
            # D-80: per-type STB generator override, OFF unless GENERATOR_MODEL_STB
            # is set to something other than GENERATOR_MODEL. One env var flips it.
            if settings.GENERATOR_MODEL_STB and (
                settings.GENERATOR_MODEL_STB != settings.GENERATOR_MODEL
            ):
                stb_generator_client = build_llm_client(
                    settings.GENERATOR_PROVIDER, settings.GENERATOR_MODEL_STB,
                )
                stb_generator_model = settings.GENERATOR_MODEL_STB

        engine = create_engine(settings.DATABASE_URL)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            # commit_after_each_spec=True (D-74): a real batch run must not
            # lose already-published candidates to a crash later in the run
            # (an unhandled 429/insufficient_quota, a killed process). The
            # final commit is a harmless no-op safety net when every spec
            # already committed itself.
            await run_batch(
                session,
                args.n,
                generator_client=generator_client,
                gate_client=gate_client,
                generator_model=generator_model,
                gate_model=gate_model,
                rng=random.Random(args.seed) if args.seed is not None else None,
                type_mix=type_mix if type_mix is not None else ("spot_the_bug", "trace"),
                specs=specs,
                commit_after_each_spec=True,
                stb_generator_client=stb_generator_client,
                stb_generator_model=stb_generator_model,
                # D-80: predict_the_fix is nearly free (it reuses the STB's
                # verified artifacts) and STB is the flagship -- derive it in
                # every real batch. The --mock demo path leaves it off (its
                # scripted client has no wrong-fix responses configured).
                derive_predict_the_fix=not args.mock,
                policy=policy,
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
