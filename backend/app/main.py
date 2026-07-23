from __future__ import annotations

import asyncio
import contextvars
import logging
import re
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

from app.admin.router import router as admin_router
from app.attempts.router import router as attempts_router
from app.auth.router import router as auth_router
from app.auth.tokens import TokenError, verify_access_token
from app.config import Settings, get_settings
from app.core.errors import ApiError, api_error_handler, error_body, request_id
from app.core.network import resolve_client_ip
from app.core.ratelimit import check_token_bucket
from app.core.sentry import init_sentry
from app.db import asyncpg_connect_kwargs, create_engine, create_session_factory
from app.disputes.router import router as disputes_router
from app.email.router import router as email_router
from app.jobs.runner import build_scheduler
from app.reviews.router import router as reviews_router
from app.sessions.router import router as sessions_router
from app.streak.router import router as streak_router
from app.users.router import router as users_router

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)

# A client-supplied X-Request-ID is only honored if it matches this strict
# shape; anything else is replaced with a server-generated id. This closes a
# log-injection / correlation-spoofing hole: the request_id is written verbatim
# into every structured log line (and a Sentry tag), so an unsanitized client
# value could forge log fields (spaces, newlines, `key=value`) or impersonate
# another request's id. A trusted upstream can still propagate a well-formed
# trace id.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _resolve_request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID")
    if supplied and _SAFE_REQUEST_ID.match(supplied):
        return supplied
    return f"req_{uuid.uuid4().hex[:12]}"


class _RequestIdLogFilter(logging.Filter):
    """Attaches the current request's id to every log record emitted while
    handling it, so app logs can be correlated end to end with a single
    request_id -- the same value returned to the client in error bodies and
    set as a Sentry tag."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


def _configure_structured_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        # No-op when the runtime already configured handlers (pytest,
        # gunicorn log config); under bare uvicorn this makes app INFO logs
        # -- notably each periodic job tick -- visible in the server output.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s",
        )
    root.setLevel(logging.INFO)
    for handler in root.handlers:
        handler.addFilter(_RequestIdLogFilter())


async def _check_postgres(settings: Settings) -> None:
    # NOT asyncpg.connect(settings.DATABASE_URL): asyncpg's DSN parser rejects
    # the `postgresql+asyncpg://` scheme outright, so a deploy whose
    # DATABASE_URL names the driver -- the form create_async_engine() requires
    # -- would have reported postgres permanently unhealthy here, and
    # _collect_failures() would have swallowed the reason (D-112).
    # 5s timeout: Neon free tier cold-starts can take several seconds. Without
    # a bound, the healthz probe hangs indefinitely and FastAPI Cloud marks the
    # deployment verifying_failed before the DB ever wakes up.
    connection = await asyncio.wait_for(
        asyncpg.connect(**asyncpg_connect_kwargs(settings.DATABASE_URL)),
        timeout=5.0,
    )
    try:
        await asyncio.wait_for(connection.execute("SELECT 1"), timeout=5.0)
    finally:
        await connection.close()


async def _check_redis(settings: Settings) -> None:
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=5.0)
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
    _configure_structured_logging()
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


_DEFAULT_RATE_LIMIT_EXEMPT_PREFIXES = ("/v1/auth", "/v1/debug")
_DEFAULT_RATE_LIMIT_EXEMPT_PATHS = ("/healthz",)


def _needs_default_rate_limit(request: Request) -> bool:
    """docs/05 section 1: default 60/min applies to every route except the
    ones with their own more specific limit -- auth (10/min per IP,
    self-enforced in auth/router.py). POST /attempts has a stricter 10/min
    PER-USER limit (attempts/service.py) but that runs AFTER auth, so an
    UNAUTHENTICATED flood of it would hit no limiter at all (M1); it is NOT
    exempted here -- the middleware applies the default IP limit to it for
    unauthenticated requests and defers to the per-user limit for authenticated
    ones (see default_rate_limit). Everything else (sessions, me, disputes, GET
    /attempts/{id}, /admin/*) is covered here too.
    """
    if request.method == "OPTIONS":
        return False
    path = request.url.path
    if path in _DEFAULT_RATE_LIMIT_EXEMPT_PATHS:
        return False
    if path.startswith(_DEFAULT_RATE_LIMIT_EXEMPT_PREFIXES):
        return False
    return True


def _resolve_default_rate_limit_identity(request: Request, settings: Settings) -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            claims = verify_access_token(token, settings.jwt_secrets)
        except TokenError:
            pass
        else:
            return f"user:{claims.sub}"
    return f"ip:{resolve_client_ip(request, settings.TRUSTED_PROXY_COUNT)}"


async def _middleware_redis(request: Request, settings: Settings) -> tuple[Redis, bool]:
    existing = getattr(request.app.state, "redis", None)
    if existing is not None:
        return existing, False
    return Redis.from_url(settings.REDIS_URL, decode_responses=True), True


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # This backend only ever serves JSON, never HTML/script -- 'none'
    # everywhere is the correct, maximally strict policy for it. The SPA
    # itself is served from a separate static host (docs/03: Caddy) which
    # needs its own CSP tuned to its actual script/style/connect sources;
    # that host config lives outside this repo (see docs/ops-runbook.md).
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
_HSTS_HEADER = "max-age=63072000; includeSubDomains; preload"


def _unhandled_response(request: Request, exc: Exception) -> JSONResponse:
    """The one 500 body (D-121).

    Shared by the innermost catch-all middleware and the app-level
    exception_handler so the two paths cannot drift into producing different
    shapes for the same failure. The exception is NEVER leaked to the client:
    a fixed generic message only, with the traceback going to the server log
    and Sentry.
    """
    req_id = request_id(request)
    logging.getLogger("app").error(
        "unhandled exception",
        exc_info=exc,
        extra={"request_id": req_id},
    )
    response = JSONResponse(
        status_code=500,
        content=error_body("internal", "Something went wrong.", req_id),
    )
    response.headers["X-Request-ID"] = req_id
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if get_settings().SENTRY_ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", _HSTS_HEADER)
    return response


def create_app() -> FastAPI:
    settings = get_settings()
    init_sentry(settings)

    app = FastAPI(title="Reedkode API", lifespan=lifespan)

    # D-121. REGISTERED FIRST ON PURPOSE, WHICH MAKES IT THE INNERMOST USER
    # MIDDLEWARE: Starlette's add_middleware prepends, so the last thing added
    # is outermost. Being inside CORSMiddleware is the entire point.
    #
    # An unhandled exception used to propagate past every user middleware up to
    # ServerErrorMiddleware, which is outside CORS. The 500 it produced carried
    # no Access-Control-Allow-Origin, so a browser refused to expose the
    # response to JS at all. The client did not see a 500 with a readable body;
    # it saw a failed fetch, and api.ts reported "Could not reach the server" --
    # a network error that was not a network error. Two separate incidents were
    # misdiagnosed off the back of that (D-119's seeded-session race, and the
    # mid-session "Something went wrong" in the July 2026 report).
    #
    # Catching here instead means the JSON error response travels back OUT
    # through CORSMiddleware, which applies the real origin-allowlist logic.
    # Note what this deliberately does NOT do: echo the request's Origin header
    # itself. Hand-rolling that would turn an error path into a CORS bypass for
    # any origin. Let the middleware that already owns the allowlist decide.
    @app.middleware("http")
    async def _catch_unhandled(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 -- deliberate catch-all
            return _unhandled_response(request, exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_ORIGINS,
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
        # M3: never trust a client-supplied X-Request-ID verbatim -- sanitize
        # it (or generate a fresh one) before it reaches logs or Sentry.
        request.state.request_id = _resolve_request_id(request)
        # Safe to call unconditionally: a no-op when Sentry was never
        # initialized (no SENTRY_DSN). Lets a user-reported request_id be
        # looked up directly in Sentry.
        sentry_sdk.set_tag("request_id", request.state.request_id)
        token = _request_id_ctx.set(request.state.request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        # Added before default_rate_limit so it wraps it (Starlette nests
        # in add-order, outermost first): a 429 short-circuit from the rate
        # limiter still passes back through here and gets these headers,
        # not just 2xx content responses.
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if get_settings().SENTRY_ENVIRONMENT == "production":
            response.headers.setdefault("Strict-Transport-Security", _HSTS_HEADER)
        return response

    @app.middleware("http")
    async def default_rate_limit(request: Request, call_next):
        if not _needs_default_rate_limit(request):
            return await call_next(request)
        current_settings = get_settings()
        identity = _resolve_default_rate_limit_identity(request, current_settings)
        # M1: POST /attempts self-enforces a stricter per-USER limit after auth.
        # For an AUTHENTICATED request (identity is user-based) defer to that and
        # don't double-limit here; for an UNAUTHENTICATED one (identity is
        # ip-based -- a missing/garbage token) apply the default IP limit below,
        # so an anonymous flood of the write endpoint is actually capped.
        if (
            request.method == "POST"
            and request.url.path == "/v1/attempts"
            and identity.startswith("user:")
        ):
            return await call_next(request)
        redis, ephemeral = await _middleware_redis(request, current_settings)
        try:
            result = await check_token_bucket(
                redis,
                key=f"rl:default:{identity}",
                limit=current_settings.RATE_LIMIT_DEFAULT_PER_MINUTE,
            )
        finally:
            if ephemeral:
                await redis.aclose()
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content=error_body("rate_limited", "Too many requests.", request_id(request)),
                headers=result.headers,
            )
        response = await call_next(request)
        for header, value in result.headers.items():
            response.headers[header] = value
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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # M2: an unhandled exception used to fall through to Starlette's default
        # plain-text "Internal Server Error" -- no uniform JSON body, no
        # request_id for a user to quote to support, and (that path being
        # outside the header middlewares) no security headers. Restore all
        # three here. The exception is NEVER leaked to the client: a fixed
        # generic message only; the traceback goes to the server log (below)
        # and Sentry, never the response body.
        #
        # D-121: this handler is registered on the app, so Starlette invokes it
        # from ServerErrorMiddleware, which sits OUTSIDE every user middleware
        # including CORSMiddleware. Responses built here therefore never got
        # CORS headers, and a browser could not read the 500 as a 500. That is
        # why `_catch_unhandled` below exists and why it is the innermost
        # middleware. This stays as the last-resort net for anything raised in
        # the outer middlewares themselves, where CORS is genuinely out of
        # reach.
        return _unhandled_response(request, exc)

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
    app.include_router(email_router)
    app.include_router(sessions_router)
    app.include_router(attempts_router)
    app.include_router(disputes_router)
    app.include_router(reviews_router)
    app.include_router(streak_router)
    app.include_router(admin_router)
    return app


app = create_app()
