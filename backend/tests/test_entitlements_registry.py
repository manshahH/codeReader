"""The house rule "every gate gets a negative test" mechanized (D-145(d)).

For every feature that is NOT free -- i.e. one that has actually been gated --
this introspects the collected test suite and asserts that a test function
matching each mandatory name pattern EXISTS. A feature that is still free has
nothing to prove and is exempt, which is why this passes today with an empty
loop body (everything is free, decision 2).

CI already runs `pytest backend/tests`, so this pytest test IS the CI check; no
workflow change.

Deliberately crude name matching, matching the house style of
test_api_contract_documented.py: it UNDER-catches and NEVER false-fails, which
is the correct failure direction for a guard, because a check that cries wolf
gets disabled.

HONEST LIMITATION (D-145(d)): name matching proves a test EXISTS, not that it
asserts anything. It mechanizes the checklist; it does not replace review.
"""

from __future__ import annotations

from pathlib import Path

from app.core.entitlements import PLAN_FEATURES, Feature, Plan

_TESTS_DIR = Path(__file__).resolve().parent


def _required_test_names(feature: str) -> tuple[str, ...]:
    """The three mandatory names per gated feature (D-145(d))."""
    return (
        f"test_{feature}_entitled_user_gets_the_data",
        f"test_{feature}_unentitled_user_is_refused_by_the_api",
        f"test_{feature}_map_change_alone_flips_it",
    )


def _gated_feature_values() -> list[str]:
    """Registry keys that are NOT in the free set -- the ones that must prove
    their gating with tests."""
    free = PLAN_FEATURES[Plan.FREE]
    return [f.value for f in Feature if f not in free]


def _collected_test_source() -> str:
    """All test source concatenated, the substring haystack for the name check.
    Reading the files is enough and mirrors test_api_contract_documented.py's
    read-the-doc-text approach -- no pytest collection introspection needed."""
    parts = [p.read_text(encoding="utf-8") for p in sorted(_TESTS_DIR.glob("test_*.py"))]
    return "\n".join(parts)


def missing_required_tests(gated_features: list[str], test_source: str) -> list[str]:
    """Pure, so the live check and its negative share it. Returns the required
    test names that do not appear as `def <name>` anywhere in the source."""
    missing: list[str] = []
    for feature in gated_features:
        for name in _required_test_names(feature):
            if f"def {name}" not in test_source:
                missing.append(name)
    return missing


def test_every_gated_feature_has_its_three_tests() -> None:
    """Live check over the real registry. Passes trivially while everything is
    free; the moment a feature leaves the free set, its three tests must exist
    or CI fails here."""
    missing = missing_required_tests(_gated_feature_values(), _collected_test_source())
    assert not missing, f"gated features missing mandatory tests: {missing}"


def test_the_check_reports_a_gated_feature_with_no_tests() -> None:
    """Negative (house rule): inject a sentinel gated feature that has no tests
    and assert the check reports all three missing names. Proves the guard is
    not vacuous -- exactly the discipline test_api_contract_documented.py uses."""
    sentinel = "sentinel_gated_feature_xyzzy"
    source = _collected_test_source()
    assert f"def test_{sentinel}_" not in source, "precondition: sentinel must be genuinely absent"

    missing = missing_required_tests([sentinel], source)
    assert set(missing) == set(_required_test_names(sentinel))
