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
from pipeline.config import resolve_repo_path
from pipeline.publish import approve, fix_and_bump, kill, pull

# Human review at 200-exercise scale (CLAUDE.md M8 part 2) is bottlenecked on
# whether a reviewer can tell, WITHOUT opening the receipts file, whether an
# exercise is worth a close look. These are the two things that make a
# candidate riskier than a plain pass: the sandbox-derived answer key
# disagreeing with what the generator claimed (D-49/D-11 style), and a
# semantic gate landing on "flag" instead of a clean "pass"/"reject".
_GATE_KEYS = ("defect_audit", "solver", "reasons")


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


def load_validation_report(exercise: Exercise) -> dict[str, Any] | None:
    """The receipts written by orchestrator.py/publish.py (D-48), read back
    for review. None if the pointer is missing or the file is gone --
    review must degrade gracefully, not crash, on a stale/moved report.

    The pointer is repo-relative (D-109) and is resolved against the repo
    root, so a report written by the containerised pipeline reads back from
    the host. Graceful degradation is why this bug hid: 92 of 98 exercises
    reported "no validation report on disk" while the files sat on disk.
    """
    if not exercise.validation_report_url:
        return None
    path = resolve_repo_path(exercise.validation_report_url)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def quality_flags(report: dict[str, Any] | None) -> list[str]:
    """Everything worth a reviewer's extra attention, in one place: a
    sandbox-derived answer key that disagreed with the generator's claim
    (D-49/D-11 style -- not wrong, but worth a second look), an explanation
    whose draft never referenced the verified facts (D-32), and any
    semantic gate that landed on "flag" rather than a clean "pass".
    """
    if report is None:
        return ["no_validation_report"]
    flags: list[str] = []
    if report.get("sandbox_gate", {}).get("bug_lines_claim_mismatch"):
        flags.append("bug_lines_claim_mismatch")
    if report.get("explanation", {}).get("mismatch_flagged"):
        flags.append("explanation_mismatch")
    for gate_key in _GATE_KEYS:
        gate = report.get(gate_key)
        if gate and gate.get("verdict") not in (None, "pass"):
            flags.append(f"{gate_key}={gate['verdict']}")
    return flags


def quality_summary(exercise: Exercise) -> str:
    """One line, budgeted for the `list` view: gate verdicts + confidence +
    flags, so a reviewer can triage 200 rows before opening any of them."""
    report = load_validation_report(exercise)
    if report is None:
        return "no validation report on disk"
    verdicts = [
        f"{key}={report[key]['verdict']}" for key in _GATE_KEYS if key in report
    ]
    solver_confidence = (report.get("solver") or {}).get("raw", {}).get("confidence")
    bits = []
    if verdicts:
        bits.append(" ".join(verdicts))
    if solver_confidence is not None:
        bits.append(f"solver_confidence={solver_confidence}")
    flags = quality_flags(report)
    bits.append(("FLAGS: " + ", ".join(flags)) if flags else "clean")
    return " | ".join(bits)


def print_list(exercises: list[Exercise]) -> None:
    for row in exercises:
        print(
            f"{row.id} v{row.version}  {row.type:<13} "
            f"difficulty={row.difficulty_authored} concepts={row.concepts} "
            f"created_at={row.created_at.isoformat()}",
        )
        print(f"    quality: {quality_summary(row)}")


def _format_sandbox_checks(report: dict[str, Any] | None) -> str:
    if report is None or "sandbox_gate" not in report:
        return "(no sandbox report on disk)"
    sandbox = report["sandbox_gate"]
    lines = [
        f"- [{'x' if check['passed'] else ' '}] {check['name']}"
        + (f" -- {check['detail']}" if check.get("detail") else "")
        for check in sandbox.get("checks", [])
    ]
    return "\n".join(lines) if lines else "(no individual checks recorded)"


def _format_semantic_gates(report: dict[str, Any] | None) -> str:
    if report is None:
        return "(no validation report on disk)"
    lines = []
    for gate_key in _GATE_KEYS:
        gate = report.get(gate_key)
        if gate is None:
            continue
        lines.append(f"- **{gate_key}**: {gate['verdict']} -- {gate.get('detail', '')}")
    return "\n".join(lines) if lines else "(no semantic gate receipts for this type)"


def format_exercise_markdown(exercise: Exercise) -> str:
    """The FULL exercise as a reviewer needs it (CLAUDE.md M8 part 2): code,
    question/options, the sandbox-verified answer key, the explanation, and
    the validation receipts -- one self-contained markdown section, whether
    printed standalone (`show`) or concatenated into a `packet`.
    """
    report = load_validation_report(exercise)
    payload = exercise.payload
    grading = exercise.grading
    explanation = exercise.explanation

    parts: list[str] = [
        f"### {exercise.type} -- `{exercise.id}` v{exercise.version}",
        f"status={exercise.status} difficulty={exercise.difficulty_authored} "
        f"concepts={exercise.concepts} created_at={exercise.created_at.isoformat()}",
        f"quality: {quality_summary(exercise)}",
        "",
        "#### Code",
        "```python",
        payload.get("code", ""),
        "```",
        f"context: {payload.get('context_note', '')}",
        "",
    ]

    if exercise.type == "spot_the_bug":
        parts += [
            "#### Reason options",
            *(
                f"- **{opt['id']}**: {opt['text']}"
                + (" <-- correct" if opt["id"] == grading.get("correct_reason_id") else "")
                for opt in payload.get("reason_options", [])
            ),
            "",
            "#### Verified answer key (sandbox-derived, D-49)",
            f"- correct_lines: {grading.get('correct_lines')}",
            f"- correct_reason_id: {grading.get('correct_reason_id')}",
            "",
            "#### Failing-test proof",
            "```python",
            grading.get("artifacts", {}).get("failing_test", ""),
            "```",
        ]
    else:
        parts += [
            f"#### Question\n{payload.get('question', '')}",
            "#### Choices",
            *(
                f"- **{choice['id']}**: {choice['text']}"
                + (" <-- correct" if choice["id"] == grading.get("correct_choice_id") else "")
                for choice in payload.get("choices", [])
            ),
            "",
            "#### Verified answer key (sandbox-captured stdout)",
            f"- correct_choice_id: {grading.get('correct_choice_id')}",
            f"- captured_stdout: {grading.get('captured_stdout')!r}",
        ]

    parts += [
        "",
        "#### Explanation",
        f"- summary: {explanation.get('summary', '')}",
        f"- principle: {explanation.get('principle', '')}",
        f"- mismatch_flagged: {explanation.get('mismatch_flagged', False)}"
        + (
            f" ({explanation['mismatch_detail']})"
            if explanation.get("mismatch_detail")
            else ""
        ),
    ]
    # why_wrong (trace/predict_the_fix): per-distractor rationale, the one
    # piece of generated content no gate has ever inspected (CLAUDE.md M8
    # part 2) -- surfaced so a reviewer actually reads it, not just the
    # summary/principle.
    why_wrong = explanation.get("why_wrong")
    if why_wrong:
        parts += [
            "- why_wrong:",
            *(f"  - **{w.get('choice_id')}**: {w.get('note', '')}" for w in why_wrong),
        ]
    parts += [
        "",
        "#### Sandbox checks",
        _format_sandbox_checks(report),
        "",
        "#### Semantic gate verdicts",
        _format_semantic_gates(report),
    ]
    return "\n".join(parts)


def print_show(exercise: Exercise | None) -> None:
    if exercise is None:
        print("not found")
        return
    print(format_exercise_markdown(exercise))


def build_review_packet(exercises: list[Exercise]) -> str:
    """Every pending exercise as ONE markdown file (CLAUDE.md M8 part 2): the
    only realistic way to review 200 exercises is reading them in one
    sitting, not paging through the CLI one `show` at a time.
    """
    header = f"# Review packet -- {len(exercises)} pending exercise(s)\n"
    toc = "\n".join(
        f"{i + 1}. {row.type} `{row.id}` v{row.version} "
        f"(concepts={row.concepts}, difficulty={row.difficulty_authored}) "
        f"-- {quality_summary(row)}"
        for i, row in enumerate(exercises)
    )
    body = "\n\n---\n\n".join(format_exercise_markdown(row) for row in exercises)
    return f"{header}\n## Contents\n{toc}\n\n---\n\n{body}\n"


async def cmd_packet(session: AsyncSession, *, limit: int = 500) -> str:
    exercises = await cmd_list(session, limit=limit)
    return build_review_packet(exercises)


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

    packet_parser = sub.add_parser(
        "packet",
        help="export every pending (in_review) exercise to one markdown file for review",
    )
    packet_parser.add_argument(
        "--out",
        type=Path,
        default=Path("pipeline/review_packet.md"),
        help="output markdown file (default: pipeline/review_packet.md)",
    )
    packet_parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="max exercises to include (default: 500)",
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
    elif args.command == "packet":
        packet = asyncio.run(_run(lambda session: cmd_packet(session, limit=args.limit)))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(packet, encoding="utf-8")
        # Count SECTION headings only: `packet.count('### ')` also matched every
        # '#### Code'/'#### Reason options' sub-heading and any '### ' inside a
        # snippet, reporting 616 for a 77-exercise packet.
        sections = sum(1 for line in packet.splitlines() if line.startswith("### "))
        print(f"wrote review packet: {args.out} ({sections} exercise(s))")


if __name__ == "__main__":
    main()
