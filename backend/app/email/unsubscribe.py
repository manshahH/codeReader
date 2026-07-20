"""One-click unsubscribe tokens (A3, D-137(7)).

STATELESS HMAC, which is deliberately the OPPOSITE of the stored, hashed,
single-use verification token in D-120(4). The difference is what the token can
do:

* A verification token GRANTS something. It promotes an address onto an
  account, so it is stored, single-use and expiring, and a leak is bounded by
  those properties.
* This token only REVOKES. The worst case for a leaked unsubscribe token is
  that someone stops mail the owner can switch back on in-app in one click.

That inversion drives three properties that would each be wrong for a
verification token:

* NO EXPIRY. An unsubscribe link in a two-year-old email must still work. That
  is both a deliverability expectation and the entire point of the mechanism.
* NOT SINGLE-USE. Any mail client that prefetches or scans links would burn a
  single-use token before the human ever clicked it.
* NO STORAGE. No row per sent email, no cleanup job, and the link survives a
  database restore.

Domain separation is not optional here: the key is derived from JWT_SECRET,
which also signs access tokens, so the HMAC input carries a constant version
prefix. Without it, a token minted by one subsystem could in principle be
presented to the other.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid

from app.config import get_settings
from app.email.links import link_origin
from app.models import SUPPRESSION_KINDS

# Version prefix, mixed into the MAC input rather than merely prepended to the
# payload string, so an unsubscribe MAC and any other JWT_SECRET-derived MAC
# cannot collide even on identical payload bytes. Bump it to invalidate every
# outstanding link at once, which is the only revocation lever a stateless
# token has.
_DOMAIN = b"codereader-unsubscribe-v1"


class InvalidUnsubscribeToken(ValueError):
    """The token is unusable. Never says WHY, for the D-120(5) reason."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise InvalidUnsubscribeToken("Malformed unsubscribe token.") from exc


def _mac(payload: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), _DOMAIN + b"\x00" + payload, hashlib.sha256).digest()


def mint_unsubscribe_token(user_id: uuid.UUID, kind: str) -> str:
    """`b64(payload).b64(mac)` over `user_id:kind`."""
    if kind not in SUPPRESSION_KINDS:
        raise ValueError(f"Unknown suppression kind: {kind!r}")
    payload = f"{user_id}:{kind}".encode()
    return f"{_b64(payload)}.{_b64(_mac(payload, get_settings().jwt_secrets[0]))}"


def parse_unsubscribe_token(token: str) -> tuple[uuid.UUID, str]:
    """Verify and decode, or raise InvalidUnsubscribeToken.

    Verified against EVERY configured JWT secret, not just the current one.
    These tokens never expire, so a secret rotation must not silently break
    every unsubscribe link already sitting in people's inboxes -- which would
    turn a rotation into a compliance problem.
    """
    if not token or not isinstance(token, str) or token.count(".") != 1:
        raise InvalidUnsubscribeToken("Malformed unsubscribe token.")

    encoded_payload, encoded_mac = token.split(".", 1)
    payload = _unb64(encoded_payload)
    presented = _unb64(encoded_mac)

    # compare_digest against each candidate secret, and never short-circuit out
    # of the loop early on a mismatch: the loop runs to completion so timing
    # does not reveal which secret matched.
    matched = False
    for secret in get_settings().jwt_secrets:
        if hmac.compare_digest(_mac(payload, secret), presented):
            matched = True
    if not matched:
        raise InvalidUnsubscribeToken("Unsubscribe token failed verification.")

    try:
        raw_user_id, _, kind = payload.decode("utf-8").partition(":")
        user_id = uuid.UUID(raw_user_id)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidUnsubscribeToken("Malformed unsubscribe token.") from exc

    # The MAC already covers `kind`, so this cannot be an attacker-chosen
    # value. It is checked anyway because a token minted before a kind was
    # renamed would otherwise write a row the CHECK constraint rejects, turning
    # a stale link into a 500 instead of a clean failure.
    if kind not in SUPPRESSION_KINDS:
        raise InvalidUnsubscribeToken("Unknown suppression kind.")

    return user_id, kind


def unsubscribe_api_url(user_id: uuid.UUID, kind: str) -> str:
    """The RFC 8058 one-click POST target, for the List-Unsubscribe header.

    Points at the API, and mail providers POST it without a session. Built from
    APP_ORIGIN and never from a request header, same rule as the verification
    link (D-120): a link we mail out is exactly the thing worth pointing at an
    attacker's origin.
    """
    origin = link_origin()
    return f"{origin}/v1/unsubscribe?token={mint_unsubscribe_token(user_id, kind)}"


def unsubscribe_page_url(user_id: uuid.UUID, kind: str) -> str:
    """The human-facing link in the body. Points at the SPA, NOT at the API.

    A GET must not act: prefetchers, corporate link scanners and mail-client
    previews all follow GETs, and any of them would silently unsubscribe the
    user. The page reads the token and POSTs on a button press. Same token,
    two entry points, and only one of them mutates.
    """
    origin = link_origin()
    return f"{origin}/unsubscribe?token={mint_unsubscribe_token(user_id, kind)}"
