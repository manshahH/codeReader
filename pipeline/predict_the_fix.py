"""predict_the_fix derivation (D-80).

Derived from a sandbox-verified spot_the_bug candidate: it reuses that
candidate's (buggy_code, fixed_code, test_code) triple -- already proven by
execution to fail on buggy and pass on fixed -- and asks the generator ONLY for
wrong-fix distractors. Every distractor is then re-executed against the same
test in the sandbox and MUST STILL FAIL; the correct choice is the verified
fixed_code, never a model claim (invariant 1 / D-9). Grading is deterministic
(choice_id), same as trace, so there is zero per-answer LLM cost.

This module owns the derivation logic (generate -> static gate -> sandbox gate
-> assemble the payload/grading/explanation dicts). The DB insert lives in
publish.insert_predict_the_fix, per the module boundary law (only publish.py
touches backend.app).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import random
import re
from typing import Any

from pipeline import static_gate
from pipeline.generate import load_template
from pipeline.llm_client import LLMClient
from pipeline.sandbox_gate import validate_predict_the_fix
from pipeline.schemas import PredictFixCandidate, STBCandidate

PYTHON_VERSION = "3.12"
_TEMPERATURE = 0.8
_QUESTION = "The test below fails on this code. Which change makes the test pass?"
# The failing-test output shown to the user is trimmed to the tail of stderr
# (the AssertionError and its message), not the whole traceback.
_TEST_OUTPUT_TAIL = 600
_CHOICE_IDS = ("a", "b", "c", "d")


@dataclasses.dataclass(frozen=True)
class PTFArtifacts:
    """Everything publish.insert_predict_the_fix needs, all execution-grounded."""

    payload: dict[str, Any]
    grading: dict[str, Any]
    explanation: dict[str, Any]
    content_hash: str
    correct_choice_id: str


@dataclasses.dataclass(frozen=True)
class PTFDerivationOutcome:
    artifacts: PTFArtifacts | None
    reject_stage: str | None  # None on success; else the stage that rejected
    validation_report: dict[str, Any]

    @property
    def survived(self) -> bool:
        return self.artifacts is not None


def _render(template_text: str, variables: dict[str, object]) -> str:
    rendered = template_text
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _try_parse_json(raw: str) -> dict | None:
    attempts = [raw]
    stripped = raw.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if fence_match:
        attempts.append(fence_match.group(1))
    for text in attempts:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        else:
            return parsed
    return None


def generate_wrong_fixes(
    *,
    buggy_code: str,
    fixed_code: str,
    test_code: str,
    concept: str,
    domain: str,
    llm_client: LLMClient,
) -> tuple[PredictFixCandidate | None, str | None]:
    """Ask the generator for 3 wrong-fix distractors. Returns
    (candidate, discard_reason); candidate is None on any parse/abort/schema
    failure (a discard, never a repair -- D-10; the correct choice is already
    verified upstream, so a failed distractor generation just skips deriving a
    predict_the_fix for this STB, it never blocks the STB itself).
    """
    template = load_template("predict_the_fix")
    variables = {
        "python_version": PYTHON_VERSION,
        "concept": concept,
        "domain": domain,
        "buggy_code": buggy_code,
        "fixed_code": fixed_code,
        "test_code": test_code,
    }
    user_prompt = _render(template.user, variables)
    raw = llm_client.complete(system=template.system, user=user_prompt, temperature=_TEMPERATURE)
    parsed = _try_parse_json(raw)
    if parsed is None:
        return None, "json_parse_failed"
    if isinstance(parsed, dict) and parsed.get("abort") is True:
        return None, f"generator_aborted: {parsed.get('reason', 'unspecified')}"
    try:
        return PredictFixCandidate.model_validate(parsed), None
    except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError or bad shape
        return None, f"schema_validation_failed: {exc}"


def derive_artifacts(
    *,
    stb_candidate: STBCandidate,
    wrong_fixes: PredictFixCandidate,
    rng: random.Random,
    line_budget_max: int,
) -> PTFDerivationOutcome:
    """Static-gate every wrong fix, sandbox-prove each STILL FAILS the test,
    then assemble the choice list (correct = verified fixed_code, order
    randomized). Rejects (never repairs) on any gate failure.
    """
    report: dict[str, Any] = {"template_id": "ptf_py_v1"}
    variant_codes = [v.code for v in wrong_fixes.wrong_fixes]

    # Static gate on each shown-to-the-user variant (max line budget only, per
    # D-80; forbidden imports/calls and hint words always run).
    static_violations: list[str] = []
    for code in variant_codes:
        result = static_gate.check(code, line_budget=(None, line_budget_max))
        static_violations.extend(result.violations)
    report["static_gate"] = {"accepted": not static_violations, "violations": static_violations}
    if static_violations:
        return PTFDerivationOutcome(None, "ptf_static_gate", report)

    sandbox = validate_predict_the_fix(
        buggy_code=stb_candidate.buggy_code,
        fixed_code=stb_candidate.fixed_code,
        test_code=stb_candidate.test_code,
        wrong_fixes=variant_codes,
    )
    report["sandbox_gate"] = sandbox.as_report()
    if not sandbox.accepted:
        return PTFDerivationOutcome(None, "ptf_sandbox_gate", report)

    # Assemble choices: the verified fix plus the 3 proven-still-failing
    # distractors, order randomized so the correct one is not always first.
    entries: list[dict[str, Any]] = [
        {"code": stb_candidate.fixed_code, "note": None, "is_correct": True},
    ]
    for variant in wrong_fixes.wrong_fixes:
        entries.append({"code": variant.code, "note": variant.note, "is_correct": False})
    rng.shuffle(entries)

    choices: list[dict[str, str]] = []
    why_wrong: list[dict[str, str]] = []
    correct_choice_id = ""
    for choice_id, entry in zip(_CHOICE_IDS, entries, strict=True):
        choices.append({"id": choice_id, "text": entry["code"]})
        if entry["is_correct"]:
            correct_choice_id = choice_id
        else:
            why_wrong.append({"choice_id": choice_id, "note": entry["note"]})

    test_output = (sandbox.captured_test_output or "").strip()[-_TEST_OUTPUT_TAIL:]

    payload = {
        "code": stb_candidate.buggy_code,
        "context_note": stb_candidate.context_note,
        "question": _QUESTION,
        "failing_test": stb_candidate.test_code,
        "test_output": test_output,
        # answer_mode mirrors the STB/trace payload convention; the client
        # renders a choice list of code diffs.
        "answer_mode": "choose_fix",
        "choices": choices,
    }
    grading = {
        "mode": "deterministic",
        "correct_choice_id": correct_choice_id,
        "artifacts": {
            "fixed_code_hash": hashlib.sha256(
                stb_candidate.fixed_code.encode("utf-8"),
            ).hexdigest(),
            "sandbox_checks": sandbox.as_report(),
        },
    }
    explanation = {
        "summary": stb_candidate.draft_explanation.summary,
        "principle": stb_candidate.draft_explanation.principle,
        "why_wrong": why_wrong,
        "verified": {
            # The correct fix is the execution-proven fixed_code, shown as the
            # winning choice; recorded here for review receipts (D-49 spirit).
            "correct_choice_id": correct_choice_id,
        },
    }
    content_hash = _ptf_content_hash(stb_candidate.buggy_code, variant_codes)

    return PTFDerivationOutcome(
        PTFArtifacts(
            payload=payload,
            grading=grading,
            explanation=explanation,
            content_hash=content_hash,
            correct_choice_id=correct_choice_id,
        ),
        None,
        report,
    )


def _ptf_content_hash(buggy_code: str, variant_codes: list[str]) -> str:
    """A distinct content hash for a predict_the_fix row's `source` bookkeeping.

    Plain sha256 over buggy_code plus the sorted wrong-fix codes -- NOT the
    AST-normalized dedup hash, and deliberately distinct from the parent STB's
    (which hashes buggy_code alone), so a predict_the_fix never collides with
    the spot_the_bug it was derived from. predict_the_fix is not run through the
    AST-dedup gate: it is derived from an already-deduped STB, so it is unique
    by construction (a duplicate STB never survives to spawn a duplicate PTF).
    """
    joined = buggy_code + "\n---\n" + "\n---\n".join(sorted(variant_codes))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
