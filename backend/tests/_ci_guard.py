"""Refuse a vacuous green: a run that reports success but barely ran (D-152).

D-150 showed the pytest job can go RED without running -- container init failed,
so the job failed loudly. The opposite failure is worse: a run that goes GREEN
without running. `pytest` exits 5 (failure) when ZERO tests are collected, so
that path is covered. But if a whole CLASS of tests were silently SKIPPED --
e.g. a pytest-asyncio misconfiguration turning every async test into a skip --
pytest exits 0 and the job passes with almost nothing asserted. The green count
would be a lie, which is exactly the D-103/D-128 decay this project guards
against.

This is the pure decision behind the guard wired in conftest.py. It is opt-in
via an env floor (CODEREADER_MIN_TESTS), set only where the FULL suite runs (CI),
so a developer running a subset locally is never affected.
"""

from __future__ import annotations

MIN_TESTS_ENV = "CODEREADER_MIN_TESTS"


def required_minimum(env: dict[str, str]) -> int | None:
    """The floor of passing tests this run must clear, or None to disable the
    guard (unset, empty, or non-integer -> disabled, because the guard must
    never itself turn a real green red on a bad env value)."""
    raw = env.get(MIN_TESTS_ENV)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def is_vacuous_run(passed: int, minimum: int | None) -> bool:
    """True when a run that reported success actually ran fewer than `minimum`
    tests -- a green that means nothing. `minimum` None disables the check."""
    return minimum is not None and passed < minimum
