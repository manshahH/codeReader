"""One-time migration: re-shuffle already-published `trace` choices in place (C1).

Every published trace exercise keyed its correct answer to id "a" (the
generator prompt pins it, and `_trace_payload` never reshuffled -- unlike
predict_the_fix). Always answering "a" scored 100% on the whole trace corpus
without reading the code. `pipeline/publish.py` now shuffles trace choices at
publish time for NEW rows; this script fixes the EXISTING rows.

It reuses `publish.reassign_shuffled_choice_ids` / `publish._remap_trace_why_wrong`
verbatim -- the SAME shuffle the publish path now uses, never a second
approach. payload.choices order + ids, grading.correct_choice_id, and
explanation.why_wrong ids all move TOGETHER off one shuffle, so the answer key
can never drift apart from the shown options.

SAFETY:
- Idempotent-adjacent: seeded per-row from the exercise id, so a re-run
  produces the same layout; combined with the invariant check below it can
  never silently mis-key a row.
- Text-invariant proof (the load-bearing assertion): for every row, the choice
  whose id == correct_choice_id AFTER the shuffle must have the SAME TEXT as
  the correct choice BEFORE. The whole set of choice texts and the
  text->misconception mapping must also be preserved. A violation aborts the
  row (and, under --apply, the whole run) rather than writing a mis-keyed
  exercise.
- Writes go through `update_exercise_fields`, the D-58 immutability guard.
  in_review rows are updated in place; LIVE rows are REFUSED by the guard
  (invariant 3: live content is immutable, fixes bump version) -- the script
  reports them as blocked and does NOT bypass the guard. Deciding how to fix
  the live rows (version-bump vs. an explicit override) is a separate,
  deliberate step, not this migration's call.
- Existing `attempts` rows are never touched.

Usage:
  python backend/scripts/reshuffle_trace_choices.py            # dry-run, no writes
  python backend/scripts/reshuffle_trace_choices.py --apply    # write in_review rows
  python backend/scripts/reshuffle_trace_choices.py --apply --status in_review
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from collections import Counter
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
_REPO_ROOT = _BACKEND_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.publish import (  # noqa: E402
    _remap_trace_why_wrong,
    fix_and_bump,
    reassign_shuffled_choice_ids,
)
from sqlalchemy import func, select  # noqa: E402

from app.exercises.service import (  # noqa: E402
    ExerciseImmutableError,
    update_exercise_fields,
)
from app.models import Exercise  # noqa: E402


class TextInvariantError(RuntimeError):
    """The correct answer's TEXT would not survive the shuffle -- refuse."""


def _reshuffled(row: Exercise) -> tuple[dict, dict, dict, str, str]:
    """Compute the re-shuffled (payload, grading, explanation) for one trace
    row and PROVE the correct answer's text is preserved. Returns
    (new_payload, new_grading, new_explanation, old_correct_id, new_correct_id).
    """
    payload = dict(row.payload)
    grading = dict(row.grading)
    explanation = dict(row.explanation)

    old_choices = list(payload.get("choices", []))
    old_correct_id = grading.get("correct_choice_id")
    old_correct_text = next(
        (c["text"] for c in old_choices if c["id"] == old_correct_id),
        None,
    )
    if old_correct_text is None:
        raise TextInvariantError(
            f"{row.id}: correct_choice_id {old_correct_id!r} not found among choices",
        )

    entries = [
        {
            "old_id": c["id"],
            "text": c["text"],
            "misconception": c.get("misconception"),
            "is_correct": c["id"] == old_correct_id,
        }
        for c in old_choices
    ]
    # Seeded per-row from the (immutable) exercise id: deterministic and
    # reproducible, so a second run lands the same layout.
    rng = random.Random(f"trace-reshuffle:{row.id}")
    new_choices, new_correct_id, id_remap = reassign_shuffled_choice_ids(entries, rng=rng)

    # --- Load-bearing invariant checks: the answer key must not move away
    # from its text, and no option text may appear or vanish. ---
    new_correct_text = next(c["text"] for c in new_choices if c["id"] == new_correct_id)
    if new_correct_text != old_correct_text:
        raise TextInvariantError(
            f"{row.id}: correct text changed {old_correct_text!r} -> {new_correct_text!r}",
        )
    if Counter(c["text"] for c in old_choices) != Counter(c["text"] for c in new_choices):
        raise TextInvariantError(f"{row.id}: the set of choice texts changed")
    old_map = {c["text"]: c.get("misconception") for c in old_choices}
    new_map = {c["text"]: c.get("misconception") for c in new_choices}
    if old_map != new_map:
        raise TextInvariantError(f"{row.id}: a text->misconception mapping changed")

    new_payload = dict(payload, choices=new_choices)
    new_grading = dict(grading, correct_choice_id=new_correct_id)
    new_explanation = dict(explanation)
    if "why_wrong" in new_explanation:
        new_explanation["why_wrong"] = [dict(w) for w in new_explanation["why_wrong"]]
        _remap_trace_why_wrong(new_explanation, id_remap)
    return new_payload, new_grading, new_explanation, old_correct_id, new_correct_id


async def run(*, apply: bool, status_filter: str | None) -> None:
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    session_factory = create_session_factory(engine)

    before_dist: Counter[str] = Counter()
    after_dist: Counter[str] = Counter()
    updated: list[str] = []
    blocked_live: list[str] = []
    errors: list[str] = []

    async with session_factory() as session:
        query = select(Exercise).where(Exercise.type == "trace").order_by(Exercise.id)
        if status_filter:
            query = query.where(Exercise.status == status_filter)
        rows = (await session.scalars(query)).all()

        print(f"reshuffle_trace_choices: {len(rows)} trace rows"
              f"{f' (status={status_filter})' if status_filter else ''}\n")
        print(f"{'exercise_id':38} {'status':10} {'old':>3} -> {'new':>3}  correct_text")
        print("-" * 100)

        for row in rows:
            try:
                new_payload, new_grading, new_explanation, old_id, new_id = _reshuffled(row)
            except TextInvariantError as exc:
                errors.append(str(exc))
                print(f"  ERROR {exc}")
                if apply:
                    raise
                continue

            before_dist[old_id] += 1
            after_dist[new_id] += 1
            correct_text = next(
                c["text"] for c in new_payload["choices"] if c["id"] == new_id
            )
            preview = correct_text.replace("\n", "\\n")[:40]
            print(f"{str(row.id):38} {row.status:10} {old_id:>3} -> {new_id:>3}  {preview!r}")

            if apply:
                try:
                    await update_exercise_fields(
                        session,
                        row.id,
                        row.version,
                        {
                            "payload": new_payload,
                            "grading": new_grading,
                            "explanation": new_explanation,
                        },
                    )
                    updated.append(str(row.id))
                except ExerciseImmutableError:
                    # invariant 3: live content is immutable. Do NOT bypass the
                    # guard -- report and leave for a deliberate version-bump.
                    blocked_live.append(str(row.id))

        if apply:
            await session.commit()
    await engine.dispose()

    print("\n--- correct_choice_id distribution ---")
    print(f"  before: {dict(sorted(before_dist.items()))}")
    print(f"  after:  {dict(sorted(after_dist.items()))}")
    mode = "APPLIED" if apply else "DRY-RUN (no writes)"
    print(f"\nreshuffle_trace_choices: {mode}")
    print(f"  updated (in_review):        {len(updated)}")
    print(f"  blocked by immutability (live): {len(blocked_live)} -> {blocked_live}")
    print(f"  text-invariant errors:      {len(errors)}")


async def _shippable_distribution(session) -> Counter[str]:
    """correct_choice_id distribution across every trace row that can actually
    ship: in_review (the re-shuffled originals + any bumped v2) plus live. A
    live v1 still keyed to "a" is expected to be PULLED once its v2 is
    approved, so it is reported separately below."""
    rows = (
        await session.scalars(
            select(Exercise).where(
                Exercise.type == "trace",
                Exercise.status.in_(("in_review", "live")),
            ),
        )
    ).all()
    return Counter(r.grading.get("correct_choice_id") for r in rows)


async def run_bump_live(*, apply: bool) -> None:
    """Option 2 (bump + re-review): for each LIVE trace row (immutable,
    invariant 3), create a shuffled in_review v2 via fix_and_bump. v1 is left
    live and untouched -- its existing attempts stay honest against the exact
    version those users answered. The operator approves each v2 and pulls the
    matching v1 deliberately (review_cli), so this script never flips status.
    """
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    session_factory = create_session_factory(engine)
    bumped: list[tuple[str, int, str, str]] = []

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(Exercise)
                .where(Exercise.type == "trace", Exercise.status == "live")
                .order_by(Exercise.id),
            )
        ).all()

        print(f"bump-live: {len(rows)} live trace rows\n")
        header = f"{'exercise_id':38} v1->v2 {'old':>3}->{'new':>3}  correct_text (v1==v2 proof)"
        print(header)
        print("-" * 100)

        for row in rows:
            new_payload, new_grading, new_explanation, old_id, new_id = _reshuffled(row)
            new_version = row.version + 1
            correct_text = next(c["text"] for c in new_payload["choices"] if c["id"] == new_id)
            preview = correct_text.replace("\n", "\\n")[:40]
            print(f"{str(row.id):38} v{row.version}->v{new_version} {old_id:>3} -> "
                  f"{new_id:>3}  {preview!r}")

            if apply:
                v2 = await fix_and_bump(
                    session,
                    row.id,
                    row.version,
                    {
                        "payload": new_payload,
                        "grading": new_grading,
                        "explanation": new_explanation,
                    },
                )
                assert v2.status == "in_review"
                assert v2.version == new_version
                # Re-prove the key survived the round-trip through the DB write.
                v2_correct = v2.grading["correct_choice_id"]
                v2_text = next(c["text"] for c in v2.payload["choices"] if c["id"] == v2_correct)
                if v2_text != correct_text:
                    raise TextInvariantError(
                        f"{row.id} v2: correct text drifted after write {correct_text!r}",
                    )
                bumped.append((str(row.id), new_version, old_id, new_id))

        if apply:
            await session.commit()

        dist = await _shippable_distribution(session) if apply else Counter()
        live_still_a = 0
        if apply:
            live_still_a = await session.scalar(
                select(func.count())
                .select_from(Exercise)
                .where(
                    Exercise.type == "trace",
                    Exercise.status == "live",
                    Exercise.grading["correct_choice_id"].astext == "a",
                ),
            )
    await engine.dispose()

    mode = "APPLIED" if apply else "DRY-RUN (no writes)"
    print(f"\nbump-live: {mode}")
    if apply:
        print("\n--- v2 exercise ids to APPROVE (each pairs with a v1 to PULL) ---")
        for ex_id, v2_version, old_id, new_id in bumped:
            print(f"  approve {ex_id} v{v2_version}   (was {old_id!r} -> now {new_id!r}); "
                  f"then pull {ex_id} v{v2_version - 1}")
        print("\n--- correct_choice_id distribution across shippable trace rows "
              "(in_review + live) ---")
        print(f"  {dict(sorted(dist.items()))}")
        print(f"  (of which live v1 still keyed 'a', pending pull: {live_still_a})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python backend/scripts/reshuffle_trace_choices.py")
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument(
        "--status",
        default=None,
        help="only rows with this status (e.g. in_review); default: all trace rows",
    )
    parser.add_argument(
        "--bump-live",
        action="store_true",
        help="Option 2: fix_and_bump each LIVE trace row to a shuffled in_review v2 "
        "(v1 left live for a deliberate pull after v2 is approved).",
    )
    args = parser.parse_args()
    if args.bump_live:
        asyncio.run(run_bump_live(apply=args.apply))
    else:
        asyncio.run(run(apply=args.apply, status_filter=args.status))


if __name__ == "__main__":
    main()
