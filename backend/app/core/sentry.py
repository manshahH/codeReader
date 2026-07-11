from __future__ import annotations

import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import Settings

REDACTED = "[Filtered]"

# Mirrors app.auth.service.REFRESH_COOKIE_NAME; duplicated rather than
# imported so core stays independent of the auth domain (module law).
REFRESH_COOKIE_NAME = "rt"

# Header/body-field/local-variable NAMES that are always sensitive regardless
# of value, e.g. a stack frame local named `answer_text` or `jwt_secret`.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token_enc_key|jwt_secret|password|authorization|answer)",
    re.IGNORECASE,
)

# Env VAR NAMES whose values are secrets; matched against os.environ so any
# stack-frame local that happens to hold one of these values (under any
# variable name) is caught even if the name pattern above misses it.
_ENV_SECRET_NAME_PATTERN = re.compile(r"(_API_KEY|_SECRET)$|^TOKEN_ENC_KEY$|^JWT_SECRET$")


def _secret_env_values() -> set[str]:
    values: set[str] = set()
    for key, value in os.environ.items():
        if not value or not _ENV_SECRET_NAME_PATTERN.search(key):
            continue
        for part in value.split(","):
            part = part.strip()
            if part:
                values.add(part)
    return values


def _scrub_cookie_header(value: str) -> str:
    chunks = []
    for chunk in value.split(";"):
        name = chunk.strip().partition("=")[0]
        if name == REFRESH_COOKIE_NAME:
            chunks.append(f"{name}={REDACTED}")
        else:
            chunks.append(chunk.strip())
    return "; ".join(chunks)


def _scrub_value(value: Any, secret_values: set[str]) -> Any:
    if isinstance(value, str):
        return REDACTED if value in secret_values else value
    if isinstance(value, dict):
        return _scrub_mapping(value, secret_values)
    if isinstance(value, list):
        return [_scrub_value(item, secret_values) for item in value]
    return value


def _scrub_mapping(data: dict[Any, Any], secret_values: set[str]) -> dict[Any, Any]:
    scrubbed: dict[Any, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and _SENSITIVE_KEY_PATTERN.search(key):
            scrubbed[key] = REDACTED
        else:
            scrubbed[key] = _scrub_value(value, secret_values)
    return scrubbed


def _scrub_headers(headers: dict[str, str]) -> dict[str, str]:
    scrubbed: dict[str, str] = {}
    for name, value in headers.items():
        lname = name.lower()
        if lname in ("authorization", "set-cookie"):
            continue
        if lname == "cookie":
            scrubbed[name] = _scrub_cookie_header(value)
            continue
        scrubbed[name] = value
    return scrubbed


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Strip the `rt` cookie, the Authorization header, request bodies (which
    may carry the summarize `answer.text` field or other free text), and any
    value matching a live *_API_KEY / *_SECRET / TOKEN_ENC_KEY / JWT_SECRET
    env var -- the latter guards against sentry-sdk's stack-frame local
    variable capture leaking a secret under an unrelated variable name.
    """
    secret_values = _secret_env_values()

    request = event.get("request")
    if request:
        headers = request.get("headers")
        if headers:
            request["headers"] = _scrub_headers(headers)
        # Request bodies are hostile/user free text (CLAUDE.md invariant 6)
        # and may contain the summarize answer.text field; drop wholesale
        # rather than trying to allowlist fields inside it.
        request.pop("data", None)

    for key in ("extra", "contexts"):
        section = event.get(key)
        if isinstance(section, dict):
            event[key] = _scrub_mapping(section, secret_values)

    exception = event.get("exception")
    if exception:
        for exc_value in exception.get("values", []):
            stacktrace = exc_value.get("stacktrace")
            if not stacktrace:
                continue
            for frame in stacktrace.get("frames", []):
                frame_vars = frame.get("vars")
                if frame_vars:
                    frame["vars"] = _scrub_mapping(frame_vars, secret_values)

    return event


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    return scrub_event(event, hint)


def init_sentry(settings: Settings) -> None:
    """No-op when SENTRY_DSN is unset -- local dev without a DSN must never
    be treated as an error.
    """
    if not settings.SENTRY_DSN:
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=before_send,
    )
