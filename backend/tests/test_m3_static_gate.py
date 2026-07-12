from __future__ import annotations

from pipeline.static_gate import check


def test_static_gate_accepts_clean_code() -> None:
    code = (
        "def apply_discount(prices, discount_pct):\n"
        "    updated = dict(prices)\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n"
    )

    result = check(code, line_budget=(1, 20))

    assert result.accepted, result.violations


def test_static_gate_rejects_forbidden_import() -> None:
    code = "import random\n\ndef pick():\n    return random.choice([1, 2, 3])\n"

    result = check(code, line_budget=(1, 20))

    assert not result.accepted
    assert any("forbidden import" in v for v in result.violations)


def test_static_gate_rejects_hinting_comment() -> None:
    code = (
        "def apply_discount(prices, discount_pct):\n"
        "    # careful: this mutates the input\n"
        "    updated = prices\n"
        "    return updated\n"
    )

    result = check(code, line_budget=(1, 20))

    assert not result.accepted
    assert any("hinting word" in v for v in result.violations)


def test_static_gate_rejects_hinting_identifier() -> None:
    code = "def compute():\n    buggy_total = 1 + 1\n    return buggy_total\n"

    result = check(code, line_budget=(1, 20))

    assert not result.accepted
    assert any("hinting name" in v for v in result.violations)


def test_static_gate_does_not_flag_innocuous_substrings() -> None:
    # "prefix"/"suffix"/"notebook" contain "fix"/"note" as substrings but are
    # not hints; whole-part matching must not flag them.
    code = (
        "def format_entry(prefix, suffix, notebook_id):\n"
        "    return f'{prefix}-{notebook_id}-{suffix}'\n"
    )

    result = check(code, line_budget=(1, 20))

    assert result.accepted, result.violations


def test_static_gate_rejects_set_usage() -> None:
    code = "def unique_skus(items):\n    return {item.sku for item in items}\n"

    result = check(code, line_budget=(1, 20))

    assert not result.accepted
    assert any("set literal" in v for v in result.violations)


def test_static_gate_rejects_line_budget_violation() -> None:
    code = "x = 1\n" * 25

    result = check(code, line_budget=(1, 10))

    assert not result.accepted
    assert any("line_count" in v for v in result.violations)


# --- D-80: max-only budget (None low bound) drops the minimum ---------------


def test_static_gate_max_only_budget_accepts_code_under_the_old_minimum() -> None:
    # 5-line buggy snippet against a budget whose min used to be 10: the
    # min was the cause of nearly every real budget reject (a minimal clear
    # bug is naturally short), so max-only must accept it.
    code = "x = 1\n" * 5

    result = check(code, line_budget=(None, 20))

    assert result.accepted, result.violations


def test_static_gate_max_only_budget_still_rejects_over_the_maximum() -> None:
    code = "x = 1\n" * 25

    result = check(code, line_budget=(None, 20))

    assert not result.accepted
    assert any("line_count" in v for v in result.violations)


def test_orchestrator_static_check_uses_max_only_for_short_buggy_code() -> None:
    # A 3-line bug against a sampled budget of (10, 20): under the old min,
    # rejected; max-only, accepted. This is FIX 2b's exact false-reject class.
    from pipeline.orchestrator import _static_gate_check

    buggy = "def f(items):\n    total = 0\n    return total\n"
    candidate = _stb_candidate_for_budget(buggy, buggy)  # has_bug shape irrelevant here
    candidate = candidate.model_copy(update={"bug_lines": []})

    ok, violations = _static_gate_check(candidate, _spec_with_budget(10, 20))

    assert ok, violations


# --- D-51: line_budget=None skips ONLY the length check ---------------------


def test_static_gate_budget_none_skips_the_length_check() -> None:
    code = "x = 1\n" * 25

    result = check(code, line_budget=None)

    assert result.accepted, result.violations


def test_static_gate_budget_none_still_rejects_forbidden_import() -> None:
    code = "import random\n" + "x = 1\n" * 25

    result = check(code, line_budget=None)

    assert not result.accepted
    assert any("forbidden import" in v for v in result.violations)


# --- D-51: orchestrator applies the budget to buggy_code only ---------------


def _stb_candidate_for_budget(buggy_code: str, fixed_code: str):
    from pipeline.schemas import (
        LineNote,
        ReasonOption,
        STBCandidate,
        STBDraftExplanation,
        STBSelfCheck,
    )

    return STBCandidate(
        buggy_code=buggy_code,
        fixed_code=fixed_code,
        bug_lines=[1],
        test_code="assert True\n",
        context_note="note.",
        reason_options=[
            ReasonOption(id="a", text="w"),
            ReasonOption(id="b", text="x"),
            ReasonOption(id="c", text="y"),
            ReasonOption(id="d", text="z"),
        ],
        correct_reason_id="a",
        draft_explanation=STBDraftExplanation(
            summary="s",
            principle="p",
            line_notes=[LineNote(line=1, note="n")],
        ),
        concepts=["off-by-one"],
        self_difficulty=2,
        self_check=STBSelfCheck(
            single_bug_confirmed=True,
            runs_without_error_on_happy_path=True,
            no_hinting_names_or_comments=True,
            distractors_verifiably_wrong=True,
        ),
    )


def _spec_with_budget(lo: int, hi: int):
    from pipeline.spec_sampler import ExerciseSpec

    return ExerciseSpec(
        type="spot_the_bug",
        concept="off-by-one",
        difficulty=2,
        domain="checkout service",
        line_budget_min=lo,
        line_budget_max=hi,
        has_bug=True,
        avoid_patterns=(),
    )


def test_orchestrator_static_check_accepts_fixed_code_over_the_budget() -> None:
    # buggy_code sits at the budget max; the fix inserts lines (invited by
    # D-46) and overflows it. The budget constrains what the user READS, so
    # this must pass (D-51).
    from pipeline.orchestrator import _static_gate_check

    buggy = "def f(items):\n    total = 0\n    return total\n"  # 3 lines, at max
    fixed = (
        "def f(items):\n    total = 0\n    total += len(items)\n"
        "    total += 1\n    return total\n"
    )
    candidate = _stb_candidate_for_budget(buggy, fixed)

    ok, violations = _static_gate_check(candidate, _spec_with_budget(1, 3))

    assert ok, violations


def test_orchestrator_static_check_still_rejects_forbidden_import_in_fixed_code() -> None:
    from pipeline.orchestrator import _static_gate_check

    buggy = "def f(items):\n    total = 0\n    return total\n"
    fixed = "import random\ndef f(items):\n    total = 0\n    return total\n"
    candidate = _stb_candidate_for_budget(buggy, fixed)

    ok, violations = _static_gate_check(candidate, _spec_with_budget(1, 3))

    assert not ok
    assert any("forbidden import" in v for v in violations)
