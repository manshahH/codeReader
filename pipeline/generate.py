"""Exercise generation.

Loads the generator templates from prompts/*.md, fills {{vars}} from the
sampled ExerciseSpec, calls the LLM, and parses the JSON output with a strict
schema. Retry policy (prompts/README.md, D-10): a JSON-parse failure gets
exactly one retry with a "valid JSON only" nudge; a schema-validation failure
or an explicit {"abort": true} is discarded immediately, no retry.

The generator's claimed answers are captured here but NEVER trusted downstream
-- sandbox_gate re-derives ground truth by execution (D-9, D-11).
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

from pydantic import ValidationError

from pipeline.llm_client import LLMClient
from pipeline.schemas import STBCandidate, TraceCandidate
from pipeline.spec_sampler import ExerciseSpec

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
PYTHON_VERSION = "3.12"

_TEMPLATE_FILES = {
    # v5 (D-86): byte-identical instructional content to v4 (D-82), with the
    # varying `## Specification` block RELOCATED to the very END of the user
    # message so the large static prefix (persona + difficulty scale + the three
    # worked examples + all constraints + the output schema) is one stable,
    # spec-independent chunk OpenAI's prompt cache can serve on every call. v4's
    # decomposition (correct-code-first -> plant one bug -> DERIVE the divergence
    # as required fields -> a test that prints repr(result) and asserts on the
    # divergence input), the free B3 schema check, and the B4 execution claim-
    # check are all unchanged -- only the spec's position in the prompt moved.
    "spot_the_bug": PROMPTS_DIR / "generator_spot_the_bug_python_v5.md",
    "trace": PROMPTS_DIR / "generator_trace_python_v2.md",
    # predict_the_fix reuses a verified spot_the_bug (buggy, fixed, test)
    # triple and only asks the model for wrong-fix distractors (D-80).
    "predict_the_fix": PROMPTS_DIR / "generator_predict_the_fix_python_v1.md",
    # Feedback-driven repair templates (D-83): handed the original candidate + the
    # specific failed check + concrete evidence, asked to change ONLY what the
    # failure requires. A repaired candidate goes through the full gate chain.
    "repair_spot_the_bug": PROMPTS_DIR / "repair_spot_the_bug_python_v1.md",
    "repair_trace": PROMPTS_DIR / "repair_trace_python_v1.md",
}
_SCHEMA_BY_TYPE: dict[str, type[STBCandidate] | type[TraceCandidate]] = {
    "spot_the_bug": STBCandidate,
    "trace": TraceCandidate,
}
_TEMPERATURE = 0.8
_JSON_ONLY_NUDGE = (
    "\n\nIMPORTANT: your previous response could not be parsed as JSON. Output "
    "a single valid JSON object and nothing else: no markdown fences, no "
    "commentary, no trailing text."
)

_TEMPLATE_ID_RE = re.compile(r"^#\s*prompt_template_id:\s*(\S+)", re.MULTILINE)
_BEGIN_RE = re.compile(r"^=+\s*BEGIN (SYSTEM|USER)\s*=+$")
_END_RE = re.compile(r"^=+\s*END (SYSTEM|USER)\s*=+$")


@dataclasses.dataclass(frozen=True)
class LoadedTemplate:
    template_id: str
    system: str
    user: str


def load_template(exercise_type: str) -> LoadedTemplate:
    path = _TEMPLATE_FILES[exercise_type]
    text = path.read_text(encoding="utf-8")

    id_match = _TEMPLATE_ID_RE.search(text)
    if not id_match:
        raise ValueError(f"no prompt_template_id header found in {path}")

    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        begin_match = _BEGIN_RE.match(line)
        end_match = _END_RE.match(line)
        if begin_match:
            current = begin_match.group(1)
            buffer = []
            continue
        if end_match and current == end_match.group(1):
            sections[current] = "\n".join(buffer)
            current = None
            continue
        if current:
            buffer.append(line)

    if "SYSTEM" not in sections or "USER" not in sections:
        raise ValueError(f"template {path} missing BEGIN/END SYSTEM or USER markers")

    return LoadedTemplate(
        template_id=id_match.group(1),
        system=sections["SYSTEM"],
        user=sections["USER"],
    )


def _render(template_text: str, variables: dict[str, object]) -> str:
    rendered = template_text
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _spec_variables(spec: ExerciseSpec) -> dict[str, object]:
    variables: dict[str, object] = {
        "python_version": PYTHON_VERSION,
        "concept": spec.concept,
        "difficulty": spec.difficulty,
        "domain": spec.domain,
        "line_budget_min": spec.line_budget_min,
        "line_budget_max": spec.line_budget_max,
        "avoid_patterns": json.dumps(list(spec.avoid_patterns)),
    }
    if spec.type == "spot_the_bug":
        variables["has_bug"] = "true" if spec.has_bug else "false"
    return variables


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


@dataclasses.dataclass(frozen=True)
class GenerationOutcome:
    candidate: STBCandidate | TraceCandidate | None
    template_id: str
    raw_text: str
    discard_reason: str | None = None

    @property
    def survived(self) -> bool:
        return self.candidate is not None


def generate_candidate(spec: ExerciseSpec, llm_client: LLMClient) -> GenerationOutcome:
    template = load_template(spec.type)
    variables = _spec_variables(spec)
    user_prompt = _render(template.user, variables)

    raw = llm_client.complete(system=template.system, user=user_prompt, temperature=_TEMPERATURE)
    parsed = _try_parse_json(raw)

    if parsed is None:
        # Sole exception to "no repair" (D-10): one retry, JSON-parse failures only.
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
                discard_reason="json_parse_failed",
            )

    if isinstance(parsed, dict) and parsed.get("abort") is True:
        reason = parsed.get("reason", "unspecified")
        return GenerationOutcome(
            candidate=None,
            template_id=template.template_id,
            raw_text=raw,
            discard_reason=f"generator_aborted: {reason}",
        )

    schema = _SCHEMA_BY_TYPE[spec.type]
    try:
        candidate = schema.model_validate(parsed)
    except ValidationError as exc:
        return GenerationOutcome(
            candidate=None,
            template_id=template.template_id,
            raw_text=raw,
            discard_reason=f"schema_validation_failed: {exc.error_count()} errors",
        )

    return GenerationOutcome(candidate=candidate, template_id=template.template_id, raw_text=raw)
