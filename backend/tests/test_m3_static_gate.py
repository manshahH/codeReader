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
