"""D-129: the code payload normalizes to a document list at the serialization
boundary, and the stored payload is never touched.

These are pure function tests against _serialize_payload -- no database, no
session build. The point of the boundary is that it is the ONLY place the two
shapes meet, so testing it directly is testing the whole contract.

Every test here fails against the pre-D-129 backend, where SessionExercisePayload
had no `documents` field at all.
"""

import uuid

from app.models import Exercise
from app.sessions.service import _serialize_payload

STB_CODE = "def add_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket"


def _exercise(exercise_type: str, payload: dict) -> Exercise:
    """An in-memory Exercise. _serialize_payload reads `type`, `language` and
    `payload` and nothing else, so this never needs to reach the database."""
    return Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type=exercise_type,
        grading_mode="deterministic",
        difficulty_authored=4,
        concepts=["defaults"],
        tags=[],
        status="live",
        source={"origin": "test"},
        payload=payload,
        grading={},
        explanation={},
        est_time_s=90,
        human_reviewed=True,
    )


def test_legacy_payload_normalizes_to_a_single_primary_document() -> None:
    """The shape all 109 stored payloads are in: a bare `code` string."""
    exercise = _exercise(
        "spot_the_bug",
        {
            "code": STB_CODE,
            "context_note": "Part of a cart service.",
            "answer_mode": "line_select_plus_reason",
            "reason_options": [{"id": "a", "text": "Mutable default argument"}],
        },
    )

    result = _serialize_payload(exercise)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.id == "primary"
    assert document.role == "primary"
    assert document.code == STB_CODE
    assert document.language == "python"
    # `code` stays on the wire beside `documents` (D-129): dropping it would be
    # a client-visible break for a refactor that is meant to have none.
    assert result.code == STB_CODE


def test_serializing_does_not_mutate_the_stored_payload() -> None:
    """Invariant 3: exercises are immutable per (id, version) and a fix bumps
    the version. Normalization happens on the way OUT, so the stored JSONB must
    come back from a serialize exactly as it went in -- no `documents` key
    written into it, nothing rewritten."""
    stored = {
        "code": STB_CODE,
        "context_note": "Part of a cart service.",
        "answer_mode": "line_select_plus_reason",
        "reason_options": [{"id": "a", "text": "Mutable default argument"}],
    }
    before = {**stored, "reason_options": [dict(o) for o in stored["reason_options"]]}
    exercise = _exercise("spot_the_bug", stored)

    _serialize_payload(exercise)

    assert exercise.payload == before
    assert "documents" not in exercise.payload


def test_predict_the_fix_payload_yields_several_documents() -> None:
    """Decision 4 is not speculative: this type already shows the buggy code,
    the failing test, and one block per candidate fix."""
    exercise = _exercise(
        "predict_the_fix",
        {
            "code": "def merge(w):\n    return w",
            "context_note": "Merges overlapping windows.",
            "answer_mode": "choice",
            "question": "Which fix makes the test pass?",
            "failing_test": "assert merge([]) == []",
            "test_output": "IndexError: list index out of range",
            "choices": [
                {"id": "f1", "text": "if not w:\n    return []"},
                {"id": "f2", "text": "return list(w)"},
            ],
        },
    )

    result = _serialize_payload(exercise)

    assert [(d.id, d.role) for d in result.documents] == [
        ("primary", "primary"),
        ("failing_test", "failing_test"),
        ("f1", "choice"),
        ("f2", "choice"),
    ]
    # A choice document's id is the choice id, so a client can line documents
    # up with the answer options it renders.
    by_id = {d.id: d for d in result.documents}
    assert by_id["f1"].code == "if not w:\n    return []"
    assert by_id["failing_test"].code == "assert merge([]) == []"
    assert by_id["failing_test"].label == "Failing test"


def test_a_stored_payload_that_already_has_documents_passes_through() -> None:
    """The boundary NORMALIZES rather than always constructing, so a future
    published version that carries its own documents is not overwritten by a
    reconstruction from `code`."""
    exercise = _exercise(
        "spot_the_bug",
        {
            "code": "ignored_if_documents_present = 1",
            "context_note": "Part of a cart service.",
            "answer_mode": "line_select_plus_reason",
            "reason_options": [],
            "documents": [
                {"id": "primary", "role": "primary", "code": "authored = 1", "language": "python"},
                {"id": "extra", "role": "choice", "code": "authored = 2", "language": "python"},
            ],
        },
    )

    result = _serialize_payload(exercise)

    assert [d.id for d in result.documents] == ["primary", "extra"]
    assert result.documents[0].code == "authored = 1"


def test_trace_payload_has_one_document_and_no_choice_documents() -> None:
    """trace choices are prose answers, not code blocks, so they must NOT
    become documents -- only predict_the_fix's choices are code."""
    exercise = _exercise(
        "trace",
        {
            "code": "x = 1\nprint(x)",
            "context_note": "A tiny script.",
            "question": "What prints?",
            "choices": [{"id": "c1", "text": "1"}, {"id": "c2", "text": "2"}],
        },
    )

    result = _serialize_payload(exercise)

    assert [(d.id, d.role) for d in result.documents] == [("primary", "primary")]
