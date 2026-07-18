"""Strict address validation, applied BEFORE an address reaches any sender.

Two separate jobs, and they are separate on purpose:

1. Reject anything that could inject a mail header. CR, LF, NUL and every other
   control character are refused outright rather than stripped. Stripping is the
   wrong move: it silently rewrites what the user typed into something they did
   not ask for, and a sanitizer that "fixes" hostile input is one bug away from
   fixing it incompletely. Refusing is total.
2. Reject syntactically implausible addresses early so the user learns about a
   typo on the profile screen instead of by never receiving mail.

This is intentionally NARROWER than RFC 5322. Quoted local parts, comments, and
bare-IP domain literals are all legal and all rejected here: none of them are
things a developer types into a "where should we send your weekly recap" field,
and each one is parser surface we gain nothing by accepting.
"""

from __future__ import annotations

import re

# RFC 5321 caps the whole path at 254 and the local part at 64.
MAX_EMAIL_LENGTH = 254
MAX_LOCAL_LENGTH = 64

# Any control character at all, not just CR/LF: the header-injection classics
# are \r and \n, but NUL truncates in C string handling and the rest have no
# business in an address either.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

_LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


class InvalidEmailError(ValueError):
    """The address is unusable. The message is safe to show the user."""


def normalize_email(raw: str) -> str:
    """Validate and canonicalize, or raise InvalidEmailError.

    Returns the lowercased address. The column is citext so comparison would be
    case-insensitive regardless; normalizing on the way in means the value we
    echo back to the user and the value we hand a sender are the same string.
    """
    if not isinstance(raw, str):
        raise InvalidEmailError("Enter an email address.")

    # Surrounding whitespace is a paste artifact, not hostile input, so it is
    # the one thing we forgive. Interior whitespace is not forgiven below.
    value = raw.strip()

    if not value:
        raise InvalidEmailError("Enter an email address.")
    if _CONTROL_CHARS.search(value):
        # Deliberately does not echo the offending character back.
        raise InvalidEmailError("That email address contains characters we can't accept.")
    if len(value) > MAX_EMAIL_LENGTH:
        raise InvalidEmailError("That email address is too long.")
    if any(ch.isspace() for ch in value):
        raise InvalidEmailError("That email address doesn't look right.")

    local, sep, domain = value.rpartition("@")
    if not sep or not local or not domain:
        raise InvalidEmailError("That email address doesn't look right.")
    if len(local) > MAX_LOCAL_LENGTH:
        raise InvalidEmailError("That email address is too long.")
    if not _LOCAL_RE.match(local):
        raise InvalidEmailError("That email address doesn't look right.")

    # A single-label domain is either a typo or an internal host we cannot
    # deliver to from a hosted sender, so it fails either way.
    labels = domain.split(".")
    if len(labels) < 2 or not all(_LABEL_RE.match(label) for label in labels):
        raise InvalidEmailError("That email address doesn't look right.")
    if len(labels[-1]) < 2:
        raise InvalidEmailError("That email address doesn't look right.")

    return value.lower()


def mask_email(value: str) -> str:
    """`alice@example.com` -> `a***e@example.com`, for logs.

    We log the FACT of a send (D-120), and an unreadable log is not an
    operable one, so the domain and the shape survive while the mailbox does
    not. Never used in a response body: the owner sees their own address in
    full, and nobody else ever sees it at all.
    """
    local, sep, domain = value.rpartition("@")
    if not sep:
        return "***"
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"
