from __future__ import annotations

import json
import random

import pytest
from pipeline import taxonomy
from pipeline.dedup import content_hash, is_duplicate
from pipeline.explain import finalize_stb_explanation, finalize_trace_explanation
from pipeline.generate import generate_candidate, load_template
from pipeline.llm_client import ScriptedLLMClient
from pipeline.schemas import (
    Choice,
    LineNote,
    ReasonOption,
    STBCandidate,
    STBDraftExplanation,
    STBSelfCheck,
    TraceCandidate,
    TraceDraftExplanation,
    TraceSelfCheck,
    TraceTableEntry,
    WhyWrong,
)
from pipeline.semantic_gates import GateOutcome, GateVerdict
from pipeline.spec_sampler import ExerciseSpec, sample_batch, sample_spec
from pydantic import ValidationError

# --- taxonomy -----------------------------------------------------------


def test_taxonomy_has_no_duplicate_slugs_and_covers_both_types() -> None:
    slugs = [c.slug for c in taxonomy.CONCEPTS]
    assert len(slugs) == len(set(slugs))
    assert len(taxonomy.concepts_for_type("spot_the_bug")) > 0
    assert len(taxonomy.concepts_for_type("trace")) > 0
    assert 30 <= len(taxonomy.CONCEPTS) <= 50


def test_taxonomy_get_concept_round_trips() -> None:
    concept = taxonomy.CONCEPTS[0]
    assert taxonomy.get_concept(concept.slug) is concept


# --- spec_sampler ---------------------------------------------------------


def test_sample_spec_is_deterministic_for_a_given_seed() -> None:
    spec_a = sample_spec(random.Random(42), "spot_the_bug")
    spec_b = sample_spec(random.Random(42), "spot_the_bug")

    assert spec_a == spec_b


def test_sample_spec_has_bug_false_only_for_spot_the_bug() -> None:
    trace_spec = sample_spec(random.Random(1), "trace")
    assert trace_spec.has_bug is None

    rng = random.Random(7)
    stb_specs = [sample_spec(rng, "spot_the_bug") for _ in range(200)]
    false_rate = sum(1 for s in stb_specs if s.has_bug is False) / len(stb_specs)
    assert 0.05 < false_rate < 0.25  # sampled around the ~15% target


def test_sample_spec_avoid_patterns_uses_recent_history_for_the_sampled_concept() -> None:
    rng = random.Random(3)
    spec = sample_spec(rng, "spot_the_bug")
    history = {spec.concept: ["mechanism-a", "mechanism-b", "mechanism-c", "mechanism-d"]}

    rng2 = random.Random(3)
    spec_with_history = sample_spec(rng2, "spot_the_bug", recent_bug_mechanisms=history)

    assert spec_with_history.avoid_patterns == ("mechanism-b", "mechanism-c", "mechanism-d")


def test_sample_batch_alternates_type_mix() -> None:
    specs = sample_batch(random.Random(5), 4, type_mix=("spot_the_bug", "trace"))
    assert [s.type for s in specs] == ["spot_the_bug", "trace", "spot_the_bug", "trace"]


# --- generate.py: template loading ----------------------------------------


def test_load_template_parses_stb_template() -> None:
    template = load_template("spot_the_bug")

    assert template.template_id == "stb_py_v1"
    assert "senior Python engineer" in template.system
    assert "{{concept}}" in template.user
    assert "BEGIN USER" not in template.user


def test_load_template_parses_trace_template() -> None:
    template = load_template("trace")

    assert template.template_id == "trace_py_v1"
    assert "{{python_version}}" in template.user


# --- generate.py: parse/retry/discard policy ------------------------------

_GOOD_STB_JSON = {
    "buggy_code": "def f(prices):\n    return prices\n",
    "fixed_code": "def f(prices):\n    return prices\n",
    "bug_lines": [],
    "test_code": "assert f({'a': 1}) == {'a': 1}\n",
    "context_note": "note.",
    "reason_options": [
        {"id": "a", "text": "x"},
        {"id": "b", "text": "y"},
        {"id": "c", "text": "z"},
        {"id": "d", "text": "No bug; this is correct"},
    ],
    "correct_reason_id": "d",
    "draft_explanation": {
        "summary": "s",
        "principle": "p",
        "line_notes": [{"line": 1, "note": "n"}],
    },
    "concepts": ["off-by-one"],
    "self_difficulty": 2,
    "self_check": {
        "single_bug_confirmed": True,
        "runs_without_error_on_happy_path": True,
        "no_hinting_names_or_comments": True,
        "distractors_verifiably_wrong": True,
    },
}


def _spec(exercise_type: str = "spot_the_bug", has_bug: bool | None = False) -> ExerciseSpec:
    return ExerciseSpec(
        type=exercise_type,
        concept="off-by-one",
        difficulty=2,
        domain="checkout service",
        line_budget_min=1,
        line_budget_max=20,
        has_bug=has_bug,
        avoid_patterns=(),
    )


def test_generate_candidate_parses_clean_json_on_first_try() -> None:
    client = ScriptedLLMClient([json.dumps(_GOOD_STB_JSON)])

    outcome = generate_candidate(_spec(), client)

    assert outcome.survived
    assert isinstance(outcome.candidate, STBCandidate)
    assert len(client.calls) == 1


def test_generate_candidate_retries_once_on_json_parse_failure_then_succeeds() -> None:
    client = ScriptedLLMClient(["not json at all {{{", json.dumps(_GOOD_STB_JSON)])

    outcome = generate_candidate(_spec(), client)

    assert outcome.survived
    assert len(client.calls) == 2
    assert "valid JSON object" in client.calls[1]["user"]


def test_generate_candidate_discards_after_second_parse_failure_no_further_retry() -> None:
    client = ScriptedLLMClient(["not json", "still not json"])

    outcome = generate_candidate(_spec(), client)

    assert not outcome.survived
    assert outcome.discard_reason == "json_parse_failed"
    assert len(client.calls) == 2


def test_generate_candidate_discards_schema_violation_without_retry() -> None:
    bad = dict(_GOOD_STB_JSON)
    del bad["bug_lines"]  # required field missing
    client = ScriptedLLMClient([json.dumps(bad)])

    outcome = generate_candidate(_spec(), client)

    assert not outcome.survived
    assert outcome.discard_reason is not None
    assert outcome.discard_reason.startswith("schema_validation_failed")
    assert len(client.calls) == 1  # no retry for a semantic/schema failure


def test_generate_candidate_discards_explicit_abort_without_retry() -> None:
    abort_response = {"abort": True, "reason": "cannot satisfy constraints"}
    client = ScriptedLLMClient([json.dumps(abort_response)])

    outcome = generate_candidate(_spec(), client)

    assert not outcome.survived
    assert outcome.discard_reason == "generator_aborted: cannot satisfy constraints"
    assert len(client.calls) == 1


# --- dedup.py ---------------------------------------------------------------


def test_content_hash_is_stable_across_variable_renaming_and_literal_values() -> None:
    code_a = "def apply_discount(prices, pct):\n    updated = dict(prices)\n    return updated\n"
    code_b = "def apply_discount(costs, rate):\n    result = dict(costs)\n    return result\n"

    assert content_hash(code_a) == content_hash(code_b)


def test_content_hash_differs_for_different_builtin_calls() -> None:
    # Only user-bound identifiers are stripped; the choice of dict() vs list()
    # is meaningful content, not superficial naming, and must not collapse.
    code_a = "def f(items):\n    result = dict(items)\n    return result\n"
    code_b = "def f(items):\n    result = list(items)\n    return result\n"

    assert content_hash(code_a) != content_hash(code_b)


def test_content_hash_ignores_comments_and_docstrings() -> None:
    code_a = "def f(x):\n    return x + 1\n"
    code_b = 'def f(x):\n    """Adds one."""\n    # increment\n    return x + 1\n'

    assert content_hash(code_a) == content_hash(code_b)


def test_is_duplicate_checks_against_the_supplied_live_pool() -> None:
    code = "def f(x):\n    return x + 1\n"
    live_pool = {content_hash(code)}

    assert is_duplicate(code, live_pool)
    assert not is_duplicate("def g(y):\n    return y - 1\n", live_pool)


# --- schemas.py: why_wrong-covers-exactly-the-distractors validator ---------


def _trace_candidate_with_why_wrong(why_wrong_choice_ids: list[str]) -> dict:
    return {
        "code": "print(1)\n",
        "context_note": "note.",
        "question": "What does this code print?",
        "expected_stdout": "1",
        "choices": [
            {"id": "a", "text": "1", "misconception": None},
            {"id": "b", "text": "2", "misconception": "m1"},
            {"id": "c", "text": "0", "misconception": "m2"},
            {"id": "d", "text": "3", "misconception": "m3"},
        ],
        "correct_choice_id": "a",
        "draft_explanation": {
            "summary": "s",
            "principle": "p",
            "trace_table": [{"line": 1, "state": "n/a"}],
            "why_wrong": [{"choice_id": cid, "note": "n"} for cid in why_wrong_choice_ids],
        },
        "concepts": ["off-by-one"],
        "self_difficulty": 1,
        "self_check": {
            "traced_line_by_line_not_from_memory": True,
            "output_deterministic_and_repr_stable": True,
            "each_distractor_derived_from_named_misconception": True,
            "no_two_choices_identical": True,
        },
    }


def test_trace_candidate_accepts_why_wrong_covering_exactly_the_distractors() -> None:
    TraceCandidate.model_validate(_trace_candidate_with_why_wrong(["b", "c", "d"]))


def test_trace_candidate_rejects_why_wrong_missing_a_distractor() -> None:
    with pytest.raises(ValidationError):
        TraceCandidate.model_validate(_trace_candidate_with_why_wrong(["b", "c"]))


def test_trace_candidate_rejects_why_wrong_covering_the_correct_choice() -> None:
    with pytest.raises(ValidationError):
        TraceCandidate.model_validate(_trace_candidate_with_why_wrong(["a", "b", "c"]))


# --- explain.py --------------------------------------------------------------


def _stb_candidate_for_explain(line_notes: list[LineNote]) -> STBCandidate:
    return STBCandidate(
        buggy_code="def f(prices):\n    updated = prices\n    return updated\n",
        fixed_code="def f(prices):\n    updated = dict(prices)\n    return updated\n",
        bug_lines=[2],
        test_code="assert True\n",
        context_note="note.",
        reason_options=[
            ReasonOption(id="a", text="aliasing"),
            ReasonOption(id="b", text="x"),
            ReasonOption(id="c", text="y"),
            ReasonOption(id="d", text="z"),
        ],
        correct_reason_id="a",
        draft_explanation=STBDraftExplanation(
            summary="The function aliases the input dict instead of copying it.",
            principle="Copy mutable arguments before mutating them.",
            line_notes=line_notes,
        ),
        concepts=["aliasing-vs-copy"],
        self_difficulty=3,
        self_check=STBSelfCheck(
            single_bug_confirmed=True,
            runs_without_error_on_happy_path=True,
            no_hinting_names_or_comments=True,
            distractors_verifiably_wrong=True,
        ),
    )


def test_finalize_stb_explanation_no_mismatch_when_line_notes_cover_the_bug_line() -> None:
    candidate = _stb_candidate_for_explain([LineNote(line=2, note="binds the same dict object")])
    gate_outcome = GateOutcome(
        GateVerdict.PASS,
        "ok",
        {"defects": [{"lines": [2], "description": "aliasing", "exposed_by": "mutation test"}]},
    )

    result = finalize_stb_explanation(
        candidate,
        has_bug=True,
        verified_bug_lines=[2],
        defect_audit_outcome=gate_outcome,
    )

    assert result.mismatch_flagged is False
    assert result.explanation["verified"]["bug_lines"] == [2]
    assert result.explanation["verified"]["confirmed_defect_description"] == "aliasing"


def test_finalize_stb_explanation_flags_mismatch_when_line_notes_miss_the_bug_line() -> None:
    candidate = _stb_candidate_for_explain([LineNote(line=99, note="irrelevant note")])

    result = finalize_stb_explanation(candidate, has_bug=True, verified_bug_lines=[2])

    assert result.mismatch_flagged is True
    assert "99" in result.mismatch_detail or "[99]" in result.mismatch_detail
    # verified facts still win regardless of the mismatch
    assert result.explanation["verified"]["bug_lines"] == [2]


def _trace_candidate_for_explain(summary: str) -> TraceCandidate:
    return TraceCandidate(
        code="print(sum([1, 2, 3]))\n",
        context_note="note.",
        question="What does this code print?",
        expected_stdout="6",
        choices=[
            Choice(id="a", text="6", misconception=None),
            Choice(id="b", text="5", misconception="m1"),
            Choice(id="c", text="1", misconception="m2"),
            Choice(id="d", text="0", misconception="m3"),
        ],
        correct_choice_id="a",
        draft_explanation=TraceDraftExplanation(
            summary=summary,
            principle="sum() folds left to right.",
            trace_table=[TraceTableEntry(line=1, state="n/a")],
            why_wrong=[
                WhyWrong(choice_id="b", note="m1"),
                WhyWrong(choice_id="c", note="m2"),
                WhyWrong(choice_id="d", note="m3"),
            ],
        ),
        concepts=["control_flow"],
        self_difficulty=1,
        self_check=TraceSelfCheck(
            traced_line_by_line_not_from_memory=True,
            output_deterministic_and_repr_stable=True,
            each_distractor_derived_from_named_misconception=True,
            no_two_choices_identical=True,
        ),
    )


def test_finalize_trace_explanation_no_mismatch_when_summary_cites_the_captured_output() -> None:
    candidate = _trace_candidate_for_explain("sum([1, 2, 3]) prints 6.")

    result = finalize_trace_explanation(candidate, captured_stdout="6")

    assert result.mismatch_flagged is False
    assert result.explanation["verified"]["captured_stdout"] == "6"


def test_finalize_trace_explanation_flags_mismatch_when_summary_never_cites_the_output() -> None:
    candidate = _trace_candidate_for_explain("This prints the total of the list.")

    result = finalize_trace_explanation(candidate, captured_stdout="6")

    assert result.mismatch_flagged is True
    # verified output still wins regardless of the mismatch
    assert result.explanation["verified"]["captured_stdout"] == "6"
