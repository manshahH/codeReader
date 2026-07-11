"""The periodic-jobs layer is actually invoked by the app (audit FIX 1).

Every job function already had isolated unit tests; what shipped broken was
the invocation: nothing ever ran them. These tests therefore assert against
the real FastAPI lifespan -- the scheduler starts with the app, ticks the
jobs, resolves a genuinely pending attempt end to end, and creates the next
attempts partition at startup -- not against the job functions directly.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.rubric import RubricResult
from app.config import get_settings
from app.jobs.runner import JobScheduler, PeriodicJob
from app.main import create_app
from app.models import Attempt
from tests.factories_m4 import (
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_summarize_exercise,
    make_user,
)

JOB_NAMES = {"grading_retry", "percentiles", "partitions"}


@pytest.fixture
def fast_job_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBS_ENABLED", "true")
    monkeypatch.setenv("JOB_GRADING_RETRY_INTERVAL_S", "0.05")
    monkeypatch.setenv("JOB_PERCENTILES_INTERVAL_S", "0.05")
    monkeypatch.setenv("JOB_PARTITIONS_INTERVAL_S", "60")
    get_settings.cache_clear()


async def _wait_until(predicate, timeout_s: float = 5.0):
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        result = await predicate()
        if result:
            return result
        if asyncio.get_running_loop().time() >= deadline:
            return result
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_lifespan_starts_the_scheduler_and_every_job_actually_ticks(
    fast_job_env: None,
) -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        scheduler = app.state.job_scheduler
        assert scheduler is not None
        assert {job.name for job in scheduler.jobs} == JOB_NAMES

        async def all_ticked() -> bool:
            return all(scheduler.run_counts[name] >= 1 for name in JOB_NAMES)

        assert await _wait_until(all_ticked), f"jobs never ran: {scheduler.run_counts}"
        assert scheduler.error_counts == {name: 0 for name in JOB_NAMES}
    # After lifespan exit the scheduler is stopped: no task keeps ticking.
    counts_after_stop = dict(scheduler.run_counts)
    await asyncio.sleep(0.2)
    assert scheduler.run_counts == counts_after_stop


@pytest.mark.asyncio
async def test_jobs_disabled_setting_skips_the_scheduler(
    fast_job_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBS_ENABLED", "false")
    get_settings.cache_clear()
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.job_scheduler is None


@pytest.mark.asyncio
async def test_grading_retry_job_resolves_a_pending_attempt_via_the_running_app(
    fast_job_env: None,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end through the scheduler: a grading_pending row left behind by
    a grader timeout is resolved by the app itself, with no manual job call.
    """
    user = await make_user(db_session)
    exercise = await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])
    db_session.add(
        Attempt(
            user_id=user.id,
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            session_date=dt.date(2026, 7, 11),
            answer={"text": "Retries the call with exponential backoff."},
            grading_mode="rubric",
            status="grading_pending",
            time_taken_ms=1000,
        ),
    )
    await db_session.commit()

    async def fake_grade_rubric(_exercise, _answer_text) -> RubricResult:
        return RubricResult(
            score=0.7,
            is_correct=True,
            rubric_hits=["retries with exponential backoff"],
            rubric_misses=[],
            reference_answer="Retries the wrapped call with backoff.",
        )

    monkeypatch.setattr("app.jobs.grading_retry.grade_rubric", fake_grade_rubric)

    app = create_app()
    async with app.router.lifespan_context(app):

        async def attempt_graded() -> bool:
            async with app.state.session_factory() as check_db:
                status = await check_db.scalar(
                    select(Attempt.status).where(Attempt.user_id == user.id),
                )
            return status == "graded"

        assert await _wait_until(attempt_graded), "pending attempt was never resolved by the app"

        async with app.state.session_factory() as check_db:
            attempt = await check_db.scalar(select(Attempt).where(Attempt.user_id == user.id))
            assert attempt.is_correct is True
            assert attempt.grader_output["rubric_hits"] == ["retries with exponential backoff"]


@pytest.mark.asyncio
async def test_partitions_job_startup_run_creates_next_month_partition(
    fast_job_env: None,
    db_session: AsyncSession,
) -> None:
    next_month = (dt.datetime.now(dt.UTC).date().replace(day=1) + dt.timedelta(days=32)).replace(
        day=1,
    )
    partition_name = f"attempts_{next_month:%Y_%m}"

    app = create_app()
    async with app.router.lifespan_context(app):
        scheduler = app.state.job_scheduler

        async def partitions_ran() -> bool:
            return scheduler.run_counts["partitions"] >= 1

        assert await _wait_until(partitions_ran)

    exists = await db_session.scalar(
        text("SELECT count(*) FROM pg_class WHERE relname = :name"),
        {"name": partition_name},
    )
    assert exists == 1


@pytest.mark.asyncio
async def test_one_failing_job_never_kills_the_others() -> None:
    """Negative test for the runner itself: a job that raises every tick is
    isolated -- its error is counted and the other jobs keep running.
    """
    ticks = {"healthy": 0}

    async def broken() -> None:
        raise RuntimeError("boom")

    async def healthy() -> None:
        ticks["healthy"] += 1

    scheduler = JobScheduler(
        [
            PeriodicJob("broken", 0.02, broken),
            PeriodicJob("healthy", 0.02, healthy),
        ],
    )
    await scheduler.start()
    try:

        async def both_ticked() -> bool:
            return scheduler.error_counts["broken"] >= 2 and ticks["healthy"] >= 2

        assert await _wait_until(both_ticked, timeout_s=2.0)
    finally:
        await scheduler.stop()
    assert scheduler.run_counts["broken"] == 0
    assert ticks["healthy"] >= 2
