"""The outbound email seam (A2, D-120).

Shape mirrors attempts/grader_client.py deliberately: a Protocol, a real
provider client, and a test double, so nothing in the service layer knows or
cares which one it holds.

Two guarantees this module exists to make un-bypassable:

* EMAIL_SENDING_ENABLED is a HARD off-switch and defaults to false. When it is
  false, `get_email_sender()` returns a sender that records the call and returns
  -- it never constructs a request, never imports a transport, never resolves a
  hostname. A test or a local run therefore cannot make a network call by
  accident, and the assertion "no network call happens with the off-switch set"
  is structural rather than a matter of nobody having wired it up wrong.
* RESEND_API_KEY is validated LAZILY, at first send, exactly like
  ANTHROPIC_API_KEY (config.py, D-44). Requiring it to construct Settings would
  break every deploy and every test run that does not send mail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import get_settings
from app.email.address import mask_email

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
_SEND_TIMEOUT_S = 10


class EmailSendError(RuntimeError):
    """The provider refused or was unreachable."""


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    text: str
    html: str
    # D-126: the actionable link, carried separately so DisabledEmailSender can
    # log it in local dev without regex-scraping the body. Never read by the
    # real sender, and never included in the provider payload.
    dev_link: str | None = None
    # A3 (D-137(4)): the SECOND send-once layer, and the one that makes
    # retrying an ambiguous failure safe at all. Deterministic from the ledger
    # key ("{kind}:{user_id}:{period_key}"), so a retry of the same period
    # presents the same key and Resend collapses it. Without this, retrying a
    # ReadTimeout is a coin flip on a duplicate, because a timeout does not
    # tell us whether the request landed. None for A2's verification mail,
    # which is user-initiated and has no period to be idempotent over.
    idempotency_key: str | None = None
    # A3 (D-137(7)): RFC 8058 one-click unsubscribe. Both headers or neither --
    # List-Unsubscribe-Post without a URL to POST to is meaningless, and a URL
    # without the Post header only gets a mail client's "unsubscribe" affordance
    # in some clients. Server-owned values built from APP_ORIGIN, never from a
    # request header.
    headers: dict[str, str] = field(default_factory=dict)


class EmailSender(Protocol):
    async def send(self, message: OutboundEmail) -> None: ...


@dataclass
class DisabledEmailSender:
    """The off-switch. Records, logs, and returns. No transport, ever.

    `sent` exists so tests can assert an email WOULD have gone out (the service
    path ran to completion) while proving nothing left the process.
    """

    sent: list[OutboundEmail] = field(default_factory=list)

    async def send(self, message: OutboundEmail) -> None:
        self.sent.append(message)
        logger.info(
            "email.send.suppressed",
            extra={"to": mask_email(message.to), "subject": message.subject},
        )
        # D-126: with sending off, no mail exists, so the verification link is
        # otherwise unrecoverable -- the token is sha256-hashed at rest and
        # deliberately never logged (D-120), which left no way to walk the
        # verify path locally.
        #
        # DOUBLE-GATED, and the first gate is structural: this class is only
        # ever constructed by get_email_sender() when EMAIL_SENDING_ENABLED is
        # false, so production never reaches this code at all. The explicit
        # re-check below covers the one way that could be defeated -- someone
        # constructing DisabledEmailSender directly -- so a token can never be
        # logged on a sending deploy even by mistake.
        if message.dev_link and not get_settings().EMAIL_SENDING_ENABLED:
            logger.warning("email.verification.dev_link link=%s", message.dev_link)


class ResendEmailSender:
    """Real Resend-backed sender.

    Per-call AsyncClient, matching auth/oauth.py's HttpGithubClient rather than
    inventing a second outbound-HTTP convention in the same codebase.
    """

    async def send(self, message: OutboundEmail) -> None:
        settings = get_settings()
        api_key = settings.RESEND_API_KEY
        if not api_key:
            # Lazy validation, D-44 pattern: this is the first point at which a
            # missing key is actually a problem.
            raise EmailSendError("RESEND_API_KEY is not configured.")

        # Belt and braces. The address was already validated by
        # email/address.py before it was ever stored, and the subject is a
        # server-owned constant, but a header-injection guard that only runs at
        # the far end of the call chain is one refactor away from being skipped.
        # A3 adds message.headers to the sweep: those values embed a token and
        # an origin, and they are literally headers, so they are the one input
        # here where injection would be immediately exploitable.
        checked = [message.to, message.subject, settings.EMAIL_FROM]
        checked.extend(message.headers.keys())
        checked.extend(message.headers.values())
        if message.idempotency_key:
            checked.append(message.idempotency_key)
        for value in checked:
            if "\r" in value or "\n" in value or "\x00" in value:
                raise EmailSendError("Refusing to send: header injection attempt.")

        payload: dict[str, object] = {
            "from": settings.EMAIL_FROM,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }
        if message.headers:
            payload["headers"] = dict(message.headers)

        request_headers = {"Authorization": f"Bearer {api_key}"}
        if message.idempotency_key:
            request_headers["Idempotency-Key"] = message.idempotency_key
        try:
            async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_S) as client:
                response = await client.post(
                    RESEND_ENDPOINT,
                    json=payload,
                    headers=request_headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # The exception text can carry the request body on some httpx
            # errors, and that body is a verification email. Log the shape, not
            # the content.
            logger.warning(
                "email.send.failed",
                extra={"to": mask_email(message.to), "error": type(exc).__name__},
            )
            raise EmailSendError("Could not send the verification email.") from exc

        logger.info(
            "email.send.ok",
            extra={"to": mask_email(message.to), "subject": message.subject},
        )


def get_email_sender() -> EmailSender:
    """The only place a real sender is ever constructed."""
    if not get_settings().EMAIL_SENDING_ENABLED:
        return DisabledEmailSender()
    return ResendEmailSender()
