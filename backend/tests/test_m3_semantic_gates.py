from __future__ import annotations

import json

import pytest
from pipeline.config import GateModelConflictError, PipelineSettings
from pipeline.llm_client import ScriptedLLMClient
from pipeline.semantic_gates import GateVerdict, _number_lines, defect_audit, reasons, solver

_BUGGY_CODE = "def f(prices):\n    updated = prices\n    return updated\n"

# D-81 (pipeline defect #5). A real falsely-rejected candidate from this run's
# reject reports (semantic_gate_closure-late-binding_d3dad6218fb1.json): a
# 29-line class whose only bug is the late-binding closure on line 25
# (`def reporter():` -> `def reporter(cid=cid):`). The sandbox diff-derived the
# verified bug line as [25]; gpt-4o-mini identified the bug correctly but,
# counting un-numbered lines, reported it at line 20, so the old exact
# set-intersection killed it as a "line mismatch". These fixtures exercise the
# post-fix decision logic against that candidate's shape.
_DEEP_BUG_CODE = (
    "class PointsLedger:\n"
    "    def __init__(self):\n"
    "        self._accounts = {}\n"
    "\n"
    "    def add_account(self, customer_id):\n"
    "        if customer_id not in self._accounts:\n"
    "            self._accounts[customer_id] = []\n"
    "\n"
    "    def post_transaction(self, customer_id, amount, description):\n"
    "        if customer_id not in self._accounts:\n"
    "            raise ValueError('Unknown customer')\n"
    "        self._accounts[customer_id].append({'amount': amount})\n"
    "\n"
    "    def get_balance(self, customer_id):\n"
    "        return sum(t['amount'] for t in self._accounts[customer_id])\n"
    "\n"
    "    def generate_reporters(self, customer_ids):\n"
    "        reporters = []\n"
    "        for cid in customer_ids:\n"
    "            def reporter():\n"
    "                return (cid, self.get_balance(cid))\n"
    "            reporters.append(reporter)\n"
    "        return reporters\n"
)
_VERIFIED_BUG_LINE = 20  # `def reporter():` in _DEEP_BUG_CODE (diff-derived key)


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


# --- D-81 (pipeline defect #5): false-reject recovery + preserved guards -------


def test_number_lines_prefixes_each_line_so_the_model_reads_not_counts() -> None:
    # A1: the code fed to the gate carries an explicit `N|` prefix, so the gate
    # model reports the number it reads rather than one it miscounts. Line 20 of
    # the real falsely-rejected candidate is the `def reporter():` bug line.
    numbered = _number_lines(_DEEP_BUG_CODE)
    lines = numbered.split("\n")
    assert lines[0] == " 1| class PointsLedger:"
    assert lines[_VERIFIED_BUG_LINE - 1].startswith(f"{_VERIFIED_BUG_LINE}| ")
    assert "def reporter():" in lines[_VERIFIED_BUG_LINE - 1]


def test_defect_audit_accepts_the_real_falsely_rejected_closure_candidate() -> None:
    # The whole point of A1: with the code numbered, the gate model reports the
    # ONE real bug at its actual line (20 here). Old and new both accept an
    # exactly-on-line report -- this documents that the recovered candidate now
    # passes end to end.
    client = _client(
        {
            "defects": [
                {
                    "lines": [_VERIFIED_BUG_LINE],
                    "description": "reporter closure captures cid by reference (late binding)",
                    "exposed_by": "call the returned reporters after the loop",
                },
            ],
        },
    )

    outcome = defect_audit(
        _DEEP_BUG_CODE, has_bug=True, bug_lines=[_VERIFIED_BUG_LINE], llm_client=client,
    )

    assert outcome.verdict == GateVerdict.PASS


def test_defect_audit_accepts_correct_bug_reported_a_line_or_two_off_the_key() -> None:
    # A2: even reading numbered lines, the model may attribute a construct-
    # spanning bug to the def line or one line above/below. A +/-2 window
    # accepts it; the OLD exact set-intersection ({18} & {20} == empty) rejected
    # this exact case -- one of the run's real false rejects.
    client = _client(
        {
            "defects": [
                {
                    "lines": [_VERIFIED_BUG_LINE - 2],
                    "description": "late-binding closure over the loop variable",
                    "exposed_by": "call the returned reporters after the loop",
                },
            ],
        },
    )

    outcome = defect_audit(
        _DEEP_BUG_CODE, has_bug=True, bug_lines=[_VERIFIED_BUG_LINE], llm_client=client,
    )

    assert outcome.verdict == GateVerdict.PASS


def test_defect_audit_still_rejects_a_defect_far_from_the_verified_region() -> None:
    # The window is deliberately tight (2): a defect reported in a DIFFERENT
    # method, many lines from the verified bug, is a genuine accidental second
    # bug and must still reject. This proves A2 did not weaken the gate into
    # accepting anything.
    client = _client(
        {
            "defects": [
                {
                    "lines": [12],  # post_transaction, far from the closure at 20
                    "description": "unrelated state-handling issue",
                    "exposed_by": "some other call",
                },
            ],
        },
    )

    outcome = defect_audit(
        _DEEP_BUG_CODE, has_bug=True, bug_lines=[_VERIFIED_BUG_LINE], llm_client=client,
    )

    assert outcome.verdict == GateVerdict.REJECT


def test_defect_audit_still_rejects_a_genuine_two_bug_candidate_after_D81() -> None:
    # The "exactly one bug" invariant is the trust product and is NOT weakened:
    # two reported defects still reject even when one of them is on the key line.
    client = _client(
        {
            "defects": [
                {"lines": [_VERIFIED_BUG_LINE], "description": "the closure bug", "exposed_by": ""},
                {"lines": [15], "description": "a real second bug", "exposed_by": ""},
            ],
        },
    )

    outcome = defect_audit(
        _DEEP_BUG_CODE, has_bug=True, bug_lines=[_VERIFIED_BUG_LINE], llm_client=client,
    )

    assert outcome.verdict == GateVerdict.REJECT


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


def test_solver_passes_when_answer_names_any_verified_bug_line() -> None:
    # D-52: a multi-line bug has several equally correct lines; naming the
    # second verified line is a correct answer, not a mis-key.
    client = _client(
        {
            "answer": {"line": 5, "reason_id": "a"},
            "confidence": 0.9,
            "problems_with_the_exercise": [],
        },
    )

    outcome = solver(
        {"code": "print(1)"},
        correct_answer={"line": 2, "reason_id": "a"},
        llm_client=client,
        acceptable_lines=[2, 5],
    )

    assert outcome.verdict == GateVerdict.PASS


def test_solver_still_rejects_confident_answer_naming_a_line_outside_the_verified_set() -> None:
    client = _client(
        {
            "answer": {"line": 7, "reason_id": "a"},
            "confidence": 0.9,
            "problems_with_the_exercise": [],
        },
    )

    outcome = solver(
        {"code": "print(1)"},
        correct_answer={"line": 2, "reason_id": "a"},
        llm_client=client,
        acceptable_lines=[2, 5],
    )

    assert outcome.verdict == GateVerdict.REJECT


def test_solver_with_acceptable_lines_still_requires_the_reason_to_match() -> None:
    client = _client(
        {
            "answer": {"line": 2, "reason_id": "b"},
            "confidence": 0.9,
            "problems_with_the_exercise": [],
        },
    )

    outcome = solver(
        {"code": "print(1)"},
        correct_answer={"line": 2, "reason_id": "a"},
        llm_client=client,
        acceptable_lines=[2, 5],
    )

    assert outcome.verdict == GateVerdict.REJECT


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
