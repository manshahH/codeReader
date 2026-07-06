from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.auth.service as auth_service
from app.auth.oauth import GithubToken, GithubUserProfile, get_github_client
from app.auth.service import REFRESH_COOKIE_NAME
from app.auth.tokens import (
    decode_unverified_payload,
    issue_access_token,
    refresh_token_hash,
)
from app.config import get_settings
from app.core.security import decrypt_token
from app.main import create_app
from app.models import AuthIdentity, RefreshToken, User

KNOWN_GITHUB_TOKEN = "gho_known_test_token_secret"
TOKEN_ENC_KEY = "test-token-enc-key-32-byte-value"


@dataclass
class FlowResult:
    start: Response
    callback: Response
    refresh: Response
    me: Response
    state: str
    initial_refresh_token: str
    rotated_refresh_token: str
    access_token: str


class FakeGithubClient:
    def __init__(self) -> None:
        self.seen_verifiers: list[str] = []
        self.seen_access_tokens: list[str] = []

    async def exchange_code(self, *, code: str, code_verifier: str) -> GithubToken:
        self.seen_verifiers.append(code_verifier)
        assert code == "oauth-code"
        return GithubToken(access_token=KNOWN_GITHUB_TOKEN, scope="read:user")

    async def fetch_profile(self, *, access_token: str) -> GithubUserProfile:
        self.seen_access_tokens.append(access_token)
        return GithubUserProfile(
            id="1234567",
            login="octoreader",
            name="Octo Reader",
            avatar_url="https://avatars.example/octoreader.png",
        )


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-github-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-github-client-secret")
    monkeypatch.setenv("GITHUB_REDIRECT_URI", "https://api.example/v1/auth/github/callback")
    monkeypatch.setenv("TOKEN_ENC_KEY", TOKEN_ENC_KEY)
    monkeypatch.setenv("APP_ORIGIN", "https://app.example")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "10")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def clean_redis() -> None:
    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


@pytest.fixture
async def auth_client() -> AsyncClient:
    fake_github = FakeGithubClient()
    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: fake_github
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        client.fake_github = fake_github  # type: ignore[attr-defined]
        yield client


def _cookie_value(response: Response, name: str) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie[name].value


def _assert_known_github_token_absent(*responses: Response) -> None:
    for response in responses:
        assert KNOWN_GITHUB_TOKEN not in response.text
        assert KNOWN_GITHUB_TOKEN not in response.headers.get("location", "")
        assert KNOWN_GITHUB_TOKEN not in response.headers.get("set-cookie", "")


async def _oauth_flow(client: AsyncClient) -> FlowResult:
    start = await client.get("/v1/auth/github/start", follow_redirects=False)
    assert start.status_code == 302
    parsed_start = urlparse(start.headers["location"])
    params = parse_qs(parsed_start.query)
    assert parsed_start.netloc == "github.com"
    assert params["scope"] == ["read:user"]
    assert params["code_challenge_method"] == ["S256"]
    assert "code_challenge" in params
    state = params["state"][0]

    callback = await client.get(
        f"/v1/auth/github/callback?code=oauth-code&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "https://app.example"
    assert "access_token" not in callback.headers["location"]
    initial_refresh_token = _cookie_value(callback, REFRESH_COOKIE_NAME)

    refresh = await client.post("/v1/auth/refresh")
    assert refresh.status_code == 200
    body = refresh.json()
    access_token = body["access_token"]
    rotated_refresh_token = _cookie_value(refresh, REFRESH_COOKIE_NAME)

    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    return FlowResult(
        start=start,
        callback=callback,
        refresh=refresh,
        me=me,
        state=state,
        initial_refresh_token=initial_refresh_token,
        rotated_refresh_token=rotated_refresh_token,
        access_token=access_token,
    )


@pytest.mark.asyncio
async def test_full_oauth_flow_with_mocked_github_creates_rows_and_authenticates(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    flow = await _oauth_flow(auth_client)

    assert flow.me.json()["user"]["username"] == "octoreader"
    users = (await db_session.scalars(select(User).where(User.username == "octoreader"))).all()
    identities = (await db_session.scalars(select(AuthIdentity))).all()
    assert len(users) == 1
    assert len(identities) == 1
    assert identities[0].user_id == users[0].id
    assert identities[0].token_scopes == "read:user"
    assert auth_client.fake_github.seen_access_tokens == [KNOWN_GITHUB_TOKEN]  # type: ignore[attr-defined]
    _assert_known_github_token_absent(flow.start, flow.callback, flow.refresh, flow.me)


@pytest.mark.asyncio
async def test_oauth_state_is_single_use(auth_client: AsyncClient) -> None:
    flow = await _oauth_flow(auth_client)

    replay = await auth_client.get(
        f"/v1/auth/github/callback?code=oauth-code&state={flow.state}",
        follow_redirects=False,
    )

    assert replay.status_code == 302
    assert replay.headers["location"] == "https://app.example/login?error=oauth_state"
    _assert_known_github_token_absent(replay)


@pytest.mark.asyncio
async def test_github_token_is_encrypted_at_rest_and_never_in_auth_responses(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    flow = await _oauth_flow(auth_client)

    identity = await db_session.scalar(select(AuthIdentity))
    assert identity is not None
    assert identity.access_token_enc is not None
    assert identity.access_token_enc != KNOWN_GITHUB_TOKEN.encode("utf-8")
    assert KNOWN_GITHUB_TOKEN.encode("utf-8") not in identity.access_token_enc
    assert decrypt_token(identity.access_token_enc, TOKEN_ENC_KEY) == KNOWN_GITHUB_TOKEN
    _assert_known_github_token_absent(flow.start, flow.callback, flow.refresh, flow.me)


@pytest.mark.asyncio
async def test_refresh_rotates_token_same_family_and_marks_old_rotated(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    flow = await _oauth_flow(auth_client)

    rows = (await db_session.scalars(select(RefreshToken))).all()
    old_hash = refresh_token_hash(flow.initial_refresh_token)
    new_hash = refresh_token_hash(flow.rotated_refresh_token)
    old_row = next(row for row in rows if row.token_hash == old_hash)
    new_row = next(row for row in rows if row.token_hash == new_hash)
    assert old_row.family_id == new_row.family_id
    assert old_row.rotated_at is not None
    assert new_row.rotated_at is None

    second_refresh = await auth_client.post("/v1/auth/refresh")
    assert second_refresh.status_code == 200
    assert second_refresh.json()["access_token"] != flow.access_token


@pytest.mark.asyncio
async def test_refresh_reuse_returns_invalid_token_and_logs_alert(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = await _oauth_flow(auth_client)
    old_row = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == refresh_token_hash(flow.initial_refresh_token),
        ),
    )
    assert old_row is not None
    assert old_row.rotated_at is not None
    alert_events: list[dict[str, object]] = []

    def capture_alert(**event: object) -> None:
        alert_events.append(event)

    monkeypatch.setattr(auth_service, "alert_refresh_reuse", capture_alert)

    auth_client.cookies.clear()
    reuse = await auth_client.post(
        "/v1/auth/refresh",
        headers={"Cookie": f"{REFRESH_COOKIE_NAME}={flow.initial_refresh_token}"},
    )

    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "invalid_token"
    assert alert_events == [
        {
            "token_id": old_row.id,
            "family_id": old_row.family_id,
            "user_id": old_row.user_id,
            "request_id": alert_events[0]["request_id"],
        }
    ]


@pytest.mark.asyncio
async def test_access_jwt_claim_set_and_expired_token_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = User(username="expired-reader")
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()

    token = issue_access_token(
        user_id=user.id,
        secret=get_settings().jwt_secrets[0],
        ttl_seconds=get_settings().ACCESS_TOKEN_TTL,
        now=dt.datetime.now(dt.UTC),
    )
    assert len(token) < 400
    assert set(decode_unverified_payload(token)) == {"sub", "plan", "exp", "iat", "jti"}

    expired = issue_access_token(
        user_id=user.id,
        secret=get_settings().jwt_secrets[0],
        ttl_seconds=1,
        now=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30),
    )
    response = await auth_client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


@pytest.mark.asyncio
async def test_cookie_scope_does_not_authenticate_me_and_access_jwt_cannot_refresh(
    auth_client: AsyncClient,
) -> None:
    flow = await _oauth_flow(auth_client)

    cookie_only_me = await auth_client.get("/v1/me")
    assert cookie_only_me.status_code == 401
    assert cookie_only_me.json()["error"]["code"] == "invalid_token"

    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as no_cookie_client:
        refresh = await no_cookie_client.post(
            "/v1/auth/refresh",
            headers={"Authorization": f"Bearer {flow.access_token}"},
        )
    assert refresh.status_code == 401
    assert refresh.json()["error"]["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_auth_route_rate_limit_returns_429_with_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "2")
    get_settings.cache_clear()
    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()

    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        first = await client.get("/v1/auth/github/start", follow_redirects=False)
        second = await client.get("/v1/auth/github/start", follow_redirects=False)
        assert first.status_code == 302
        assert second.status_code == 302
        limited = await client.get("/v1/auth/github/start", follow_redirects=False)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["Retry-After"]
    assert limited.headers["X-RateLimit-Limit"] == "2"
    assert limited.headers["X-RateLimit-Remaining"] == "0"