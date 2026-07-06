from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.core.errors import ApiError, api_error_handler, error_body, request_id
from app.db import create_engine, create_session_factory
from app.users.router import router as users_router


async def _check_postgres(settings: Settings) -> None:
    connection = await asyncpg.connect(settings.DATABASE_URL)
    try:
        await connection.execute("SELECT 1")
    finally:
        await connection.close()


async def _check_redis(settings: Settings) -> None:
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _collect_failures(
    checks: dict[str, Callable[[Settings], Awaitable[None]]],
    settings: Settings,
) -> list[str]:
    failures: list[str] = []
    for name, check in checks.items():
        try:
            await check(settings)
        except Exception:
            failures.append(name)
    return failures


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Code Reader API", lifespan=lifespan)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or (
            f"req_{uuid.uuid4().hex[:12]}"
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_exception_handler(ApiError, api_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_body(
                "validation_error",
                "Request validation failed.",
                request_id(request),
            ),
        )

    @app.get("/healthz")
    async def healthz():
        settings = get_settings()
        failures = await _collect_failures(
            {"postgres": _check_postgres, "redis": _check_redis},
            settings,
        )
        if failures:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "dependencies": failures},
            )
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(users_router)
    return app


app = create_app()