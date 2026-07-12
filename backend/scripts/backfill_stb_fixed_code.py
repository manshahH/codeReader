"""One-time backfill: `grading.artifacts.fixed_code` for hand-authored
spot_the_bug rows (D-90).

`pipeline/publish.py`'s `_stb_grading` used to store only `fixed_code_hash` --
a sha256 digest of the execution-verified fix, never the fix itself. The
digest cannot be inverted, so every `spot_the_bug` row published before the
D-90 fix is missing `fixed_code` in the database. For the `origin="llm"` rows
that text is gone forever (never persisted anywhere else); for
`origin="handauthored_claude"` rows it still exists on disk, in the
`pipeline/handauthored_stb_batch{1,2,3,4}.json` files ingest.py originally read
from -- this script recovers it from there, ONE TIME, and stops being useful
the moment every row already has fixed_code (idempotent: rows that already
carry it are skipped).

Join key: `pipeline.dedup.content_hash(buggy_code)` -- the SAME AST-normalized
hash `orchestrator._evaluate_candidate` computes and stores as
`source.content_hash` on every published row (both LLM and hand-authored
paths run through the same `_evaluate_candidate`). Matching on this instead of
raw buggy_code text is exact and collision-resistant by construction; it is
not a guess.

Usage: python backend/scripts/backfill_stb_fixed_code.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
_REPO_ROOT = _BACKEND_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.dedup import content_hash  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import create_engine, create_session_factory  # noqa: E402
from app.exercises.service import update_exercise_fields  # noqa: E402
from app.models import Exercise  # noqa: E402

BATCH_FILES = [
    _REPO_ROOT / "pipeline" / f"handauthored_stb_batch{n}.json" for n in (1, 2, 3, 4)
]


def _load_fixed_code_by_hash() -> tuple[dict[str, str], list[str]]:
    """hash(buggy_code) -> fixed_code across every batch file, plus a list of
    any hash collision encountered (same hash, different fixed_code) --
    ambiguous, so those are excluded from the map and reported, never guessed.
    """
    by_hash: dict[str, str] = {}
    collisions: list[str] = []
    for path in BATCH_FILES:
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            candidate = item["candidate"]
            digest = content_hash(candidate["buggy_code"])
            fixed = candidate["fixed_code"]
            if digest in by_hash and by_hash[digest] != fixed:
                collisions.append(digest)
                continue
            by_hash[digest] = fixed
    for digest in collisions:
        by_hash.pop(digest, None)
    return by_hash, collisions


async def run(*, dry_run: bool) -> None:
    by_hash, collisions = _load_fixed_code_by_hash()

    engine = create_engine()
    session_factory = create_session_factory(engine)
    backfilled: list[str] = []
    already_had: list[str] = []
    unmatched: list[str] = []

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(Exercise).where(
                    Exercise.type == "spot_the_bug",
                    Exercise.source["origin"].astext == "handauthored_claude",
                ),
            )
        ).all()

        for row in rows:
            label = f"{row.id} v{row.version} concept={row.concepts}"
            artifacts = row.grading.get("artifacts", {}) if isinstance(row.grading, dict) else {}
            if artifacts.get("fixed_code"):
                already_had.append(label)
                continue

            digest = row.source.get("content_hash") if isinstance(row.source, dict) else None
            fixed_code = by_hash.get(digest) if digest else None
            if fixed_code is None:
                unmatched.append(f"{label} content_hash={digest}")
                continue

            if not dry_run:
                new_grading = dict(row.grading)
                new_artifacts = dict(new_grading.get("artifacts", {}))
                new_artifacts["fixed_code"] = fixed_code
                new_grading["artifacts"] = new_artifacts
                await update_exercise_fields(
                    session, row.id, row.version, {"grading": new_grading},
                )
            backfilled.append(label)

        if not dry_run:
            await session.commit()
    await engine.dispose()

    print(f"backfill_stb_fixed_code: batch files provided {len(by_hash)} fixed_code entries "
          f"({len(collisions)} hash collision(s) excluded: {collisions})")
    print(f"backfill_stb_fixed_code: {len(rows)} handauthored_claude spot_the_bug rows examined")
    dry_run_note = " (dry-run, no commit)" if dry_run else ""
    print(f"backfill_stb_fixed_code: backfilled {len(backfilled)}{dry_run_note}")
    for label in backfilled:
        print(f"  OK      {label}")
    print(f"backfill_stb_fixed_code: already had fixed_code: {len(already_had)}")
    print(f"backfill_stb_fixed_code: could NOT match: {len(unmatched)}")
    for label in unmatched:
        print(f"  MISSING {label}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python backend/scripts/backfill_stb_fixed_code.py")
    parser.add_argument(
        "--dry-run", action="store_true", help="report matches without writing to the database",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
