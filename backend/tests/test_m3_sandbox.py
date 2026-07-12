from __future__ import annotations

import pytest
from pipeline.sandbox import runner
from pipeline.sandbox.runner import (
    SandboxResult,
    SandboxUnavailableError,
    run_python,
    verify_sandbox_available,
)
from pipeline.sandbox_gate import (
    validate_predict_the_fix,
    validate_spot_the_bug,
    validate_trace,
)
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
from pydantic import ValidationError

# --- the dry-run's own candidate (prompts/dryrun_stb_validation.py), ported ---

_BUGGY_CODE = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = prices\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_FIXED_CODE = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)
_STRONG_TEST = (
    "prices = {'A1': 100.0, 'B2': 50.0}\n"
    "result = apply_discount(prices, 10)\n"
    "assert result == {'A1': 90.0, 'B2': 45.0}\n"
    "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n"
)
# A "weak" test: checks the return value only, never checks that the caller's
# dict was left alone. The buggy code produces the right numbers (it just also
# mutates the input as a side effect), so this test PASSES on buggy code too --
# the exact weak-test sabotage the sandbox gate must catch.
_WEAK_TEST = (
    "prices = {'A1': 100.0, 'B2': 50.0}\n"
    "result = apply_discount(prices, 10)\n"
    "assert result == {'A1': 90.0, 'B2': 45.0}\n"
)


def _stb_candidate(
    *,
    test_code: str,
    bug_lines: list[int],
    fixed_code: str = _FIXED_CODE,
) -> STBCandidate:
    return STBCandidate(
        buggy_code=_BUGGY_CODE,
        fixed_code=fixed_code,
        bug_lines=bug_lines,
        test_code=test_code,
        context_note="Runs once per order in the checkout worker.",
        reason_options=[
            ReasonOption(id="a", text="The input price dict is mutated in place via aliasing."),
            ReasonOption(id="b", text="round() introduces floating point drift here."),
            ReasonOption(id="c", text="The loop skips the last SKU."),
            ReasonOption(id="d", text="discount_pct is applied twice."),
        ],
        correct_reason_id="a",
        draft_explanation=STBDraftExplanation(
            summary="updated = prices aliases the caller's dict instead of copying it.",
            principle="Copy a mutable argument before mutating it in place.",
            line_notes=[LineNote(line=2, note="Binds updated to the same dict object as prices.")],
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


def test_sandbox_gate_accepts_the_dryrun_good_candidate() -> None:
    candidate = _stb_candidate(test_code=_STRONG_TEST, bug_lines=[2])

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    passed_names = {c.name for c in result.checks if c.passed}
    assert passed_names == {
        "buggy_fails_test",
        "fixed_passes_test",
        "buggy_runs_clean",
        "deterministic_double_run",
        "fix_diff_real_and_minimal",
    }
    # D-49: the published key is diff-derived; here the claim happens to match.
    assert result.verified_bug_lines == [2]
    assert result.bug_lines_claim_mismatch is False


def test_sandbox_gate_rejects_weak_test_that_passes_on_buggy_code() -> None:
    candidate = _stb_candidate(test_code=_WEAK_TEST, bug_lines=[2])

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["buggy_fails_test"].passed is False


def test_sandbox_gate_accepts_has_bug_false_variant() -> None:
    candidate = _stb_candidate(
        test_code=_STRONG_TEST.replace(
            "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n",
            "",
        ),
        bug_lines=[],
        fixed_code=_BUGGY_CODE,
    )
    # has_bug=False: the "buggy" and "fixed" code are identical, and the test
    # simply proves the (correct) code passes on the tricky-looking path.

    result = validate_spot_the_bug(candidate, has_bug=False)

    assert result.accepted, result.as_report()


# --- fix_diff_real_and_minimal: diff-derived key (D-49), real diff (D-45) ---

# The fix inserts a brand new line (`import copy`) *and* changes the declared
# bug line (line 2 of buggy_code: aliasing -> a deep copy that needs the new
# import). A positional zip diff would flag every line from the insertion
# onward; the real diff must only flag line 2, since that's the only original
# line actually replaced or removed.
_FIXED_CODE_WITH_INSERTED_IMPORT = (
    "import copy\n"
    "\n"
    "def apply_discount(prices, discount_pct):\n"
    "    updated = copy.deepcopy(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)

# Same fix, but the fix also rewrites an UNDECLARED line (line 4: adds
# redundant parens, functionally identical, textually different) that isn't
# in the claimed bug_lines. Under D-49 this is ACCEPTED: the key is derived
# from the diff ([2, 4]) and the claim/diff mismatch is logged for review,
# not rejected -- rejecting on the claim was the transcription test D-49
# removed.
_FIXED_CODE_WITH_UNDECLARED_CHANGE = (
    "def apply_discount(prices, discount_pct):\n"
    "    updated = dict(prices)\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - (discount_pct / 100)), 2)\n"
    "    return updated\n"
)

# The "fix" only inserts a blank line and never touches the declared bug line
# (line 2 still aliases). Insertions alone must never satisfy bug_lines.
_FIXED_CODE_INSERTION_ONLY = (
    "def apply_discount(prices, discount_pct):\n"
    "\n"
    "    updated = prices\n"
    "    for sku in updated:\n"
    "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
    "    return updated\n"
)


def test_sandbox_gate_accepts_fix_that_inserts_a_line_alongside_the_declared_change() -> None:
    candidate = _stb_candidate(
        test_code=_STRONG_TEST,
        bug_lines=[2],
        fixed_code=_FIXED_CODE_WITH_INSERTED_IMPORT,
    )

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["fix_diff_real_and_minimal"].passed is True
    assert result.verified_bug_lines == [2]
    assert result.bug_lines_claim_mismatch is False


def test_sandbox_gate_accepts_undeclared_extra_change_with_derived_key_and_mismatch() -> None:
    # D-49 semantic change, recorded there explicitly: this scenario used to
    # reject on claim != diff. The key is now the diff-derived [2, 4] and the
    # mismatch is surfaced as a metric/flag for human review, not a reject.
    candidate = _stb_candidate(
        test_code=_STRONG_TEST,
        bug_lines=[2],
        fixed_code=_FIXED_CODE_WITH_UNDECLARED_CHANGE,
    )

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    assert result.verified_bug_lines == [2, 4]
    assert result.bug_lines_claim_mismatch is True


def test_sandbox_gate_accepts_correct_fix_with_wrongly_transcribed_bug_line_claim() -> None:
    # D-49: a perfect bug/test/fix whose declared bug_lines are off by one is
    # not a worse exercise; the diff-derived key wins and the mismatch is
    # logged. This was the single biggest false-reject class in the old
    # exact-match check.
    candidate = _stb_candidate(
        test_code=_STRONG_TEST,
        bug_lines=[3],  # wrong transcription; the fix actually changes line 2
    )

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    assert result.verified_bug_lines == [2]
    assert result.bug_lines_claim_mismatch is True


def test_sandbox_gate_rejects_fix_that_only_inserts_and_never_touches_the_declared_line() -> None:
    candidate = _stb_candidate(
        test_code=_STRONG_TEST,
        bug_lines=[2],
        fixed_code=_FIXED_CODE_INSERTION_ONLY,
    )

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["fix_diff_real_and_minimal"].passed is False
    assert "pure insertion" in checks_by_name["fix_diff_real_and_minimal"].detail
    assert result.verified_bug_lines is None


# A 10-line buggy function whose "fix" rewrites almost every line: over the
# minimal-fix cap of max(5, 20% of 10) = 5 changed original lines. The diff
# is so smeared that every changed line would count as a "correct" answer,
# which is no answer key at all -- must reject (D-49's second negative).
_BUGGY_CODE_TEN_LINES = (
    "def shipping_rate(weight_kg, zone):\n"
    "    base = 4.0\n"
    "    per_kg = 1.5\n"
    "    surcharge = 0.0\n"
    "    if zone == 'remote':\n"
    "        surcharge = 3.0\n"
    "    total = base + per_kg * weight_kg + surcharge\n"
    "    if total < 5.0:\n"
    "        total = 5.0\n"
    "    return total\n"
)
_FIXED_CODE_FULL_REWRITE = (
    "def shipping_rate(weight_kg, zone):\n"
    "    minimum = 5.0\n"
    "    rate = 1.5 * weight_kg\n"
    "    extra = 3.0 if zone == 'remote' else 0.0\n"
    "    subtotal = 4.0 + rate + extra\n"
    "    if subtotal < minimum:\n"
    "        return minimum\n"
    "    return subtotal\n"
)


def test_sandbox_gate_rejects_rewrite_sized_diff_as_not_a_minimal_fix() -> None:
    candidate = _stb_candidate(
        test_code="assert shipping_rate(2.0, 'local') >= 5.0\n",
        bug_lines=[7],
        fixed_code=_FIXED_CODE_FULL_REWRITE,
    ).model_copy(update={"buggy_code": _BUGGY_CODE_TEN_LINES})

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["fix_diff_real_and_minimal"].passed is False
    assert "rewrite" in checks_by_name["fix_diff_real_and_minimal"].detail
    assert result.verified_bug_lines is None


def test_sandbox_gate_accepts_candidate_whose_code_lacks_trailing_newlines() -> None:
    # D-50: the gate inserts the newline separator itself; a generator that
    # dropped the trailing newline used to produce buggy_code+test_code glued
    # into a SyntaxError and a false reject.
    candidate = _stb_candidate(
        test_code=_STRONG_TEST,
        bug_lines=[2],
    ).model_copy(
        update={
            "buggy_code": _BUGGY_CODE.rstrip("\n"),
            "fixed_code": _FIXED_CODE.rstrip("\n"),
        },
    )

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    assert result.verified_bug_lines == [2]


def test_sandbox_gate_rejects_has_bug_false_candidate_whose_fixed_code_differs_at_all() -> None:
    # has_bug=False must mean byte-identical code, not merely "bug_lines is
    # empty" -- a generator that quietly "improves" something it was told is
    # already correct must still be rejected. Unchanged in strictness by D-49.
    candidate = _stb_candidate(
        test_code=_STRONG_TEST.replace(
            "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n",
            "",
        ),
        bug_lines=[],
        fixed_code=_FIXED_CODE,  # differs from buggy_code (dict(prices) vs prices)
    )

    result = validate_spot_the_bug(candidate, has_bug=False)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["fix_diff_real_and_minimal"].passed is False
    assert result.verified_bug_lines is None


# --- D-82: v4 divergence fields, free B3 static check + B4 execution claim-check

_V4_BUGGY = (
    "def tier_discount(order_total):\n"
    "    if order_total > 100:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)
_V4_FIXED = (
    "def tier_discount(order_total):\n"
    "    if order_total >= 100:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)
# The v4 test prints repr(result) before asserting, so the sandbox captures the
# actual buggy/fixed results and claim-checks them (B4).
_V4_TEST = (
    "result = tier_discount(100)\n"
    "print(repr(result))\n"
    "assert result == 0.1, 'spend of exactly 100 should earn the discount'\n"
)


def _v4_candidate(
    *,
    buggy_result: str = "0.0",
    fixed_result: str = "0.1",
) -> STBCandidate:
    return STBCandidate(
        buggy_code=_V4_BUGGY,
        fixed_code=_V4_FIXED,
        bug_lines=[2],
        test_code=_V4_TEST,
        context_note="Runs once per order in the checkout worker.",
        reason_options=[
            ReasonOption(id="a", text="The threshold uses > where the spec says at least 100."),
            ReasonOption(id="b", text="round() introduces floating point drift here."),
            ReasonOption(id="c", text="The discount is applied twice."),
            ReasonOption(id="d", text="0.10 should be 0.1 (they are the same float)."),
        ],
        correct_reason_id="a",
        draft_explanation=STBDraftExplanation(
            summary="`>` excludes the exact threshold; `>=` includes it.",
            principle="'at least N' is >=, not >.",
            line_notes=[LineNote(line=2, note="Excludes order_total == 100 from the discount.")],
        ),
        concepts=["off-by-one"],
        self_difficulty=2,
        self_check=STBSelfCheck(
            single_bug_confirmed=True,
            runs_without_error_on_happy_path=True,
            no_hinting_names_or_comments=True,
            distractors_verifiably_wrong=True,
            test_input_is_on_the_divergence_boundary=True,
            test_asserts_on_divergence_input=True,
        ),
        bug_trigger_condition="order_total is exactly the threshold, 100",
        divergence_input="order_total = 100",
        buggy_result_on_divergence_input=buggy_result,
        fixed_result_on_divergence_input=fixed_result,
        divergence_justification="at exactly 100, > is False (0.0) but >= is True (0.1)",
    )


def test_schema_rejects_identical_divergence_results_for_free_before_the_sandbox() -> None:
    # B3: the model claiming buggy and fixed produce the SAME result on its own
    # divergence input is an admission the test cannot discriminate -- rejected
    # at schema validation, zero tokens, zero sandbox.
    with pytest.raises(ValidationError, match="cannot discriminate"):
        _v4_candidate(buggy_result="0.1", fixed_result="0.1")


def test_schema_rejects_partial_divergence_fields() -> None:
    # All-or-none: a v4 candidate that fills some divergence fields but not all
    # is malformed. (model_validate re-runs the validator; model_copy would not.)
    data = _v4_candidate().model_dump()
    data["divergence_justification"] = None
    with pytest.raises(ValidationError, match="must be provided together"):
        STBCandidate.model_validate(data)


def test_schema_accepts_a_candidate_with_no_divergence_fields_backward_compat() -> None:
    # v2/v3 candidates and every existing fixture omit the divergence fields and
    # must still validate.
    candidate = _stb_candidate(test_code=_STRONG_TEST, bug_lines=[2])

    assert candidate.buggy_result_on_divergence_input is None


def test_sandbox_gate_v4_claim_check_accepts_a_correct_prediction() -> None:
    candidate = _v4_candidate(buggy_result="0.0", fixed_result="0.1")

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert result.accepted, result.as_report()
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["stb_claim_matches_execution"].passed is True


def test_sandbox_gate_v4_claim_check_rejects_a_mispredicted_result() -> None:
    # B4 (D-11 for STB): the model claims buggy returns 0.5, but it actually
    # returns 0.0. A model that mis-predicts its own code's behavior wrote an
    # unreliable exercise -> reject, exactly as trace's claim-check does.
    candidate = _v4_candidate(buggy_result="0.5", fixed_result="0.1")

    result = validate_spot_the_bug(candidate, has_bug=True)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["stb_claim_matches_execution"].passed is False


def _trace_candidate(
    *,
    expected_stdout: str,
    distractor_text: str = "wrong output",
) -> TraceCandidate:
    return TraceCandidate(
        code="values = [1, 2, 3]\nprint(sum(values))\n",
        context_note="Runs in the nightly reconciliation job.",
        question="What does this code print?",
        expected_stdout=expected_stdout,
        choices=[
            Choice(id="a", text=expected_stdout, misconception=None),
            Choice(id="b", text=distractor_text, misconception="miscounted the list length"),
            Choice(id="c", text="1", misconception="stopped after the first element"),
            Choice(id="d", text="0", misconception="believed sum() needs an explicit start of 1"),
        ],
        correct_choice_id="a",
        draft_explanation=TraceDraftExplanation(
            summary="sum() adds 1 + 2 + 3.",
            principle="sum() folds left to right over the iterable.",
            trace_table=[TraceTableEntry(line=2, state="values=[1, 2, 3]")],
            why_wrong=[
                WhyWrong(choice_id="b", note="miscounted the list length"),
                WhyWrong(choice_id="c", note="stopped after the first element"),
                WhyWrong(choice_id="d", note="believed sum() needs an explicit start of 1"),
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


def test_sandbox_gate_accepts_a_good_trace_candidate_and_replaces_choice_with_output() -> None:
    candidate = _trace_candidate(expected_stdout="6")

    result = validate_trace(candidate)

    assert result.accepted, result.as_report()
    assert result.captured_stdout == "6"


def test_sandbox_gate_rejects_trace_candidate_whose_real_output_disagrees_with_claim() -> None:
    candidate = _trace_candidate(expected_stdout="7")  # generator mis-traced its own code

    result = validate_trace(candidate)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["captured_output_matches_claim"].passed is False


def test_sandbox_gate_rejects_nondeterministic_candidate() -> None:
    # Real nondeterminism, not a mock: printing a set's repr depends on the
    # process's (randomized-by-default) hash seed, so two separate sandbox
    # runs of the same code produce different orderings.
    candidate = _trace_candidate(
        expected_stdout="irrelevant",
    ).model_copy(update={"code": "print({str(i) for i in range(30)})\n"})

    result = validate_trace(candidate)

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["deterministic_double_run"].passed is False


# --- D-80: predict_the_fix gate -- every distractor must STILL FAIL the test ---

_PTF_BUGGY = (
    "def tier_discount(order_total):\n"
    "    if order_total > 100:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)
_PTF_FIXED = (
    "def tier_discount(order_total):\n"
    "    if order_total >= 100:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)
# The test picks exactly the divergence boundary (order_total == 100).
_PTF_TEST = "assert tier_discount(100) == 0.10\n"

# Three plausible-but-wrong fixes; each still returns something != 0.10 at 100.
_PTF_WRONG_ELSE_VALUE = (
    "def tier_discount(order_total):\n"
    "    if order_total > 100:\n"
    "        return 0.10\n"
    "    return 0.05\n"
)
_PTF_WRONG_BOUNDARY = (
    "def tier_discount(order_total):\n"
    "    if order_total > 101:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)
_PTF_WRONG_DISCOUNT = (
    "def tier_discount(order_total):\n"
    "    if order_total > 100:\n"
    "        return 0.15\n"
    "    return 0.0\n"
)
# A "wrong" fix that actually PASSES the test (100 > 99 -> 0.10): not wrong.
_PTF_ACTUALLY_CORRECT = (
    "def tier_discount(order_total):\n"
    "    if order_total > 99:\n"
    "        return 0.10\n"
    "    return 0.0\n"
)


def test_validate_predict_the_fix_accepts_distractors_that_all_still_fail() -> None:
    result = validate_predict_the_fix(
        buggy_code=_PTF_BUGGY,
        fixed_code=_PTF_FIXED,
        test_code=_PTF_TEST,
        wrong_fixes=[_PTF_WRONG_ELSE_VALUE, _PTF_WRONG_BOUNDARY, _PTF_WRONG_DISCOUNT],
    )

    assert result.accepted, result.as_report()
    passed = {c.name for c in result.checks if c.passed}
    assert "correct_fix_passes_test" in passed
    assert "buggy_fails_test" in passed
    assert "distractors_distinct" in passed
    # captured failing-test output is handed back for the payload.
    assert result.captured_test_output is not None
    assert "AssertionError" in result.captured_test_output


def test_validate_predict_the_fix_rejects_a_distractor_that_passes_the_test() -> None:
    # The new invariant: a distractor that makes the test PASS is a second
    # correct answer, so the whole candidate is rejected.
    result = validate_predict_the_fix(
        buggy_code=_PTF_BUGGY,
        fixed_code=_PTF_FIXED,
        test_code=_PTF_TEST,
        wrong_fixes=[_PTF_WRONG_ELSE_VALUE, _PTF_ACTUALLY_CORRECT, _PTF_WRONG_DISCOUNT],
    )

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    # the actually-correct variant is at index 1
    assert checks_by_name["distractor_1_still_fails_test"].passed is False
    assert result.captured_test_output is None


def test_validate_predict_the_fix_rejects_distractor_equal_to_buggy_or_fixed() -> None:
    # A distractor identical to buggy_code still fails the test, but it is the
    # unchanged original, not a real alternative -> distinctness rejects it.
    result = validate_predict_the_fix(
        buggy_code=_PTF_BUGGY,
        fixed_code=_PTF_FIXED,
        test_code=_PTF_TEST,
        wrong_fixes=[_PTF_WRONG_ELSE_VALUE, _PTF_BUGGY, _PTF_WRONG_DISCOUNT],
    )

    assert not result.accepted
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["distractors_distinct"].passed is False


def test_sandbox_has_no_database_or_secret_env_vars() -> None:
    code = (
        "import os\n"
        "for k in ['DATABASE_URL', 'REDIS_URL', 'TOKEN_ENC_KEY', 'JWT_SECRET']:\n"
        "    print(k, repr(os.environ.get(k)))\n"
    )

    result = run_python(code)

    assert result.exit_code == 0
    for secret_var in ("DATABASE_URL", "REDIS_URL", "TOKEN_ENC_KEY", "JWT_SECRET"):
        assert f"{secret_var} None" in result.stdout, result.stdout


def test_sandbox_network_socket_attempt_fails_closed() -> None:
    code = (
        "import socket\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(2)\n"
        "try:\n"
        "    s.connect(('8.8.8.8', 53))\n"
        "    print('CONNECTED')\n"
        "except OSError as e:\n"
        "    print('FAILED_CLOSED', type(e).__name__)\n"
    )

    result = run_python(code)

    assert result.exit_code == 0
    assert "FAILED_CLOSED" in result.stdout
    assert "CONNECTED" not in result.stdout


# --- D-57 regression: the sandbox must actually execute code, not silently
# reject every candidate. Before the fix, a bind-mount delivery path made
# every real run produce exit_code != 0 and captured_stdout == "" whenever
# the caller's temp path was not host-visible to the Docker daemon -- a code
# delivery failure indistinguishable, from the gate's point of view, from a
# real candidate rejection. This is the trivial `print("ok")` proof the old
# code path could never pass in that setup.


def test_sandbox_run_python_actually_executes_and_returns_nonempty_stdout() -> None:
    result = run_python('print("ok")\n')

    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"
    assert result.stdout != ""


def test_verify_sandbox_available_passes_against_the_real_docker_sandbox() -> None:
    verify_sandbox_available(force=True)


def test_verify_sandbox_available_raises_loud_when_delivery_is_broken(monkeypatch) -> None:
    # Simulates exactly the bug this canary exists to catch: the delivery
    # mechanism runs but never reaches the interpreter, so stdout comes back
    # empty instead of the canary token. Must raise, never silently pass.
    def _broken(code: str, timeout_s: float) -> SandboxResult:  # noqa: ARG001
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr="can't find '__main__' module",
            timed_out=False,
        )

    monkeypatch.setattr(runner, "_run_container", _broken)

    with pytest.raises(SandboxUnavailableError, match="canary check failed"):
        verify_sandbox_available(force=True)
