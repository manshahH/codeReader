"""A2 email capture (docs/10; D-120).

Every gate here has a negative, per CLAUDE.md: a gate that cannot prove it
REJECTS a crafted bad input is not a gate. The security-relevant ones are the
generic-failure tests (an oracle is the bug, not a wrong status code), the
partial-index tests (uniqueness must attach to proven control, not to typing),
and test_off_switch_makes_a_network_call_impossible, which fails loudly if any
code path can reach httpx with sending disabled.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import get_settings
from app.email.address import InvalidEmailError, normalize_email
from app.email.sender import (
    DisabledEmailSender,
    EmailSendError,
    OutboundEmail,
    ResendEmailSender,
    get_email_sender,
)
from app.email.service import verification_token_hash
from app.models import EmailVerificationToken, User
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_user,
)


class RecordingSender:
    """Stands in for the provider. Records, never transports."""

    def __init__(self) -> None:
        self.sent: list[OutboundEmail] = []

    async def send(self, message: OutboundEmail) -> None:
        self.sent.append(message)

    @property
    def last_token(self) -> str:
        match = re.search(r"/verify-email\?token=([A-Za-z0-9_\-%]+)", self.sent[-1].text)
        assert match, f"no verification link in: {self.sent[-1].text!r}"
        return match.group(1)


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
async def client(sender: RecordingSender) -> AsyncClient:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_email_sender] = lambda: sender
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


async def _capture(client: AsyncClient, headers: dict[str, str], email: str):
    return await client.post("/v1/me/email", headers=headers, json={"email": email})


# --------------------------------------------------------------------------
# Capture and the pending state
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_puts_address_in_pending_and_sends_a_link(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    response = await _capture(client, headers, "dev@example.com")

    assert response.status_code == 200
    assert response.json() == {
        "email": None,
        "email_verified": False,
        "pending_email": "dev@example.com",
    }
    assert len(sender.sent) == 1
    # The link points at APP_ORIGIN (m4_env sets it), never at a request header.
    assert sender.sent[0].text.startswith("Confirm this address")
    assert "https://app.example/verify-email?token=" in sender.sent[0].text


@pytest.mark.asyncio
async def test_token_is_hashed_at_rest_and_never_stored_raw(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    await _capture(client, auth_headers(user), "dev@example.com")
    raw = sender.last_token

    row = await db_session.scalar(select(EmailVerificationToken))
    assert row.token_hash == verification_token_hash(raw)
    # The raw token appears nowhere in the row.
    assert raw.encode() not in bytes(row.token_hash)
    assert row.email == "dev@example.com"
    assert row.consumed_at is None and row.invalidated_at is None


@pytest.mark.asyncio
async def test_capture_does_not_touch_the_verified_address(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """The whole point of D-120(2): a typo must not kill a working channel."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "good@example.com")
    await client.post("/v1/me/email/verify", headers=headers, json={"token": sender.last_token})

    response = await _capture(client, headers, "typo@exmaple.com")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "good@example.com"  # still live
    assert body["email_verified"] is True
    assert body["pending_email"] == "typo@exmaple.com"


# --------------------------------------------------------------------------
# Verification: succeeds once, then every failure mode
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verification_succeeds_once_and_the_same_token_then_fails(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    token = sender.last_token

    first = await client.post("/v1/me/email/verify", headers=headers, json={"token": token})
    assert first.status_code == 200
    assert first.json() == {
        "email": "dev@example.com",
        "email_verified": True,
        "pending_email": None,
    }

    # NEGATIVE: single-use.
    second = await client.post("/v1/me/email/verify", headers=headers, json={"token": token})
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "verification_failed"


@pytest.mark.asyncio
async def test_expired_token_fails(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    token = sender.last_token

    await db_session.execute(
        text("UPDATE email_verification_tokens SET expires_at = now() - interval '1 second'"),
    )
    await db_session.commit()

    response = await client.post("/v1/me/email/verify", headers=headers, json={"token": token})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "verification_failed"
    refreshed = await db_session.get(User, user.id)
    await db_session.refresh(refreshed)
    assert refreshed.email is None


@pytest.mark.asyncio
async def test_another_users_token_fails(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    owner = await make_user(db_session)
    attacker = await make_user(db_session)
    await _capture(client, auth_headers(owner), "owner@example.com")
    stolen = sender.last_token

    response = await client.post(
        "/v1/me/email/verify", headers=auth_headers(attacker), json={"token": stolen}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "verification_failed"
    attacker_row = await db_session.get(User, attacker.id)
    await db_session.refresh(attacker_row)
    assert attacker_row.email is None


@pytest.mark.asyncio
async def test_unknown_token_fails_identically_to_a_real_but_used_one(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """The oracle test. Every failure must be byte-identical bar request_id."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    token = sender.last_token
    await client.post("/v1/me/email/verify", headers=headers, json={"token": token})

    used = await client.post("/v1/me/email/verify", headers=headers, json={"token": token})
    unknown = await client.post(
        "/v1/me/email/verify", headers=headers, json={"token": "not-a-real-token"}
    )

    assert used.status_code == unknown.status_code == 400
    used_error = used.json()["error"]
    unknown_error = unknown.json()["error"]
    assert used_error["code"] == unknown_error["code"]
    assert used_error["message"] == unknown_error["message"]


@pytest.mark.asyncio
async def test_issuing_a_second_address_invalidates_the_first_token(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "first@example.com")
    first_token = sender.last_token

    # Cooldown is per-user and per-address; clear it so the second capture is
    # testing invalidation and not the throttle.
    await _clear_cooldowns()
    await _capture(client, headers, "second@example.com")

    # NEGATIVE: the superseded link is dead, and crucially it cannot promote
    # "first@example.com" now that a newer address is pending.
    response = await client.post(
        "/v1/me/email/verify", headers=headers, json={"token": first_token}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "verification_failed"

    row = await db_session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.email == "first@example.com"),
    )
    assert row.invalidated_at is not None  # stamped, not deleted: the ledger explains it


@pytest.mark.asyncio
async def test_a_stale_token_cannot_promote_a_newer_pending_address(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """Tokens carry their target address, so a stale link is scoped, not just dead."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "first@example.com")
    stale = sender.last_token
    await _clear_cooldowns()
    await _capture(client, headers, "second@example.com")

    await client.post("/v1/me/email/verify", headers=headers, json={"token": stale})

    refreshed = await db_session.get(User, user.id)
    await db_session.refresh(refreshed)
    assert refreshed.email is None
    assert refreshed.pending_email == "second@example.com"


# --------------------------------------------------------------------------
# Throttle
# --------------------------------------------------------------------------


async def _clear_cooldowns() -> None:
    from redis.asyncio import Redis

    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        async for key in redis.scan_iter("emailsend:cooldown:*"):
            await redis.delete(key)
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_throttle_blocks_a_rapid_resend(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    assert len(sender.sent) == 1

    response = await client.post("/v1/me/email/resend", headers=headers)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in response.headers
    assert len(sender.sent) == 1  # nothing left the process


@pytest.mark.asyncio
async def test_resend_works_once_the_cooldown_has_passed(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """The positive half: the throttle is a delay, not a wall."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    first_token = sender.last_token
    await _clear_cooldowns()

    response = await client.post("/v1/me/email/resend", headers=headers)

    assert response.status_code == 200
    assert len(sender.sent) == 2
    assert sender.last_token != first_token  # reissued, not replayed


@pytest.mark.asyncio
async def test_throttle_is_per_address_not_only_per_user(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """NEGATIVE for the per-user-only design: two accounts, one mailbox.

    A per-user-only throttle would let an attacker flood one address by
    rotating accounts, so the per-address bucket must deny the second account.
    """
    first = await make_user(db_session)
    second = await make_user(db_session)
    await _capture(client, auth_headers(first), "victim@example.com")

    response = await _capture(client, auth_headers(second), "victim@example.com")

    assert response.status_code == 429
    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_resend_without_a_pending_address_is_a_conflict(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)

    response = await client.post("/v1/me/email/resend", headers=auth_headers(user))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_pending_email"
    assert sender.sent == []


# --------------------------------------------------------------------------
# Enumeration: an address verified elsewhere must not be detectable
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_does_not_leak_that_an_address_is_verified_elsewhere(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    owner = await make_user(db_session)
    owner_headers = auth_headers(owner)
    await _capture(client, owner_headers, "taken@example.com")
    await client.post(
        "/v1/me/email/verify", headers=owner_headers, json={"token": sender.last_token}
    )

    prober = await make_user(db_session)
    prober_headers = auth_headers(prober)
    await _clear_cooldowns()
    taken = await _capture(client, prober_headers, "taken@example.com")
    await _clear_cooldowns()
    free = await _capture(client, prober_headers, "free@example.com")

    # Identical status and identical shape. The only difference is the address
    # the caller themselves supplied.
    assert taken.status_code == free.status_code == 200
    assert taken.json() == {
        "email": None,
        "email_verified": False,
        "pending_email": "taken@example.com",
    }
    assert free.json() == {
        "email": None,
        "email_verified": False,
        "pending_email": "free@example.com",
    }


@pytest.mark.asyncio
async def test_losing_the_uniqueness_race_returns_the_generic_failure(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """The second account CAN hold a pending token for a taken address (that is
    the anti-squatting design), and its promotion fails at the index, generically."""
    owner = await make_user(db_session)
    owner_headers = auth_headers(owner)
    await _capture(client, owner_headers, "taken@example.com")
    await client.post(
        "/v1/me/email/verify", headers=owner_headers, json={"token": sender.last_token}
    )

    prober = await make_user(db_session)
    prober_headers = auth_headers(prober)
    await _clear_cooldowns()
    await _capture(client, prober_headers, "taken@example.com")

    response = await client.post(
        "/v1/me/email/verify", headers=prober_headers, json={"token": sender.last_token}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "verification_failed"
    # The real owner is untouched.
    owner_row = await db_session.get(User, owner.id)
    await db_session.refresh(owner_row)
    assert owner_row.email == "taken@example.com"


# --------------------------------------------------------------------------
# The partial unique index itself
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_permits_two_unverified_rows_with_the_same_address(
    db_session,
) -> None:
    """Anti-squatting: typing an address must not reserve it."""
    for _ in range(2):
        db_session.add(
            User(username=f"reader-{uuid.uuid4().hex[:10]}", pending_email="shared@example.com"),
        )
    await db_session.flush()

    rows = await db_session.execute(
        text("SELECT count(*) FROM users WHERE pending_email = 'shared@example.com'"),
    )
    assert rows.scalar_one() == 2
    await db_session.rollback()


@pytest.mark.asyncio
async def test_index_blocks_two_verified_rows_with_the_same_address(
    db_session,
) -> None:
    """NEGATIVE: uniqueness binds once an address is proven."""
    from sqlalchemy.exc import IntegrityError

    now = dt.datetime.now(dt.UTC)
    for _ in range(2):
        db_session.add(
            User(
                username=f"reader-{uuid.uuid4().hex[:10]}",
                email="shared@example.com",
                email_verified_at=now,
            ),
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_index_releases_the_address_when_the_account_is_soft_deleted(
    db_session,
) -> None:
    """deleted_at is in the predicate so an account cannot tombstone an address."""
    now = dt.datetime.now(dt.UTC)
    db_session.add(
        User(
            username=f"reader-{uuid.uuid4().hex[:10]}",
            email="shared@example.com",
            email_verified_at=now,
            deleted_at=now,
        ),
    )
    db_session.add(
        User(
            username=f"reader-{uuid.uuid4().hex[:10]}",
            email="shared@example.com",
            email_verified_at=now,
        ),
    )

    await db_session.flush()  # must not raise
    await db_session.rollback()


# --------------------------------------------------------------------------
# Withdrawal
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_clears_all_three_fields_and_invalidates_tokens(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    await client.post("/v1/me/email/verify", headers=headers, json={"token": sender.last_token})
    await _clear_cooldowns()
    await _capture(client, headers, "next@example.com")
    outstanding = sender.last_token

    response = await client.delete("/v1/me/email", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"email": None, "email_verified": False, "pending_email": None}

    refreshed = await db_session.get(User, user.id)
    await db_session.refresh(refreshed)
    assert refreshed.email is None
    assert refreshed.email_verified_at is None
    assert refreshed.pending_email is None

    live = await db_session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.invalidated_at.is_(None),
        ),
    )
    assert live is None

    # NEGATIVE: the outstanding link cannot resurrect the address afterwards.
    replay = await client.post("/v1/me/email/verify", headers=headers, json={"token": outstanding})
    assert replay.status_code == 400


# --------------------------------------------------------------------------
# The off-switch
# --------------------------------------------------------------------------


def test_off_switch_selects_the_disabled_sender() -> None:
    assert not get_settings().EMAIL_SENDING_ENABLED
    assert isinstance(get_email_sender(), DisabledEmailSender)


@pytest.mark.asyncio
async def test_off_switch_makes_a_network_call_impossible(monkeypatch, db_session) -> None:
    """Structural, not incidental: httpx is booby-trapped for this test.

    If ANY path could reach the transport with sending disabled, this fails.
    """
    import app.email.sender as sender_module

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("a network call was attempted with EMAIL_SENDING_ENABLED off")

    monkeypatch.setattr(sender_module.httpx, "AsyncClient", explode)

    from app.main import create_app

    app = create_app()  # no dependency override: the real get_email_sender runs
    transport = ASGITransport(app=app)
    user = await make_user(db_session)
    async with AsyncClient(transport=transport, base_url="https://testserver") as http:
        response = await _capture(http, auth_headers(user), "dev@example.com")

    assert response.status_code == 200
    assert response.json()["pending_email"] == "dev@example.com"


@pytest.mark.asyncio
async def test_resend_client_validates_its_key_lazily_at_first_send(monkeypatch) -> None:
    """NEGATIVE for the D-44 pattern: a missing key must NOT break Settings, and
    must fail only when a send is actually attempted."""
    monkeypatch.setenv("RESEND_API_KEY", "")
    get_settings.cache_clear()

    get_settings()  # constructing Settings with no key is fine

    with pytest.raises(EmailSendError):
        await ResendEmailSender().send(
            OutboundEmail(to="dev@example.com", subject="s", text="t", html="<p>t</p>"),
        )
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resend_client_refuses_header_injection_before_transport(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM", "CodeReader <no-reply@example.com>")
    get_settings.cache_clear()

    import app.email.sender as sender_module

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("reached the transport with a poisoned header")

    monkeypatch.setattr(sender_module.httpx, "AsyncClient", explode)

    with pytest.raises(EmailSendError):
        await ResendEmailSender().send(
            OutboundEmail(
                to="dev@example.com\r\nBcc: victim@example.com",
                subject="s",
                text="t",
                html="<p>t</p>",
            ),
        )
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Address validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "dev@example.com",
        "  Dev.Reader+tag@Example.co.uk  ",
        "a@b.io",
    ],
)
def test_valid_addresses_normalize(value: str) -> None:
    assert normalize_email(value) == value.strip().lower()


@pytest.mark.parametrize(
    "value",
    [
        "dev@example.com\r\nBcc: victim@example.com",  # CRLF header injection
        "dev@example.com\nBcc: victim@example.com",  # bare LF
        "dev\r@example.com",  # bare CR
        "dev\x00@example.com",  # NUL
        "dev\texample@example.com",  # tab
        "dev @example.com",  # interior space
        "dev@example",  # single-label domain
        "dev@example.",  # trailing dot
        "dev@.example.com",  # empty label
        "@example.com",  # no local part
        "dev@",  # no domain
        "dev..reader@example.com",  # consecutive dots
        ".dev@example.com",  # leading dot
        '"dev"@example.com',  # quoted local part: legal RFC, rejected here
        "dev@[192.168.0.1]",  # domain literal
        "",
        "   ",
        "a" * 250 + "@example.com",  # too long
    ],
)
def test_hostile_or_malformed_addresses_are_rejected(value: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(value)


@pytest.mark.asyncio
async def test_api_rejects_header_injection_with_a_validation_error(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)

    response = await _capture(
        client, auth_headers(user), "dev@example.com\r\nBcc: victim@example.com"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert sender.sent == []
    refreshed = await db_session.get(User, user.id)
    await db_session.refresh(refreshed)
    assert refreshed.pending_email is None


# --------------------------------------------------------------------------
# GET /me exposure
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_exposes_the_three_email_fields_and_nothing_more(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _capture(client, headers, "dev@example.com")
    await client.post("/v1/me/email/verify", headers=headers, json={"token": sender.last_token})

    body = (await client.get("/v1/me", headers=headers)).json()["user"]

    assert body["email"] == "dev@example.com"
    assert body["email_verified"] is True
    assert body["pending_email"] is None
    # The allowlist is the security boundary (invariant 2): ops data stays out.
    assert "email_verified_at" not in body
    assert "token" not in body and "token_hash" not in body


@pytest.mark.asyncio
async def test_email_verified_never_disagrees_with_email(
    client: AsyncClient, db_session, sender: RecordingSender
) -> None:
    """D-120(6) carries both fields deliberately; a test keeps them consistent."""
    user = await make_user(db_session)
    headers = auth_headers(user)

    before = (await client.get("/v1/me", headers=headers)).json()["user"]
    assert (before["email"] is not None) == before["email_verified"]
    assert before["email"] is None and before["email_verified"] is False

    await _capture(client, headers, "dev@example.com")
    pending = (await client.get("/v1/me", headers=headers)).json()["user"]
    assert pending["email"] is None and pending["email_verified"] is False

    await client.post("/v1/me/email/verify", headers=headers, json={"token": sender.last_token})
    after = (await client.get("/v1/me", headers=headers)).json()["user"]
    assert (after["email"] is not None) == after["email_verified"]


@pytest.mark.asyncio
async def test_patch_me_cannot_set_an_email(client: AsyncClient, db_session) -> None:
    """Email must not have a second, unverified way in."""
    user = await make_user(db_session)

    response = await client.patch(
        "/v1/me", headers=auth_headers(user), json={"email": "dev@example.com"}
    )

    assert response.status_code == 400
    refreshed = await db_session.get(User, user.id)
    await db_session.refresh(refreshed)
    assert refreshed.email is None and refreshed.pending_email is None


@pytest.mark.asyncio
async def test_email_routes_require_authentication(client: AsyncClient) -> None:
    for method, path in (
        ("post", "/v1/me/email"),
        ("post", "/v1/me/email/verify"),
        ("post", "/v1/me/email/resend"),
        ("delete", "/v1/me/email"),
    ):
        # client.request(), not client.delete(): httpx's delete() convenience
        # takes no body.
        response = await client.request(method, path, json={"email": "a@b.io", "token": "x"})
        assert response.status_code == 401, path
