"""Human review CLI: list / show / approve / kill / fix / pull.

Budget 60-90s per exercise (docs/01): review means verifying the receipts in
the validation report, not re-deriving the answer from scratch.

The `cmd_*` functions take an injected AsyncSession so they are testable
against the same shared fixture the rest of M3 uses; `main()` is the thin CLI
wrapper that owns the real engine/session and commits.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine, create_session_factory
from app.models import Exercise
from pipeline.publish import approve, fix_and_bump, kill, pull


async def cmd_list(session: AsyncSession, *, limit: int = 50) -> list[Exercise]:
    result = await session.scalars(
        select(Exercise)
        .where(Exercise.status == "in_review")
        .order_by(Exercise.created_at)
        .limit(limit),
    )
    return list(result.all())


async def cmd_show(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise | None:
    return await session.get(Exercise, (exercise_id, version))


async def cmd_approve(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    return await approve(session, exercise_id, version)


async def cmd_kill(session: AsyncSession, exercise_id: uuid.UUID, version: int) -> Exercise:
    return await kill(session, exercise_id, version)


async def cmd_pull(
    session: AsyncSession,
    redis,
    exercise_id: uuid.UUID,
    version: int,
) -> tuple[Exercise, int]:
    return await pull(session, redis, exercise_id, version)


async def cmd_fix(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    version: int,
    overrides: dict[str, Any],
) -> Exercise:
    return await fix_and_bump(session, exercise_id, version, overrides)


def print_list(exercises: list[Exercise]) -> None:
    for row in exercises:
        print(
            f"{row.id} v{row.version}  {row.type:<13} "
            f"difficulty={row.difficulty_authored} concepts={row.concepts} "
            f"created_at={row.created_at.isoformat()}",
        )


def print_show(exercise: Exercise | None) -> None:
    if exercise is None:
        print("not found")
        return
    print(
        f"id={exercise.id} version={exercise.version}"
        f" type={exercise.type} status={exercise.status}",
    )
    print(f"concepts={exercise.concepts} difficulty={exercise.difficulty_authored}")
    print("--- payload (what the client sees) ---")
    print(json.dumps(exercise.payload, indent=2))
    print("--- grading (answer key; never leaves the server pre-answer) ---")
    print(json.dumps(exercise.grading, indent=2))
    print("--- explanation ---")
    print(json.dumps(exercise.explanation, indent=2))
    print(f"--- validation report: {exercise.validation_report_url} ---")
    if exercise.validation_report_url and Path(exercise.validation_report_url).exists():
        print(Path(exercise.validation_report_url).read_text(encoding="utf-8"))


async def _run(coro) -> Any:  # noqa: ANN401
    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        try:
            result = await coro(session)
            await session.commit()
            return result
        finally:
            await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline.review_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="list in_review candidates")
    list_parser.add_argument("--limit", type=int, default=50)

    show_parser = sub.add_parser("show", help="show a candidate + validation receipts")
    show_parser.add_argument("exercise_id", type=uuid.UUID)
    show_parser.add_argument("version", type=int)

    approve_parser = sub.add_parser("approve", help="approve a candidate -> live")
    approve_parser.add_argument("exercise_id", type=uuid.UUID)
    approve_parser.add_argument("version", type=int)

    kill_parser = sub.add_parser("kill", help="kill a candidate -> retired")
    kill_parser.add_argument("exercise_id", type=uuid.UUID)
    kill_parser.add_argument("version", type=int)

    pull_parser = sub.add_parser(
        "pull",
        help="incident: pull a LIVE exercise -> pulled, purging cached sessions",
    )
    pull_parser.add_argument("exercise_id", type=uuid.UUID)
    pull_parser.add_argument("version", type=int)

    fix_parser = sub.add_parser("fix", help="fix-and-bump: create version+1 with overrides")
    fix_parser.add_argument("exercise_id", type=uuid.UUID)
    fix_parser.add_argument("version", type=int)
    fix_parser.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="key=json_value",
        help="override a field on the bumped version, repeatable",
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        exercises = asyncio.run(_run(lambda session: cmd_list(session, limit=args.limit)))
        print_list(exercises)
    elif args.command == "show":
        exercise = asyncio.run(
            _run(lambda session: cmd_show(session, args.exercise_id, args.version)),
        )
        print_show(exercise)
    elif args.command == "approve":
        exercise = asyncio.run(
            _run(lambda session: cmd_approve(session, args.exercise_id, args.version)),
        )
        print(f"approved: {exercise.id} v{exercise.version} -> live")
    elif args.command == "kill":
        exercise = asyncio.run(
            _run(lambda session: cmd_kill(session, args.exercise_id, args.version)),
        )
        print(f"killed: {exercise.id} v{exercise.version} -> retired")
    elif args.command == "pull":

        async def _pull_with_redis(session: AsyncSession) -> tuple[Exercise, int]:
            from redis.asyncio import Redis

            from app.config import get_settings

            redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
            try:
                return await cmd_pull(session, redis, args.exercise_id, args.version)
            finally:
                await redis.aclose()

        exercise, purged = asyncio.run(_run(_pull_with_redis))
        print(
            f"pulled: {exercise.id} v{exercise.version} -> pulled;"
            f" purged {purged} cached session(s)",
        )
    elif args.command == "fix":
        overrides = {
            key: json.loads(value) for key, _, value in (f.partition("=") for f in args.field)
        }
        bumped = asyncio.run(
            _run(lambda session: cmd_fix(session, args.exercise_id, args.version, overrides)),
        )
        print(
            f"bumped: {args.exercise_id} v{args.version}"
            f" -> v{bumped.version} (status={bumped.status})",
        )


if __name__ == "__main__":
    main()
