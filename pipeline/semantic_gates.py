"""Semantic gates: defect_audit -> solver -> reasons, from prompts/gates_v1.md.

Run at temperature 0 on GATE_MODEL, which must differ from GENERATOR_MODEL
(D-14) -- a model grading its own output inherits its own blind spots. Gates
never repair (D-10): every outcome is PASS, REJECT, or FLAG (send to human
review), exactly the three-way rule gates_v1.md specifies per gate. This is
deliberately not collapsed to a binary pass/reject.
"""

from __future__ import annotations

import dataclasses
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pipeline.llm_client import LLMClient

REPO_ROOT = Path(__file__).resolve().parent.parent
GATES_PATH = REPO_ROOT / "prompts" / "gates_v1.md"

_GATE_TEMPLATE_IDS = {
    "defect_audit": "gate_defect_audit_v1",
    "solver": "gate_solver_v1",
    "reasons": "gate_reasons_v1",
}
_JUDGE_SYSTEM = (
    "You are a rigorous, literal code reviewer. Output a single JSON object "
    "and nothing else: no markdown fences, no commentary."
)
_TEMPERATURE = 0.0


class GateVerdict(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    FLAG = "flag"  # needs human review


@dataclasses.dataclass(frozen=True)
class GateOutcome:
    verdict: GateVerdict
    detail: str
    raw: dict[str, Any] | None = None

    def as_report(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "detail": self.detail, "raw": self.raw}


def _load_gate_prompt(gate_key: str) -> str:
    text = GATES_PATH.read_text(encoding="utf-8")
    template_id = _GATE_TEMPLATE_IDS[gate_key]
    # Match the section header ("## GATE 2: gate_solver_v1"), not the file's
    # opening comment line, which lists all three ids together and would
    # otherwise match first, silently loading the wrong gate's prompt.
    header_match = re.search(rf"^## GATE \d+: {re.escape(template_id)}\b", text, re.MULTILINE)
    if not header_match:
        raise ValueError(f"no '## GATE N: {template_id}' header found in {GATES_PATH}")
    begin_idx = text.index("BEGIN PROMPT", header_match.end())
    end_idx = text.index("END PROMPT", begin_idx)
    return text[begin_idx + len("BEGIN PROMPT") : end_idx].strip("\n")


def _render(template_text: str, variables: dict[str, object]) -> str:
    rendered = template_text
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _parse_json_response(raw: str) -> dict | None:
    stripped = raw.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    for text in (raw, fence_match.group(1) if fence_match else None):
        if text is None:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


# --- response schemas ------------------------------------------------------


class _Defect(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lines: list[int]
    description: str
    exposed_by: str


class _DefectAuditResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    defects: list[_Defect]


class _SolverAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line: int | None = None
    reason_id: str | None = None
    choice_id: str | None = None


class _SolverResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: _SolverAnswer
    confidence: float = Field(ge=0.0, le=1.0)
    problems_with_the_exercise: list[str] = Field(default_factory=list)


class _ReasonVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    classification: str
    justification: str


class _ReasonsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdicts: list[_ReasonVerdict]


# --- gate 1: defect_audit (spot_the_bug only) ------------------------------


def defect_audit(
    buggy_code: str,
    *,
    has_bug: bool,
    bug_lines: list[int],
    llm_client: LLMClient,
    python_version: str = "3.12",
) -> GateOutcome:
    prompt = _render(
        _load_gate_prompt("defect_audit"),
        {"python_version": python_version, "buggy_code": buggy_code},
    )
    raw = llm_client.complete(system=_JUDGE_SYSTEM, user=prompt, temperature=_TEMPERATURE)
    parsed = _parse_json_response(raw)
    if parsed is None:
        return GateOutcome(GateVerdict.REJECT, "defect_audit response was not parseable JSON")

    try:
        response = _DefectAuditResponse.model_validate(parsed)
    except ValidationError as exc:
        return GateOutcome(
            GateVerdict.REJECT,
            f"defect_audit schema violation: {exc.error_count()} errors",
        )

    defects = response.defects
    report = response.model_dump()

    if has_bug:
        if len(defects) == 0:
            return GateOutcome(
                GateVerdict.FLAG,
                "defect_audit found zero defects on a has_bug=true candidate",
                report,
            )
        if len(defects) == 1 and set(defects[0].lines) & set(bug_lines):
            return GateOutcome(
                GateVerdict.PASS,
                "exactly one defect, overlapping bug_lines",
                report,
            )
        return GateOutcome(
            GateVerdict.REJECT,
            f"defect_audit reported {len(defects)} defect(s) not matching the intended bug_lines",
            report,
        )

    if len(defects) == 0:
        return GateOutcome(GateVerdict.PASS, "no defects on a has_bug=false candidate", report)
    return GateOutcome(
        GateVerdict.FLAG,
        f"defect_audit reported {len(defects)} defect(s) on a has_bug=false candidate",
        report,
    )


# --- gate 2: solver (both types) -------------------------------------------


def solver(
    payload_json: dict[str, Any],
    *,
    correct_answer: dict[str, Any],
    llm_client: LLMClient,
    compare_keys: set[str] | None = None,
    acceptable_lines: list[int] | None = None,
) -> GateOutcome:
    """`compare_keys` restricts equality to a subset of the answer's fields.

    Needed for spot_the_bug's has_bug=false case: the solver's answer schema
    always includes a "line", but there is no bug line to compare against, so
    the caller passes compare_keys={"reason_id"} to ignore it.

    `acceptable_lines` (D-52): when set, the answer's "line" matches if it is
    ANY member, with the remaining fields still compared exactly. A verified
    multi-line bug has several equally correct lines; keying to one exact
    line wrongly rejected a solver that named another of them as "mis-keyed".
    """
    prompt = _render(
        _load_gate_prompt("solver"),
        {"payload_json": json.dumps(payload_json, indent=2)},
    )
    raw = llm_client.complete(system=_JUDGE_SYSTEM, user=prompt, temperature=_TEMPERATURE)
    parsed = _parse_json_response(raw)
    if parsed is None:
        return GateOutcome(GateVerdict.REJECT, "solver response was not parseable JSON")

    try:
        response = _SolverResponse.model_validate(parsed)
    except ValidationError as exc:
        return GateOutcome(
            GateVerdict.REJECT,
            f"solver schema violation: {exc.error_count()} errors",
        )

    report = response.model_dump()
    answer = {k: v for k, v in response.answer.model_dump().items() if v is not None}
    if compare_keys is not None:
        answer = {k: v for k, v in answer.items() if k in compare_keys}
        correct_answer = {k: v for k, v in correct_answer.items() if k in compare_keys}

    if response.problems_with_the_exercise:
        return GateOutcome(
            GateVerdict.FLAG,
            "solver flagged the exercise as ambiguous/unfair",
            report,
        )

    if acceptable_lines is None:
        matched = answer == correct_answer
    else:
        line_ok = answer.get("line") in acceptable_lines
        rest = {k: v for k, v in answer.items() if k != "line"}
        rest_key = {k: v for k, v in correct_answer.items() if k != "line"}
        matched = line_ok and rest == rest_key

    if matched:
        return GateOutcome(GateVerdict.PASS, "solver matched the answer key", report)

    if response.confidence >= 0.8:
        return GateOutcome(
            GateVerdict.REJECT,
            f"solver confidently (p={response.confidence}) got a different answer:"
            " likely mis-keyed",
            report,
        )
    return GateOutcome(
        GateVerdict.FLAG,
        f"solver got a different answer at low confidence (p={response.confidence}): possibly a "
        "legitimately hard exercise",
        report,
    )


# --- gate 3: reasons (spot_the_bug only) -----------------------------------


def reasons(
    buggy_code: str,
    *,
    reason_options: list[dict[str, str]],
    correct_reason_id: str,
    llm_client: LLMClient,
    python_version: str = "3.12",
) -> GateOutcome:
    prompt = _render(
        _load_gate_prompt("reasons"),
        {
            "python_version": python_version,
            "buggy_code": buggy_code,
            "reason_options_json": json.dumps(reason_options, indent=2),
        },
    )
    raw = llm_client.complete(system=_JUDGE_SYSTEM, user=prompt, temperature=_TEMPERATURE)
    parsed = _parse_json_response(raw)
    if parsed is None:
        return GateOutcome(GateVerdict.REJECT, "reasons response was not parseable JSON")

    try:
        response = _ReasonsResponse.model_validate(parsed)
    except ValidationError as exc:
        return GateOutcome(
            GateVerdict.REJECT,
            f"reasons schema violation: {exc.error_count()} errors",
        )

    report = response.model_dump()
    classifications = {v.id: v.classification for v in response.verdicts}

    if any(c == "partially_defensible" for c in classifications.values()):
        # D-13: a hard reject, never a flag -- arguably-correct distractors fail
        # the most careful users, the ones who write disputes.
        return GateOutcome(
            GateVerdict.REJECT,
            "a distractor was classified partially_defensible",
            report,
        )

    correct_ids = [rid for rid, c in classifications.items() if c == "correct"]
    if len(correct_ids) == 1 and correct_ids[0] == correct_reason_id:
        return GateOutcome(GateVerdict.PASS, "exactly one correct option, matching the key", report)
    if len(correct_ids) >= 2:
        return GateOutcome(
            GateVerdict.REJECT,
            f"{len(correct_ids)} options classified correct",
            report,
        )
    return GateOutcome(
        GateVerdict.REJECT,
        f"correct classification(s) {correct_ids} do not match keyed reason {correct_reason_id!r}",
        report,
    )
