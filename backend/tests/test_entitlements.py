"""The entitlement gate and the export-precondition guard (D-145 (a), (b), (e)).

These are DB-free: resolve_plan is pure and returns a constant, so the gate can
be exercised by monkeypatching the map alone. That is the point of the design
(D-145(b)): a feature's fate lives in PLAN_FEATURES and nowhere in its own code.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.entitlements import (
    EXPORT_OF,
    PLAN_FEATURES,
    Feature,
    Plan,
    is_entitled,
    require_entitled,
    resolve_plan,
)
from app.core.errors import ApiError
from app.models import User


def _a_user() -> User:
    # resolve_plan ignores the row today; a bare instance is enough and keeps
    # these unit tests off the database.
    return User(id=uuid.uuid4(), username="entitlement-test")


# --- decision (2): everything is free today -------------------------------


def test_everything_is_free_today() -> None:
    """The whole registry is in the free set, so the gate answers yes for every
    feature and decision (2) holds with no special-casing (D-145(b))."""
    user = _a_user()
    assert resolve_plan(user) is Plan.FREE
    for feature in Feature:
        assert is_entitled(user, feature) is True
        require_entitled(user, feature)  # must not raise


# --- (a): the gate refuses, positive + negative ---------------------------


def test_require_entitled_refuses_with_403_feature_not_entitled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative (house rule): prove the gate actually refuses. With a feature
    removed from the free set, require_entitled raises exactly the 403 the API
    surface promises, and is_entitled reports False."""
    patched = {Plan.FREE: frozenset(PLAN_FEATURES[Plan.FREE] - {Feature.CHEAT_SHEET})}
    monkeypatch.setattr("app.core.entitlements.PLAN_FEATURES", patched)

    user = _a_user()
    assert is_entitled(user, Feature.CHEAT_SHEET) is False
    with pytest.raises(ApiError) as caught:
        require_entitled(user, Feature.CHEAT_SHEET)
    assert caught.value.status_code == 403
    assert caught.value.code == "feature_not_entitled"


# --- (b) the design property: the MAP alone flips behaviour ----------------


def test_map_change_alone_flips_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The architectural constraint of D-145(b) as an executable check: nothing
    but PLAN_FEATURES changes, and the gate's answer flips. No feature module is
    touched, so this cannot pass if paid knowledge lived anywhere but the map.

    (The per-feature `test_<feature>_map_change_alone_flips_it` required at flip
    time asserts the same property end-to-end over the real HTTP route; this is
    its unit-level twin, provable before any feature is gated.)"""
    user = _a_user()
    assert is_entitled(user, Feature.CHEAT_SHEET) is True  # free before

    monkeypatch.setattr(
        "app.core.entitlements.PLAN_FEATURES",
        {Plan.FREE: frozenset(PLAN_FEATURES[Plan.FREE] - {Feature.CHEAT_SHEET})},
    )
    assert is_entitled(user, Feature.CHEAT_SHEET) is False  # gated after


# --- (e): export is a precondition, mechanized -----------------------------


def export_guard_violations(
    plan_features: dict[Plan, frozenset[Feature]],
    export_of: dict[Feature, Feature],
) -> list[str]:
    """Pure guard, so both the live check and its negative call the same logic.

    A feature is 'gated' if it is absent from the free set. Every gated feature
    must (1) have an export key in export_of and (2) that export key must itself
    be in the free set -- otherwise a flip stranded a user's work behind the very
    tier it just moved out of reach (D-145(e))."""
    free = plan_features[Plan.FREE]
    violations: list[str] = []
    for feature in Feature:
        if feature in free:
            continue  # still free: nothing to export yet
        export = export_of.get(feature)
        if export is None:
            violations.append(f"{feature.value}: gated but has no export key")
        elif export not in free:
            violations.append(f"{feature.value}: export {export.value} is not free")
    return violations


def test_export_of_is_well_formed() -> None:
    """EXPORT_OF integrity, independent of any flip: keys and values are real
    Feature members and each export target is free today."""
    free = PLAN_FEATURES[Plan.FREE]
    for feature, export in EXPORT_OF.items():
        assert isinstance(feature, Feature)
        assert isinstance(export, Feature)
        assert export in free


def test_no_gated_feature_ships_without_a_free_export() -> None:
    """The live guard over the REAL config. Vacuous today (nothing is gated),
    and that is fine -- it becomes load-bearing the moment a feature flips."""
    assert export_guard_violations(PLAN_FEATURES, EXPORT_OF) == []


def test_export_guard_catches_a_flip_that_forgot_export() -> None:
    """Negative (house rule): a feature moved out of the free set with no export
    key must be reported. Proves the guard is not vacuous."""
    bad_plan = {Plan.FREE: frozenset(PLAN_FEATURES[Plan.FREE] - {Feature.CHEAT_SHEET})}
    violations = export_guard_violations(bad_plan, {})
    assert any("cheat_sheet" in v for v in violations)

    # And an export key that is itself gated is also caught.
    bad_export = {Feature.CHEAT_SHEET: Feature.CHEAT_SHEET_EXPORT}
    bad_plan_2 = {
        Plan.FREE: frozenset(
            PLAN_FEATURES[Plan.FREE]
            - {Feature.CHEAT_SHEET, Feature.CHEAT_SHEET_EXPORT}
        )
    }
    violations_2 = export_guard_violations(bad_plan_2, bad_export)
    assert any("export cheat_sheet_export is not free" in v for v in violations_2)
