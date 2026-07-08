from __future__ import annotations

from pipeline.sandbox.runner import run_python
from pipeline.sandbox_gate import validate_spot_the_bug, validate_trace
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
        "bug_lines_match_diff",
    }


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
