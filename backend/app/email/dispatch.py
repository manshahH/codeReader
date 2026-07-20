"""The sweep both notification jobs run (A3, D-137(3), (10)).

One place holds claim -> commit -> send -> record, because that ordering IS the
send-once guarantee and it must not be re-derived per job. The two jobs supply
only "who is eligible right now" and "what does their message say"; everything
about how a send is attempted, paced, isolated and recorded lives here.

FAILURE ISOLATION IS TWO RINGS. JobScheduler already stops one job from killing
another. This is the inner ring: each recipient runs in its own transaction
inside its own try/except, so one bad address cannot end the sweep for the other
199.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.email.address import mask_email
from app.email.deliveries import (
    claim_period,
    mark_failed,
    mark_sent,
    mark_skipped,
    read_payload,
    store_payload,
)
from app.email.sender import EmailSender, EmailSendError, OutboundEmail

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Candidate:
    """A user the job believes is due, before the ledger has ruled on it."""

    user_id: uuid.UUID
    email: str
    period_key: str


@dataclasses.dataclass
class SweepResult:
    considered: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    not_claimed: int = 0
    deferred: int = 0

    def as_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)


def delivery_idempotency_key(kind: str, user_id: uuid.UUID, period_key: str) -> str:
    """The provider-side dedup key (D-137(4)).

    Deterministic from the ledger identity, so a bounded retry of the same
    period presents the same key and Resend collapses it. This is what makes
    retrying an ambiguous failure (a timeout that may or may not have landed)
    safe rather than a coin flip.
    """
    return f"{kind}:{user_id}:{period_key}"


def _payload_from_message(message: OutboundEmail) -> dict:
    """The bytes we will resend. `idempotency_key` is deliberately NOT stored:
    it is derived from the ledger identity, so it is already immutable per
    period and storing it would create a second source of truth for it."""
    return {
        "to": message.to,
        "subject": message.subject,
        "text": message.text,
        "html": message.html,
        "headers": dict(message.headers),
        "dev_link": message.dev_link,
    }


def _message_from_payload(payload: dict) -> OutboundEmail:
    return OutboundEmail(
        to=payload["to"],
        subject=payload["subject"],
        text=payload["text"],
        html=payload["html"],
        dev_link=payload.get("dev_link"),
        headers=dict(payload.get("headers") or {}),
    )


async def run_sweep(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender,
    *,
    kind: str,
    candidates: list[Candidate],
    build_message: Callable[[AsyncSession, Candidate], Awaitable[OutboundEmail | None]],
) -> SweepResult:
    """Claim, send and record each candidate. Never raises for one recipient.

    `build_message` returns None to mean "claimed, but deliberately not sent"
    (the empty recap week, D-137(8)); the period is then closed as 'skipped'
    rather than left open to be re-derived on every later tick.

    ORDERING, and it is the whole point: the claim is COMMITTED before the
    provider call. Send-then-record has a window where a crash loses the record
    and the next tick sends again, and a duplicate reminder is the expensive
    direction of that trade (D-137(3)).
    """
    settings = get_settings()
    result = SweepResult(considered=len(candidates))
    pace = 1.0 / settings.EMAIL_SENDS_PER_SECOND if settings.EMAIL_SENDS_PER_SECOND > 0 else 0.0
    attempted = 0

    for index, candidate in enumerate(candidates):
        if attempted >= settings.EMAIL_MAX_SENDS_PER_TICK:
            # Deferred, not dropped, and counted so a cap that is biting is
            # visible in the job log rather than looking like a short list.
            # Safe only because reminder eligibility runs to the end of the
            # user's local day, so everyone here is still a candidate on the
            # next tick (D-137(10)).
            result.deferred = len(candidates) - index
            logger.info(
                "email.sweep.capped",
                extra={
                    "kind": kind,
                    "cap": settings.EMAIL_MAX_SENDS_PER_TICK,
                    "deferred": result.deferred,
                },
            )
            break

        try:
            async with session_factory() as claim_session:
                claimed = await claim_period(
                    claim_session, candidate.user_id, kind, candidate.period_key
                )
                if claimed:
                    await claim_session.commit()
            if not claimed:
                result.not_claimed += 1
                continue
        except Exception:
            # A failure to even claim is a database problem, not a mail
            # problem. Nothing was sent and nothing was recorded, so the next
            # tick retries this user cleanly.
            result.failed += 1
            logger.exception("email.claim.failed", extra={"kind": kind})
            continue

        attempted += 1
        if pace and attempted > 1:
            await asyncio.sleep(pace)

        try:
            async with session_factory() as work_session:
                # RENDER ONCE PER PERIOD, then resend those exact bytes forever.
                # Resend's idempotency contract is same-key-SAME-PAYLOAD: a
                # reused key carrying a changed body is a 409, and a changed key
                # would risk the duplicate the ledger exists to prevent. The
                # reminder body legitimately moves between attempts (it names
                # today's exercise count once a session exists), so without this
                # a retry after the user opened the app could never succeed.
                stored = await read_payload(
                    work_session, candidate.user_id, kind, candidate.period_key
                )
                if stored is not None:
                    message = _message_from_payload(stored)
                else:
                    message = await build_message(work_session, candidate)

                if message is None:
                    await mark_skipped(
                        work_session,
                        candidate.user_id,
                        kind,
                        candidate.period_key,
                        note="nothing to report",
                    )
                    await work_session.commit()
                    result.skipped += 1
                    continue

                if stored is None:
                    # Committed BEFORE the send, for the same reason the claim
                    # is: a crash between rendering and sending must still
                    # leave the retry something to resend.
                    await store_payload(
                        work_session,
                        candidate.user_id,
                        kind,
                        candidate.period_key,
                        payload=_payload_from_message(message),
                    )
                    await work_session.commit()

                try:
                    await sender.send(
                        dataclasses.replace(
                            message,
                            idempotency_key=delivery_idempotency_key(
                                kind, candidate.user_id, candidate.period_key
                            ),
                        ),
                    )
                except EmailSendError as exc:
                    # A DEFINITE failure, and committing it is what makes the
                    # period retryable. The exception TYPE only: an httpx error
                    # can carry the request body, and that body is somebody's
                    # mail (D-120).
                    # Type AND status. "HTTPStatusError 422" says the
                    # template is broken; "HTTPStatusError 503" says the
                    # provider was down; "EmailSendError None" says we refused
                    # it ourselves before building a request. Recording only
                    # the type made all three look identical.
                    detail = type(exc.__cause__ or exc).__name__
                    if exc.status is not None:
                        detail = f"{detail} {exc.status}"
                    await mark_failed(
                        work_session,
                        candidate.user_id,
                        kind,
                        candidate.period_key,
                        error=detail,
                    )
                    await work_session.commit()
                    result.failed += 1
                    logger.warning(
                        "email.send.failed",
                        extra={"kind": kind, "to": mask_email(candidate.email)},
                    )
                    continue

                await mark_sent(work_session, candidate.user_id, kind, candidate.period_key)
                await work_session.commit()
                result.sent += 1
                logger.info(
                    "email.send.ok",
                    extra={
                        "kind": kind,
                        "to": mask_email(candidate.email),
                        "period": candidate.period_key,
                    },
                )
        except Exception:
            # The ambiguous case (D-137(3)): we do not know whether the send
            # landed, so the row stays 'claimed', which is TERMINAL. The sweep
            # continues for everyone else.
            result.failed += 1
            logger.exception(
                "email.send.unhandled",
                extra={"kind": kind, "period": candidate.period_key},
            )

    return result
