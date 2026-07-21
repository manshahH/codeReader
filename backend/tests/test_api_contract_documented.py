"""Every field on the session response models must appear in docs/05 (the D-144
review). CLAUDE.md calls docs/05 "the API, exactly", and two field changes
reached the wire with docs/05 unmentioned until asked (`is_fallback`, then
`first_completed_session`). This is the cheap guard that would have caught both.

Crude substring matching on purpose: it UNDER-catches (a generic field name that
coincidentally appears elsewhere in the doc passes), but it NEVER false-fails.
That is the correct failure direction for a guard -- a check that cries wolf gets
disabled. Scoped to the session response models, where both misses happened;
generalising to every response model needs a curated allowlist of intentionally
undocumented fields and is more maintenance than the problem warrants today.
"""

from pathlib import Path

from app.schemas.session import (
    SessionExercise,
    SessionExercisePayload,
    SessionResponse,
    TomorrowTeaser,
)

_DOCS_05 = Path(__file__).resolve().parents[2] / "docs" / "05-api-contract.md"

# SessionResponse and its nested models (GET /session/today).
_SESSION_MODELS = (SessionResponse, TomorrowTeaser, SessionExercise, SessionExercisePayload)


def _field_names(models) -> set[str]:
    names: set[str] = set()
    for model in models:
        names |= set(model.model_fields)
    return names


def test_session_response_fields_are_documented_in_docs_05() -> None:
    doc = _DOCS_05.read_text(encoding="utf-8")
    missing = sorted(f for f in _field_names(_SESSION_MODELS) if f not in doc)
    assert not missing, f"session response fields absent from docs/05-api-contract.md: {missing}"


def test_the_check_actually_rejects_an_undocumented_field() -> None:
    """Negative (house rule): prove the guard is not vacuous. A field name
    deliberately absent from docs/05 must be reported missing by the exact same
    substring logic the positive test uses -- otherwise the check would pass
    against any doc that happened to contain the real field names."""
    doc = _DOCS_05.read_text(encoding="utf-8")
    sentinel = "totally_undocumented_field_xyzzy"
    assert sentinel not in doc, "precondition: the sentinel must genuinely be absent from docs/05"

    fields = _field_names(_SESSION_MODELS) | {sentinel}
    missing = sorted(f for f in fields if f not in doc)
    assert sentinel in missing, "the documentation check failed to flag a field that is absent"
