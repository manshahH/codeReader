from __future__ import annotations

import inspect
import logging
import ssl
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


_ASYNCPG_DRIVER = "postgresql+asyncpg"

# Schemes a managed Postgres may hand out. All three mean the same thing here.
_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql", "postgresql+asyncpg"})

# libpq's sslmode vocabulary. asyncpg parses the first three itself when they
# arrive as a plain string on its `ssl` kwarg. The two verify-* modes it only
# "accepts": it goes looking for ~/.postgresql/root.crt and raises
# ClientConfigurationError when that file is absent, which it always is in a
# container. Those we turn into a real SSLContext (see _ssl_connect_arg).
_SSL_STRING_MODES = frozenset({"allow", "prefer", "require"})
_SSL_VERIFY_MODES = frozenset({"verify-ca", "verify-full"})
_SSL_DISABLE_MODES = frozenset({"disable", "false", "0"})

# Hostname markers for a PgBouncer transaction pooler (Neon's `-pooler`,
# Supabase's `.pooler.`).
_POOLER_MARKERS = ("-pooler.", ".pooler.", "pgbouncer")


@lru_cache(maxsize=1)
def _asyncpg_query_params() -> frozenset[str]:
    """Query params that survive the trip into asyncpg.connect().

    SQLAlchemy's asyncpg dialect forwards every URL query param to
    asyncpg.connect() verbatim -- create_connect_args() is a bare
    `opts.update(url.query)` with no translation -- so a param outside this set
    is not ignored, it is `TypeError: connect() got an unexpected keyword
    argument '<name>'` from inside the pool on the first request.

    Derived from the live signature rather than hardcoded: a denylist of known
    libpq params would be wrong the day a provider emits a new one, and wrong
    in exactly the silent way this function exists to prevent.
    """
    params = set(inspect.signature(asyncpg.connect).parameters)
    params.discard("kwargs")
    # Consumed by SQLAlchemy's dialect itself; never reaches asyncpg.connect().
    params |= {"prepared_statement_cache_size", "async_fallback"}
    return frozenset(params)


def _is_local_host(host: str) -> bool:
    """A loopback address, or a bare name with no dot in it.

    The no-dot rule is deliberate: docker-compose reaches Postgres at the
    service name `postgres`, and that container speaks no TLS. Every managed
    provider (Neon, Supabase, RDS) is a dotted FQDN, so this splits cleanly
    without a provider list.
    """
    return host in {"", "localhost", "127.0.0.1", "::1"} or "." not in host


def _resolve_ssl(sslmode: str) -> tuple[str | None, Any]:
    """Map an sslmode to (url_param, connect_arg); exactly one is ever set.

    The modes asyncpg can parse from a plain string stay IN the URL, so the
    normalized URL keeps describing its own TLS posture (and normalizing twice
    is a no-op). Only the verify-* modes have to become a connect_arg, because
    those are the ones asyncpg cannot honour as a string.
    """
    if sslmode in _SSL_DISABLE_MODES:
        return "disable", None
    if sslmode in _SSL_STRING_MODES:
        # NB `require` encrypts but does NOT authenticate the server:
        # check_hostname=False, verify_mode=CERT_NONE. That is libpq's meaning
        # of the word, and an operator who asks for it gets it.
        return sslmode, None
    if sslmode in _SSL_VERIFY_MODES:
        # check_hostname=True, verify_mode=CERT_REQUIRED, OS trust store.
        return None, ssl.create_default_context()
    raise ValueError(
        f"unrecognised sslmode {sslmode!r} in DATABASE_URL; expected one of: "
        "disable, allow, prefer, require, verify-ca, verify-full"
    )


def normalize_database_url(database_url: str) -> tuple[str, dict[str, Any]]:
    """Turn any managed-Postgres connection URL into (asyncpg URL, connect_args).

    Accepts a provider's libpq URL verbatim, e.g. Neon's

        postgresql://u:p@ep-x.us-east-1.aws.neon.tech/neondb
            ?sslmode=require&channel_binding=require

    and returns something asyncpg will actually connect with. See D-112: a
    deploy that depends on a human hand-editing the connection string is a
    deploy that breaks at 2am, and it breaks with a TypeError that names
    neither the URL nor the offending parameter.
    """
    parts = urlsplit(database_url)
    scheme = parts.scheme.lower()
    if scheme not in _POSTGRES_SCHEMES:
        raise ValueError(
            f"DATABASE_URL has unsupported scheme {parts.scheme!r}; expected one of: "
            + ", ".join(sorted(_POSTGRES_SCHEMES))
        )

    accepted = _asyncpg_query_params()
    connect_args: dict[str, Any] = {}
    kept: list[tuple[str, str]] = []
    dropped: list[str] = []
    sslmode: str | None = None
    force_pooler = False

    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key in ("sslmode", "ssl"):
            # Intercepted even though `ssl` IS an asyncpg kwarg: a bare
            # ssl=verify-full string is the one value asyncpg cannot honour.
            sslmode = value.strip().lower()
        elif key == "pgbouncer":
            # Not an asyncpg param, but the Prisma/Supabase convention for
            # declaring a transaction pooler. Honour it instead of dropping it.
            force_pooler = value.strip().lower() in ("true", "1", "yes")
        elif key in accepted:
            kept.append((key, value))
        else:
            dropped.append(key)

    host = (parts.hostname or "").lower()

    if sslmode is not None:
        ssl_param, ssl_connect_arg = _resolve_ssl(sslmode)
        if ssl_param is not None:
            kept.append(("ssl", ssl_param))
        else:
            connect_args["ssl"] = ssl_connect_arg
    elif not _is_local_host(host):
        # A remote host with no SSL setting at all. Verify, rather than send
        # credentials across the public internet in the clear (D-112).
        connect_args["ssl"] = ssl.create_default_context()

    is_pooler = force_pooler or any(marker in host for marker in _POOLER_MARKERS)
    if is_pooler:
        # PgBouncer in transaction mode gives each transaction a different
        # backend, so a prepared statement created on one is gone by the next
        # (InvalidSQLStatementNameError: prepared statement "__asyncpg_stmt_1__"
        # does not exist). Both caches have to go: asyncpg's own, and
        # SQLAlchemy's dialect-level one. Disabling either alone still fails,
        # so neither is left to an operator's explicit value here -- against a
        # transaction pooler, any non-zero setting is simply wrong.
        connect_args["statement_cache_size"] = 0
        kept = [(k, v) for k, v in kept if k != "prepared_statement_cache_size"]
        kept.append(("prepared_statement_cache_size", "0"))
        logger.info(
            "DATABASE_URL: host %r looks like a transaction pooler; disabled prepared "
            "statement caching (asyncpg + SQLAlchemy dialect)",
            host,
        )

    if dropped:
        # Named, not silent: this is the difference between a one-line log and
        # an afternoon staring at a TypeError from inside a connection pool.
        logger.warning(
            "DATABASE_URL: dropped %d query param(s) asyncpg cannot accept: %s",
            len(dropped),
            ", ".join(sorted(set(dropped))),
        )

    # netloc is passed through untouched, so a percent-encoded password with
    # special characters in it survives the round trip.
    url = urlunsplit(
        (_ASYNCPG_DRIVER, parts.netloc, parts.path, urlencode(kept), parts.fragment)
    )
    return url, connect_args


def sqlalchemy_database_url(database_url: str) -> str:
    """The URL half of normalize_database_url(), for callers with no engine."""
    return normalize_database_url(database_url)[0]


def asyncpg_connect_kwargs(database_url: str) -> dict[str, Any]:
    """Kwargs for a direct asyncpg.connect(), bypassing SQLAlchemy entirely.

    DATABASE_URL cannot simply be handed to asyncpg.connect() as a DSN, in
    EITHER of its plausible forms, which is why this exists (D-112):

      - once it carries the driver, asyncpg's DSN parser rejects it outright:
        `invalid DSN: scheme is expected to be either "postgresql" or
        "postgres", got 'postgresql+asyncpg'`;
      - and a raw libpq DSN, which the parser does accept, is the form that
        makes create_async_engine() fail instead.

    So there is no single string that satisfies both callers. Deriving the
    kwargs from the same normalizer the engine uses is what makes the health
    check probe the connection settings the app actually runs with, rather than
    a second, subtly different interpretation of the same env var.
    """
    url, connect_args = normalize_database_url(database_url)
    _, opts = PGDialect_asyncpg().create_connect_args(make_url(url))
    opts.update(connect_args)
    # Owned by SQLAlchemy's DBAPI shim; asyncpg.connect() has no such params.
    for shim_owned in (
        "async_fallback",
        "async_creator_fn",
        "prepared_statement_cache_size",
        "prepared_statement_name_func",
    ):
        opts.pop(shim_owned, None)
    return opts


def create_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    url, connect_args = normalize_database_url(database_url or settings.DATABASE_URL)
    return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
