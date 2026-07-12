"""Feedback-driven repair (D-83), grounded in the generation-verification
pattern (ReVeal, arXiv 2506.11442): on a gate rejection, instead of discarding
the candidate and rolling three independent dice on the same spec, feed the
candidate BACK to the generator with structured failure feedback and ask for a
TARGETED fix. The reject report (D-48) already records exactly which check
failed and why; that evidence, previously thrown away, is what a repair runs on.

This module owns two things:

  1. CLASSIFICATION -- every rejection is REPAIRABLE or FUNDAMENTAL. This is the
     heart of the change. REPAIRABLE means the bug and the code are fine and
     only one artifact is wrong (a non-discriminating test input, a mis-stated
     result claim, a mechanical static violation). FUNDAMENTAL means the
     exercise IDEA is bad (a genuine second defect, an unsolvable/ambiguous
     exercise, a partially-defensible distractor, a duplicate) -- repairing it
     is asking the model to rescue a bad idea, so we spend the attempt on a
     fresh candidate instead and NEVER repair it.

  2. The repair GENERATION call (repair_stb_v1 / repair_trace_v1). A repaired
     candidate is NOT a trusted candidate: the orchestrator runs it back through
     the FULL gate chain, no exemptions (the trust guarantee, invariant 1, is
     untouched). Bounds live in the orchestrator (max repair rounds, same-check-
     twice stop, the MAX_ATTEMPTS_PER_SPEC budget).
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum

from pipeline.generate import (
    _JSON_ONLY_NUDGE,
    GenerationOutcome,
    _render,
    _try_parse_json,
    load_template,
)
from pipeline.llm_client import LLMClient
from pipeline.sandbox_gate import SandboxGateResult
from pipeline.schemas import STBCandidate, TraceCandidate

_TEMPERATURE = 0.8


class RepairClass(StrEnum):
    REPAIRABLE = "repairable"
    FUNDAMENTAL = "fundamental"


# The ONLY checks a repair may target. Everything else is FUNDAMENTAL by
# construction (the safe default): a check not on this list means either the
# exercise idea is bad or the failure is a code property we do not ask the model
# to re-roll under the "change only what's necessary" instruction.
#
#   static_gate                    -- forbidden import/call, hint word, over
#                                     budget. Purely mechanical; the idea survives.
#   buggy_fails_test               -- the test passes on buggy code. The bug is
#                                     real; the input just isn't on the divergence
#                                     boundary. Ask for a new divergence_input +
#                                     test, buggy/fixed UNCHANGED.
#   fixed_passes_test              -- the fix isn't self-consistent with the test.
#   stb_claim_matches_execution    -- the model mispredicted its own results (B4);
#                                     give it the ACTUAL captured outputs.
#   captured_output_matches_claim  -- trace: the model mis-traced its own code;
#                                     give it the REAL captured stdout.
REPAIRABLE_CHECKS: frozenset[str] = frozenset(
    {
        "static_gate",
        "buggy_fails_test",
        "fixed_passes_test",
        "stb_claim_matches_execution",
        "captured_output_matches_claim",
    },
)


@dataclasses.dataclass(frozen=True)
class Rejection:
    """A classified gate rejection, carrying the concrete evidence a repair
    prompt needs (stderr, the captured-vs-claimed diff, the exact violation).
    """

    stage: str
    check: str
    repair_class: RepairClass
    evidence: str

    @property
    def repairable(self) -> bool:
        return self.repair_class == RepairClass.REPAIRABLE


def _classify(stage: str, check: str, evidence: str) -> Rejection:
    repair_class = (
        RepairClass.REPAIRABLE if check in REPAIRABLE_CHECKS else RepairClass.FUNDAMENTAL
    )
    return Rejection(stage=stage, check=check, repair_class=repair_class, evidence=evidence)


def classify_static(violations: list[str]) -> Rejection:
    """Static violations are always mechanical -> REPAIRABLE (D-83 1a)."""
    return _classify("static_gate", "static_gate", "; ".join(violations) or "static violation")


def classify_sandbox(result: SandboxGateResult) -> Rejection:
    """A sandbox rejection is REPAIRABLE only if EVERY failing check is
    repairable; a single fundamental failure (e.g. buggy_runs_clean,
    fix_diff_real_and_minimal, deterministic_double_run) makes the whole
    candidate fundamental -- we never partially-trust a candidate that also
    failed something a repair can't touch. The named check is the first
    failure; the evidence concatenates every failing check's detail.
    """
    failing = [c for c in result.checks if not c.passed]
    if not failing:  # defensive: caller only classifies actual rejections
        return _classify("sandbox_gate", "unknown", "")
    all_repairable = all(c.name in REPAIRABLE_CHECKS for c in failing)
    evidence = "; ".join(f"{c.name}: {c.detail}".rstrip(": ") for c in failing)
    rejection = _classify("sandbox_gate", failing[0].name, evidence)
    if not all_repairable:
        # Override: a mixed failure set is fundamental even if the first-named
        # check happens to be on the repairable list.
        return Rejection(
            stage=rejection.stage,
            check=rejection.check,
            repair_class=RepairClass.FUNDAMENTAL,
            evidence=evidence,
        )
    return rejection


def classify_fundamental(stage: str, check: str, evidence: str) -> Rejection:
    """Semantic-gate rejections (defect_audit second defect, solver
    unsolvable/ambiguous, reasons partially_defensible or mis-keyed) and dedup:
    the exercise idea itself is bad, so it is FUNDAMENTAL and never repaired.
    """
    return Rejection(
        stage=stage,
        check=check,
        repair_class=RepairClass.FUNDAMENTAL,
        evidence=evidence,
    )


_REPAIR_TEMPLATE_BY_TYPE = {
    "spot_the_bug": "repair_spot_the_bug",
    "trace": "repair_trace",
}
_SCHEMA_BY_TYPE: dict[str, type[STBCandidate] | type[TraceCandidate]] = {
    "spot_the_bug": STBCandidate,
    "trace": TraceCandidate,
}


def repair_candidate(
    *,
    exercise_type: str,
    candidate: STBCandidate | TraceCandidate,
    rejection: Rejection,
    llm_client: LLMClient,
    python_version: str = "3.12",
) -> GenerationOutcome:
    """Ask the generator to TARGET-FIX `candidate` for the named failed check,
    changing only what the failure requires. Same parse/validate contract as a
    fresh generation (GenerationOutcome), so the orchestrator treats a repaired
    candidate exactly like a fresh one -- full gate chain, no exemptions.
    """
    template = load_template(_REPAIR_TEMPLATE_BY_TYPE[exercise_type])
    variables = {
        "python_version": python_version,
        "failed_check": rejection.check,
        "failure_evidence": rejection.evidence,
        "original_candidate_json": candidate.model_dump_json(indent=2),
    }
    user_prompt = _render(template.user, variables)

    raw = llm_client.complete(system=template.system, user=user_prompt, temperature=_TEMPERATURE)
    parsed = _try_parse_json(raw)
    if parsed is None:
        # Same single JSON-only retry as generate.py (D-10's sole exception).
        raw = llm_client.complete(
            system=template.system,
            user=user_prompt + _JSON_ONLY_NUDGE,
            temperature=_TEMPERATURE,
        )
        parsed = _try_parse_json(raw)
        if parsed is None:
            return GenerationOutcome(
                candidate=None,
                template_id=template.template_id,
                raw_text=raw,
                discard_reason="repair_json_parse_failed",
            )

    if isinstance(parsed, dict) and parsed.get("abort") is True:
        reason = parsed.get("reason", "unspecified")
        return GenerationOutcome(
            candidate=None,
            template_id=template.template_id,
            raw_text=raw,
            discard_reason=f"repair_aborted: {reason}",
        )

    schema = _SCHEMA_BY_TYPE[exercise_type]
    try:
        repaired = schema.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError or bad shape
        return GenerationOutcome(
            candidate=None,
            template_id=template.template_id,
            raw_text=raw,
            discard_reason=f"repair_schema_validation_failed: {exc}",
        )

    return GenerationOutcome(candidate=repaired, template_id=template.template_id, raw_text=raw)
