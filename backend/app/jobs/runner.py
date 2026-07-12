"""In-process periodic jobs runner.

Every job in app/jobs existed and passed its unit tests, but nothing ever
invoked them: no scheduler, no cron, no __main__ (the audit's FIX 1). This is
the missing invocation layer. docs/06 pins background jobs as "plain asyncio
workers + cron (no Celery at MVP)"; this is the plain-asyncio-worker half --
a set of asyncio tasks started from the FastAPI lifespan, zero new
dependencies -- chosen over a separate cron container so a running API
process is sufficient for grades to resolve, stats to compute, and
partitions to exist (one process to deploy, one to monitor at MVP scale).
Each job module also has a __main__ for manual/cron invocation, so moving to
an external cron later is a compose change, not a code change.

Failure isolation: one job raising never kills the others or the app; the
error is logged and the next tick runs normally. `run_counts`/`error_counts`
exist so tests can assert the app ACTUALLY invokes the jobs -- the gap that
let the uninvoked layer ship was testing the job functions only in
isolation.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime as dt
import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.jobs.grading_retry import resolve_pending_summarize_grades
from app.jobs.partitions import ensure_next_month_attempts_partition
from app.jobs.percentiles import compute_exercise_stats

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class PeriodicJob:
    name: str
    interval_s: float
    run: Callable[[], Awaitable[object]]
    # Partition creation must not wait a full interval after a deploy that
    # straddles a month boundary; anything idempotent can opt in.
    run_at_startup: bool = False


class JobScheduler:
    def __init__(self, jobs: list[PeriodicJob]) -> None:
        self.jobs = list(jobs)
        self.run_counts: dict[str, int] = {job.name: 0 for job in self.jobs}
        self.error_counts: dict[str, int] = {job.name: 0 for job in self.jobs}
        # M8 beta readiness: "job-runner health" needs more than a
        # cumulative count to answer "is this job still alive right now" --
        # a run_count that stopped climbing between two /admin/metrics polls
        # is invisible without a timestamp to compare against.
        self.last_run_at: dict[str, str | None] = dict.fromkeys(self.run_counts)
        self.last_error_at: dict[str, str | None] = dict.fromkeys(self.run_counts)
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._job_loop(job), name=f"job:{job.name}") for job in self.jobs
        ]

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def _run_once(self, job: PeriodicJob) -> None:
        try:
            result = await job.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.error_counts[job.name] += 1
            self.last_error_at[job.name] = dt.datetime.now(dt.UTC).isoformat()
            logger.exception("periodic job %r failed; next tick unaffected", job.name)
        else:
            self.run_counts[job.name] += 1
            self.last_run_at[job.name] = dt.datetime.now(dt.UTC).isoformat()
            logger.info("periodic job %r ran: %s", job.name, result)

    async def _job_loop(self, job: PeriodicJob) -> None:
        if job.run_at_startup:
            await self._run_once(job)
        while True:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=job.interval_s)
                return
            except TimeoutError:
                pass
            await self._run_once(job)


def build_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
) -> JobScheduler:
    async def run_grading_retry() -> object:
        async with session_factory() as db:
            return await resolve_pending_summarize_grades(db, redis)

    async def run_percentiles() -> object:
        async with session_factory() as db:
            return await compute_exercise_stats(db)

    async def run_partitions() -> object:
        async with session_factory() as db:
            partition_name = await ensure_next_month_attempts_partition(db)
            await db.commit()
            return partition_name

    return JobScheduler(
        [
            PeriodicJob(
                "grading_retry",
                settings.JOB_GRADING_RETRY_INTERVAL_S,
                run_grading_retry,
            ),
            PeriodicJob(
                "percentiles",
                settings.JOB_PERCENTILES_INTERVAL_S,
                run_percentiles,
            ),
            # ensure_next_month_attempts_partition is CREATE IF NOT EXISTS, so
            # a daily tick is a cheap no-op 29 days a month; the alternative
            # (a true monthly interval) never fires in a process that restarts
            # more often than monthly.
            PeriodicJob(
                "partitions",
                settings.JOB_PARTITIONS_INTERVAL_S,
                run_partitions,
                run_at_startup=True,
            ),
        ],
    )
