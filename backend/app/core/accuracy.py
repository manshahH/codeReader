"""Internal storage shape for user_stats.accuracy_by_type.

The DB column stores {"<type>": {"attempts": int, "correct": int}, ...} so a
running accuracy can be recomputed on every write without aggregating
attempts (invariant: nothing user-facing aggregates attempts at request
time). docs/05's GET /me/stats response projects this down to
{"<type>": <float 0..1>, ...} at read time via `project()`.
"""

from __future__ import annotations


def bump(accuracy_by_type: dict | None, exercise_type: str, is_correct: bool) -> dict:
    updated = dict(accuracy_by_type or {})
    counts = dict(updated.get(exercise_type) or {"attempts": 0, "correct": 0})
    counts["attempts"] += 1
    if is_correct:
        counts["correct"] += 1
    updated[exercise_type] = counts
    return updated


def project(accuracy_by_type: dict | None) -> dict[str, float]:
    result: dict[str, float] = {}
    for exercise_type, counts in (accuracy_by_type or {}).items():
        attempts = counts.get("attempts", 0)
        correct = counts.get("correct", 0)
        result[exercise_type] = round(correct / attempts, 4) if attempts else 0.0
    return result
