"""External job trigger, for platforms that scale to zero (A3, D-138).

THE PROBLEM THIS EXISTS FOR. The in-process scheduler (jobs/runner.py) runs
from the FastAPI lifespan, so it lives exactly as long as the app process. On
FastAPI Cloud the app scales to zero when idle, and the idle trough is
overnight -- which is precisely when an 08:00 reminder has to fire. A scheduler
that sleeps with the app is not a scheduler.

The subtler half, and the reason a keepalive ping does not fix this: each job
loop waits `interval_s` from the moment the process started
(`asyncio.wait_for(stop.wait(), timeout=interval_s)`). Every cold start
restarts that clock from zero. An app that wakes for 40 seconds of traffic and
sleeps again NEVER reaches a 60s reminder tick, let alone a 900s recap tick, no
matter how warm you keep it. Uptime is not the missing property; an external
clock is.

So the trigger is OUTSIDE the thing that sleeps: a scheduled workflow calls
this, and the HTTP request is itself what wakes the app. The in-process
scheduler is deliberately left exactly as it was, so local dev and any
always-on deployment keep working with no configuration.

SYNCHRONOUS, NOT FIRE-AND-FORGET. Returning 202 and running the sweep in a
background task would reintroduce the original bug in a smaller form: on a
scale-to-zero platform the instance can be suspended once the response is sent,
killing the task mid-sweep. The platform keeps an instance alive while a
request is in flight, so completing the work INSIDE the request is what
guarantees it completes at all. The cost is a slow request; the work is already
bounded by EMAIL_MAX_SENDS_PER_TICK and the send pacing, so it is bounded too.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs.reminders import send_daily_reminders
from app.jobs.weekly_email import send_weekly_recaps

logger = logging.getLogger(__name__)

# Only the notification jobs. The other three (grading_retry, percentiles,
# partitions) are deliberately NOT exposed: they are idempotent, tolerate a
# long gap, and none of them has a user-visible deadline the way a reminder
# does. Adding them here would widen an admin-authenticated surface for no
# benefit.
TRIGGERABLE: dict[str, Callable[[async_sessionmaker[AsyncSession]], Awaitable[dict[str, int]]]] = {
    "reminders": send_daily_reminders,
    "weekly_recap": send_weekly_recaps,
}

# Long enough to cover a full capped sweep (EMAIL_MAX_SENDS_PER_TICK at the
# send pacing, plus cold start), short enough that a crashed run self-heals
# well inside one trigger interval rather than blocking the next hour.
_LOCK_TTL_S = 600


async def run_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    *,
    names: list[str] | None = None,
) -> dict[str, object]:
    """Run the named jobs now. Never raises for one job; reports per job.

    OVERLAP IS SAFE BEFORE IT IS PREVENTED, and the order matters. Correctness
    does not depend on the lock below: `claim_period`'s primary key means two
    concurrent sweeps cannot both send the same period, which is the same
    property that makes the in-process scheduler safe across multiple app
    instances. The lock is a WASTE guard, not a correctness guard -- a delayed
    trigger landing on top of a running one would otherwise pay for a second
    full candidate query and a second round of losing races.

    SET NX EX rather than a Postgres advisory lock: it matches the existing
    per-address cooldown in email/service.py, and a TTL self-heals a crashed
    run without needing a session to stay open across the whole sweep.
    """
    selected = names or list(TRIGGERABLE)
    unknown = [n for n in selected if n not in TRIGGERABLE]
    if unknown:
        raise ValueError(f"Unknown job(s): {', '.join(sorted(unknown))}")

    results: dict[str, object] = {}
    for name in selected:
        lock_key = f"jobtrigger:running:{name}"
        claimed = await redis.set(lock_key, "1", ex=_LOCK_TTL_S, nx=True)
        if not claimed:
            # Not an error. A trigger that arrives while the previous one is
            # still working has nothing useful to do, and saying so plainly is
            # better than a 409 that a cron job would report as a failure.
            results[name] = {"skipped": "already_running"}
            logger.info("jobtrigger.already_running", extra={"job": name})
            continue
        try:
            results[name] = await TRIGGERABLE[name](session_factory)
        except Exception as exc:
            # One job failing must not stop the others, matching JobScheduler's
            # isolation. The type only, never the message: these run against
            # user data and an exception string can carry it.
            results[name] = {"error": type(exc).__name__}
            logger.exception("jobtrigger.failed", extra={"job": name})
        finally:
            await redis.delete(lock_key)

    logger.info("jobtrigger.ran", extra={"jobs": list(results)})
    return results
