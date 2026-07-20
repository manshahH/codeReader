"""The one origin every emailed link is built from.

Its own module because both `messages` and `unsubscribe` need it and
`messages` already imports `unsubscribe`; putting it in either would make the
pair circular.
"""

from __future__ import annotations

from app.config import get_settings


def link_origin() -> str:
    """The single origin to prefix an emailed path with.

    APP_ORIGIN is one origin on this branch, so `.split(",")[0]` is a no-op
    here. It is written anyway because the value in the wild is not always one
    origin: the local compose override already sets a comma-separated
    "localhost plus a LAN address" for phone testing, and pasting that whole
    string in front of a path yields
    `http://localhost:5173,http://192.168.100.10:5173/unsubscribe?token=...`
    -- silently, unclickably broken, in an email nobody gets to re-read. Found
    by walking the flow locally rather than by a test, because every test sets
    a single-origin APP_ORIGIN.

    Taking the first entry is also exactly the semantics the LAN-access work
    settles on, so this stays correct when that merges instead of having to be
    rediscovered.

    NEVER built from a request header: Host and X-Forwarded-Host are
    attacker-controlled, and a link we mail out is precisely the thing worth
    pointing at an attacker's origin (D-120).
    """
    return get_settings().APP_ORIGIN.split(",")[0].strip().rstrip("/")
