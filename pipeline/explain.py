"""Explanation finalization.

Per D-32 (docs/07): this is a deterministic merge, not a new LLM call -- no
explain_*.md template exists in prompts/, and gates never repair (D-10). It
takes the generator's draft_explanation and layers the now-verified artifacts
on top: the sandbox-captured stdout for trace, and the sandbox-confirmed
bug_lines plus the defect_audit gate's confirmed defect for spot_the_bug.

The `verified` block is always built from ground truth, never from the
draft. If the draft explanation doesn't even reference the verified facts,
that is flagged (mismatch_flagged/mismatch_detail) for human review rather
than silently smoothed over -- the verified facts still win, but the
discrepancy is surfaced, not hidden.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from pipeline.schemas import STBCandidate, TraceCandidate
from pipeline.semantic_gates import GateOutcome


@dataclasses.dataclass(frozen=True)
class FinalExplanation:
    explanation: dict[str, Any]
    mismatch_flagged: bool
    mismatch_detail: str | None = None


def finalize_stb_explanation(
    candidate: STBCandidate,
    *,
    has_bug: bool,
    verified_bug_lines: list[int],
    defect_audit_outcome: GateOutcome | None = None,
) -> FinalExplanation:
    draft = candidate.draft_explanation
    mismatch = False
    detail: str | None = None

    if has_bug:
        noted_lines = {note.line for note in draft.line_notes}
        if not (noted_lines & set(verified_bug_lines)):
            mismatch = True
            detail = (
                f"draft_explanation.line_notes ({sorted(noted_lines)}) does not reference "
                f"the sandbox-verified bug_lines ({verified_bug_lines})"
            )

    verified: dict[str, Any] = {
        "bug_lines": verified_bug_lines,
        "confirmed_by": (
            "sandbox_execution (twin-snippet: failing test on buggy code, passing on fixed code)"
            if has_bug
            else "sandbox_execution (test passes on the code as written; defect_audit confirmed "
            "zero defects)"
        ),
    }
    if defect_audit_outcome is not None and defect_audit_outcome.raw:
        defects = defect_audit_outcome.raw.get("defects") or []
        if defects:
            verified["confirmed_defect_description"] = defects[0].get("description")
            verified["confirmed_defect_exposed_by"] = defects[0].get("exposed_by")

    explanation = {
        "summary": draft.summary,
        "principle": draft.principle,
        "line_notes": [note.model_dump() for note in draft.line_notes],
        "verified": verified,
        "mismatch_flagged": mismatch,
        "mismatch_detail": detail,
    }
    return FinalExplanation(
        explanation=explanation,
        mismatch_flagged=mismatch,
        mismatch_detail=detail,
    )


def finalize_trace_explanation(
    candidate: TraceCandidate,
    *,
    captured_stdout: str,
) -> FinalExplanation:
    draft = candidate.draft_explanation
    mismatch = captured_stdout not in draft.summary
    detail = (
        None
        if not mismatch
        else (
            "draft_explanation.summary does not literally reference the sandbox-captured output "
            f"{captured_stdout!r}; the verified output is authoritative regardless"
        )
    )

    explanation = {
        "summary": draft.summary,
        "principle": draft.principle,
        "trace_table": [entry.model_dump() for entry in draft.trace_table],
        "why_wrong": [entry.model_dump() for entry in draft.why_wrong],
        "verified": {
            "captured_stdout": captured_stdout,
            "confirmed_by": "sandbox_execution (double-run determinism verified)",
        },
        "mismatch_flagged": mismatch,
        "mismatch_detail": detail,
    }
    return FinalExplanation(
        explanation=explanation,
        mismatch_flagged=mismatch,
        mismatch_detail=detail,
    )
