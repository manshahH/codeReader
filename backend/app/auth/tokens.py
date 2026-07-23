from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Any


class TokenError(Exception):
    code = "invalid_token"
    message = "Invalid token."


class TokenExpiredError(TokenError):
    code = "token_expired"
    message = "Token expired."


ACCESS_CLAIMS = {"sub", "plan", "exp", "iat", "jti"}


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_b64(payload: dict[str, Any]) -> str:
    return _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


@dataclass(frozen=True)
class AccessClaims:
    sub: uuid.UUID
    plan: str
    exp: int
    iat: int
    jti: str


def issue_access_token(
    *,
    user_id: uuid.UUID,
    secret: str,
    ttl_seconds: int,
    now: dt.datetime | None = None,
) -> str:
    issued = now or dt.datetime.now(dt.UTC)
    iat = int(issued.timestamp())
    payload = {
        "sub": str(user_id),
        # VESTIGIAL, and NOT authoritative for entitlement (D-145(c)). This is a
        # token-SHAPE constant: verify_access_token rejects any token whose plan
        # is not "free", and ACCESS_CLAIMS asserts the key is present. It is kept
        # only because removing it would change ACCESS_CLAIMS and invalidate
        # every live token. Entitlement is resolved server-side per request from
        # the User row (app.core.entitlements.resolve_plan); never mint a
        # per-user plan claim here, because a 15-minute token would delay a
        # downgrade or refund and cannot be revoked (D-4 declined a denylist).
        "plan": "free",
        "exp": iat + ttl_seconds,
        "iat": iat,
        "jti": uuid.uuid4().hex,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    return f"{signing_input}.{_sign(signing_input, secret)}"


def verify_access_token(
    token: str,
    secrets_: list[str],
    now: dt.datetime | None = None,
) -> AccessClaims:
    try:
        header_b64, payload_b64, signature = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
    except Exception as exc:
        raise TokenError from exc

    if header != {"alg": "HS256", "typ": "JWT"}:
        raise TokenError
    if set(payload) != ACCESS_CLAIMS:
        raise TokenError
    if payload.get("plan") != "free":
        raise TokenError

    valid_signature = any(
        hmac.compare_digest(_sign(signing_input, secret), signature) for secret in secrets_
    )
    if not valid_signature:
        raise TokenError

    now_ts = int((now or dt.datetime.now(dt.UTC)).timestamp())
    if int(payload["exp"]) <= now_ts:
        raise TokenExpiredError

    try:
        return AccessClaims(
            sub=uuid.UUID(payload["sub"]),
            plan=payload["plan"],
            exp=int(payload["exp"]),
            iat=int(payload["iat"]),
            jti=str(payload["jti"]),
        )
    except Exception as exc:
        raise TokenError from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def refresh_token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def decode_unverified_payload(token: str) -> dict[str, Any]:
    _header, payload, _signature = token.split(".")
    return json.loads(_b64decode(payload))