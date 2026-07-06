from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str


@dataclass(frozen=True)
class GithubToken:
    access_token: str
    scope: str | None


@dataclass(frozen=True)
class GithubUserProfile:
    id: str
    login: str
    name: str | None
    avatar_url: str | None


class GithubClient(Protocol):
    async def exchange_code(self, *, code: str, code_verifier: str) -> GithubToken: ...

    async def fetch_profile(self, *, access_token: str) -> GithubUserProfile: ...


def create_pkce_pair() -> PkcePair:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(verifier=verifier, challenge=challenge)


def create_state() -> str:
    return secrets.token_urlsafe(32)


def authorize_url(*, state: str, code_challenge: str, settings: Settings) -> str:
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "read:user",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


class HttpGithubClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def exchange_code(self, *, code: str, code_verifier: str) -> GithubToken:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.GITHUB_CLIENT_ID,
                    "client_secret": self._settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": self._settings.GITHUB_REDIRECT_URI,
                    "code_verifier": code_verifier,
                },
            )
            response.raise_for_status()
        body = response.json()
        return GithubToken(access_token=body["access_token"], scope=body.get("scope"))

    async def fetch_profile(self, *, access_token: str) -> GithubUserProfile:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GITHUB_USER_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            response.raise_for_status()
        body = response.json()
        return GithubUserProfile(
            id=str(body["id"]),
            login=body["login"],
            name=body.get("name"),
            avatar_url=body.get("avatar_url"),
        )


def get_github_client() -> GithubClient:
    return HttpGithubClient(get_settings())