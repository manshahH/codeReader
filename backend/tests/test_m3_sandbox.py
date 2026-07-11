from __future__ import annotations

import pytest
from pipeline.sandbox import runner
from pipeline.sandbox.runner import (
    SandboxResult,
    SandboxUnavailableError,
    run_python,
    verify_sandbox_available,
)
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
