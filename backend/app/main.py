from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import asyncpg
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.attempts.router import router as attempts_router
from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.core.errors import ApiError, api_error_handler, error_body, request_id
from app.core.sentry import init_sentry
from app.db import create_engine, create_session_factory
from app.disputes.router import router as disputes_router
from app.jobs.runner import build_scheduler
from app.sessions.router import router as sessions_router
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
    # No-op when the runtime already configured handlers (pytest, gunicorn
    # log config); under bare uvicorn this makes app INFO logs -- notably
    # each periodic job tick -- visible in the server output.
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.job_scheduler = None
    if settings.JOBS_ENABLED:
        app.state.job_scheduler = build_scheduler(
            app.state.session_factory,
            app.state.redis,
            settings,
        )
        await app.state.job_scheduler.start()
    try:
        yield
    finally:
        if app.state.job_scheduler is not None:
            await app.state.job_scheduler.stop()
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    init_sentry(settings)

    app = FastAPI(title="Code Reader API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.APP_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
            "X-Idempotent-Replay",
            "X-Request-ID",
        ],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or (
            f"req_{uuid.uuid4().hex[:12]}"
        )
        # Safe to call unconditionally: a no-op when Sentry was never
        # initialized (no SENTRY_DSN). Lets a user-reported request_id be
        # looked up directly in Sentry.
        sentry_sdk.set_tag("request_id", request.state.request_id)
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

    if settings.SENTRY_ENVIRONMENT != "production":

        @app.get("/v1/debug/sentry-test")
        async def debug_sentry_test():
            raise RuntimeError("Sentry backend verification test exception")

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(sessions_router)
    app.include_router(attempts_router)
    app.include_router(disputes_router)
    return app


app = create_app()