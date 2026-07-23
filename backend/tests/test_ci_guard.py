"""The vacuous-green guard's decision logic (D-152).

The wiring (counting passed tests, setting session.exitstatus) lives in
conftest; here we pin the pure decision so a bad env value can never itself turn
a real green red, and a genuinely-empty run can never pass."""

from __future__ import annotations

from _ci_guard import is_vacuous_run, required_minimum


def test_required_minimum_parses_a_set_floor() -> None:
    assert required_minimum({"CODEREADER_MIN_TESTS": "600"}) == 600


def test_required_minimum_is_none_when_unset_or_unusable() -> None:
    # Unset, empty, and non-integer all DISABLE the guard rather than failing --
    # the guard must never itself break a run over a bad env value.
    assert required_minimum({}) is None
    assert required_minimum({"CODEREADER_MIN_TESTS": ""}) is None
    assert required_minimum({"CODEREADER_MIN_TESTS": "lots"}) is None


def test_guard_fires_only_when_too_few_tests_passed() -> None:
    # Negative (house rule): below the floor is vacuous and must be caught.
    assert is_vacuous_run(passed=3, minimum=600) is True
    assert is_vacuous_run(passed=0, minimum=600) is True


def test_guard_is_silent_on_a_real_run() -> None:
    assert is_vacuous_run(passed=649, minimum=600) is False
    assert is_vacuous_run(passed=600, minimum=600) is False  # exactly the floor is fine


def test_guard_disabled_when_no_floor_set() -> None:
    # A local subset run (no floor) must never be failed by the guard.
    assert is_vacuous_run(passed=1, minimum=None) is False
