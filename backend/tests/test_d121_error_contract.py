"""D-121: a 500 must be readable BY THE BROWSER as a 500.

The defect: an unhandled exception propagated past every user middleware up to
Starlette's ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware. The 500 it
produced carried no Access-Control-Allow-Origin, so a browser refused to expose
the response to JS at all. The SPA did not see a 500 with a parseable body; it
saw a failed fetch, and api.ts reported "Could not reach the server. Check your
connection." -- a network error that was not a network error.

That is not a cosmetic problem. It cost two misdiagnoses: D-119's seeded-session
race (which presented as a network error for four steps of investigation) and
the mid-session "Something went wrong" in docs/ops-incident-report-july-2026.md.
An error that disguises itself as a vaguer error corrupts every incident report
downstream of it.

These tests fail without the innermost `_catch_unhandled` middleware: the body
assertion fails first (Starlette's plain-text "Internal Server Error" is not
JSON), and the CORS assertion fails right behind it.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.core.errors import ApiError
from app.main import create_app
from tests.factories_m4 import (
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
)


def _app_with_a_broken_route():
    """A route that raises the way a transient DB fault does: uncaught."""
    app = create_app()

    @app.get("/v1/_test/boom")
    async def boom():
        raise RuntimeError("simulated transient failure")

    @app.get("/v1/_test/api-error")
    async def api_error():
        raise ApiError(403, "exercise_not_in_session", "Not part of your session.")

    return app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=_app_with_a_broken_route())
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_unhandled_exception_returns_a_parseable_json_error_body(
    client: AsyncClient,
) -> None:
    response = await client.get("/v1/_test/boom")

    assert response.status_code == 500
    body = response.json()  # would raise on Starlette's plain-text default
    assert body["error"]["code"] == "internal"
    assert body["error"]["message"] == "Something went wrong."
    assert body["error"]["request_id"]


@pytest.mark.asyncio
async def test_unhandled_exception_carries_cors_headers(client: AsyncClient) -> None:
    """The load-bearing one: without this the browser cannot read the body above."""
    origin = get_settings().APP_ORIGIN

    response = await client.get("/v1/_test/boom", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_the_exception(
    client: AsyncClient,
) -> None:
    """NEGATIVE: fixing the contract must not turn 500s into an info leak."""
    response = await client.get("/v1/_test/boom", headers={"Origin": get_settings().APP_ORIGIN})

    raw = response.text
    assert "simulated transient failure" not in raw
    assert "RuntimeError" not in raw
    assert "Traceback" not in raw


@pytest.mark.asyncio
async def test_unhandled_exception_keeps_its_security_headers(
    client: AsyncClient,
) -> None:
    """The M2 guarantee must survive the D-121 restructure."""
    response = await client.get("/v1/_test/boom")

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_cors_is_not_bypassed_for_a_disallowed_origin_on_the_error_path(
    client: AsyncClient,
) -> None:
    """NEGATIVE, and the reason the fix does not hand-roll the header.

    Echoing the request's Origin back would make the 500 path a CORS bypass for
    any site on the internet. The allowlist must still decide.
    """
    response = await client.get("/v1/_test/boom", headers={"Origin": "https://evil.example"})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


@pytest.mark.asyncio
async def test_api_errors_still_carry_body_and_cors(client: AsyncClient) -> None:
    """Regression guard for the OTHER half of the incident report.

    HANDOFF attributes the mid-session "Something went wrong" to the 403
    exercise_not_in_session lacking an {error: ...} body. It does not lack one
    and never did (it is raised as ApiError, and test_m4_attempts has asserted
    its body since M4). This pins that shape so the claim cannot be re-derived,
    and checks the 403 is browser-readable too.
    """
    origin = get_settings().APP_ORIGIN

    response = await client.get("/v1/_test/api-error", headers={"Origin": origin})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "exercise_not_in_session"
    assert response.json()["error"]["request_id"]
    assert response.headers.get("access-control-allow-origin") == origin
