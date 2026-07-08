from __future__ import annotations

import json

import pytest
from pipeline.config import GateModelConflictError, PipelineSettings
from pipeline.llm_client import ScriptedLLMClient
from pipeline.semantic_gates import GateVerdict, defect_audit, reasons, solver

_BUGGY_CODE = "def f(prices):\n    updated = prices\n    return updated\n"


def _client(response: dict) -> ScriptedLLMClient:
    return ScriptedLLMClient([json.dumps(response)])


# --- defect_audit -----------------------------------------------------------


def test_defect_audit_passes_exactly_one_overlapping_defect() -> None:
    client = _client(
        {"defects": [{"lines": [2], "description": "aliasing bug", "exposed_by": "mutation test"}]},
    )

    outcome = defect_audit(_BUGGY_CODE, has_bug=True, bug_lines=[2], llm_client=client)

    assert outcome.verdict == GateVerdict.PASS


def test_defect_audit_rejects_two_bug_candidate() -> None:
    client = _client(
        {
            "defects": [
                {"lines": [2], "description": "aliasing bug", "exposed_by": "mutation test"},
                {"lines": [5], "description": "unrelated off-by-one", "exposed_by": "loop test"},
            ],
        },
    )

    outcome = defect_audit(_BUGGY_CODE, has_bug=True, bug_lines=[2], llm_client=client)

    assert outcome.verdict == GateVerdict.REJECT


def test_defect_audit_flags_zero_defects_when_has_bug_true() -> None:
    client = _client({"defects": []})

    outcome = defect_audit(_BUGGY_CODE, has_bug=True, bug_lines=[2], llm_client=client)

    assert outcome.verdict == GateVerdict.FLAG


def test_defect_audit_passes_zero_defects_when_has_bug_false() -> None:
    client = _client({"defects": []})

    outcome = defect_audit(_BUGGY_CODE, has_bug=False, bug_lines=[], llm_client=client)

    assert outcome.verdict == GateVerdict.PASS


# --- solver ------------------------------------------------------------------


def test_solver_passes_when_answer_matches_key() -> None:
    client = _client(
        {"answer": {"choice_id": "a"}, "confidence": 0.95, "problems_with_the_exercise": []},
    )

    outcome = solver({"code": "print(1)"}, correct_answer={"choice_id": "a"}, llm_client=client)

    assert outcome.verdict == GateVerdict.PASS


def test_solver_rejects_confident_mis_keyed_answer() -> None:
    client = _client(
        {"answer": {"choice_id": "b"}, "confidence": 0.9, "problems_with_the_exercise": []},
    )

    outcome = solver({"code": "print(1)"}, correct_answer={"choice_id": "a"}, llm_client=client)

    assert outcome.verdict == GateVerdict.REJECT


def test_solver_flags_low_confidence_wrong_answer_for_human_review() -> None:
    client = _client(
        {"answer": {"choice_id": "b"}, "confidence": 0.4, "problems_with_the_exercise": []},
    )

    outcome = solver({"code": "print(1)"}, correct_answer={"choice_id": "a"}, llm_client=client)

    assert outcome.verdict == GateVerdict.FLAG


def test_solver_flags_when_problems_reported_even_if_correct() -> None:
    client = _client(
        {
            "answer": {"choice_id": "a"},
            "confidence": 0.99,
            "problems_with_the_exercise": ["choice b is also arguably correct"],
        },
    )

    outcome = solver({"code": "print(1)"}, correct_answer={"choice_id": "a"}, llm_client=client)

    assert outcome.verdict == GateVerdict.FLAG


# --- reasons -------------------------------------------------------------------

_REASON_OPTIONS = [
    {"id": "a", "text": "aliasing mutates the caller's dict"},
    {"id": "b", "text": "off-by-one in the loop"},
    {"id": "c", "text": "wrong rounding mode"},
    {"id": "d", "text": "discount applied twice"},
]


def test_reasons_passes_exactly_one_correct_matching_key() -> None:
    client = _client(
        {
            "verdicts": [
                {"id": "a", "classification": "correct", "justification": "j"},
                {"id": "b", "classification": "wrong", "justification": "j"},
                {"id": "c", "classification": "wrong", "justification": "j"},
                {"id": "d", "classification": "wrong", "justification": "j"},
            ],
        },
    )

    outcome = reasons(
        _BUGGY_CODE,
        reason_options=_REASON_OPTIONS,
        correct_reason_id="a",
        llm_client=client,
    )

    assert outcome.verdict == GateVerdict.PASS


def test_reasons_rejects_partially_defensible_distractor() -> None:
    client = _client(
        {
            "verdicts": [
                {"id": "a", "classification": "correct", "justification": "j"},
                {"id": "b", "classification": "partially_defensible", "justification": "j"},
                {"id": "c", "classification": "wrong", "justification": "j"},
                {"id": "d", "classification": "wrong", "justification": "j"},
            ],
        },
    )

    outcome = reasons(
        _BUGGY_CODE,
        reason_options=_REASON_OPTIONS,
        correct_reason_id="a",
        llm_client=client,
    )

    assert outcome.verdict == GateVerdict.REJECT


def test_reasons_rejects_two_options_classified_correct() -> None:
    client = _client(
        {
            "verdicts": [
                {"id": "a", "classification": "correct", "justification": "j"},
                {"id": "b", "classification": "correct", "justification": "j"},
                {"id": "c", "classification": "wrong", "justification": "j"},
                {"id": "d", "classification": "wrong", "justification": "j"},
            ],
        },
    )

    outcome = reasons(
        _BUGGY_CODE,
        reason_options=_REASON_OPTIONS,
        correct_reason_id="a",
        llm_client=client,
    )

    assert outcome.verdict == GateVerdict.REJECT


# --- GATE_MODEL != GENERATOR_MODEL enforcement (D-14) -------------------------


def test_gate_and_generator_model_equality_is_rejected() -> None:
    settings = PipelineSettings(
        ANTHROPIC_API_KEY="test-key",
        GATE_MODEL="same-model",
        GENERATOR_MODEL="same-model",
    )

    with pytest.raises(GateModelConflictError):
        settings.assert_gate_and_generator_models_differ()


def test_gate_and_generator_model_difference_is_accepted() -> None:
    settings = PipelineSettings(
        ANTHROPIC_API_KEY="test-key",
        GATE_MODEL="model-a",
        GENERATOR_MODEL="model-b",
    )

    settings.assert_gate_and_generator_models_differ()  # must not raise
