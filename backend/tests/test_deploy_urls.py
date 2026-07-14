"""D-112: DATABASE_URL / REDIS_URL must accept what a managed provider hands out.

No real credentials anywhere in here. Hosts are shaped like Neon/Upstash ones
because the shape is what the normalizer keys off; the endpoint IDs are made up
and the passwords are the literal string "pw".
"""

from __future__ import annotations

import asyncio
import inspect
import ssl

import asyncpg
import pytest
from redis.asyncio import Redis
from redis.asyncio.connection import Connection, SSLConnection
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.engine import make_url

from app.db import asyncpg_connect_kwargs, normalize_database_url

# What Neon actually puts in the dashboard, unedited.
NEON_LIBPQ = (
    "postgresql://reader:pw@ep-fake-endpoint-a1b2c3d4.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)
NEON_POOLER_LIBPQ = (
    "postgresql://reader:pw@ep-fake-endpoint-a1b2c3d4-pooler.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)
# The hand-converted form (what a human writes when they know asyncpg wants `ssl`).
NEON_HAND_CONVERTED = (
    "postgresql+asyncpg://reader:pw@ep-fake-endpoint-a1b2c3d4.us-east-1.aws.neon.tech"
    "/neondb?ssl=require"
)


def assert_connectable(database_url: str) -> dict:
    """Assert asyncpg.connect() would accept this URL's kwargs, and return them.

    asyncpg_connect_kwargs() reproduces the real connect boundary: SQLAlchemy's
    asyncpg dialect forwards every URL query param into the DBAPI shim
    (create_connect_args -> `opts.update(url.query)`), the shim pops the four
    keys it owns, and hands the rest to asyncpg.connect(**kw). Binding those
    against the live signature is the whole point of this assertion: it fails on
    exactly the params (`sslmode`, `channel_binding`) that made an unedited Neon
    URL blow up inside the pool, and it keeps failing if a future asyncpg drops
    one.
    """
    opts = asyncpg_connect_kwargs(database_url)
    inspect.signature(asyncpg.connect).bind(**opts)  # raises TypeError if not
    return opts


# --------------------------------------------------------------------------
# The bug D-112 exists to kill: a provider's URL, pasted in unedited.
# --------------------------------------------------------------------------


def test_neon_libpq_url_is_accepted_verbatim() -> None:
    url, connect_args = normalize_database_url(NEON_LIBPQ)

    assert url.startswith("postgresql+asyncpg://")
    # The two params asyncpg has no kwarg for are gone from the URL...
    assert "sslmode" not in url
    assert "channel_binding" not in url
    # ...but the TLS requirement was translated, not silently discarded. `ssl`
    # is the spelling asyncpg understands, and it survives as a URL param
    # because asyncpg parses this one itself.
    assert "ssl=require" in url
    assert "ssl" not in connect_args

    assert assert_connectable(NEON_LIBPQ)["ssl"] == "require"


def test_unnormalized_neon_url_would_have_raised_typeerror() -> None:
    """The negative case, pinned: this is precisely what used to reach asyncpg.

    The OLD sqlalchemy_database_url() only rewrote the scheme, so `sslmode` and
    `channel_binding` sailed through into asyncpg.connect(). If this ever stops
    raising, asyncpg grew the kwargs and D-112's translation can be simplified.
    """
    old_behaviour = NEON_LIBPQ.replace("postgresql://", "postgresql+asyncpg://", 1)
    _, opts = PGDialect_asyncpg().create_connect_args(make_url(old_behaviour))

    assert opts["sslmode"] == "require"
    assert opts["channel_binding"] == "require"
    with pytest.raises(TypeError):
        inspect.signature(asyncpg.connect).bind(**opts)


def test_hand_converted_url_still_works() -> None:
    """The URL already sitting in the deploy env must keep working untouched."""
    assert_connectable(NEON_HAND_CONVERTED)
    url, _ = normalize_database_url(NEON_HAND_CONVERTED)
    assert "ssl=require" in url


@pytest.mark.parametrize(
    "database_url",
    [NEON_LIBPQ, NEON_POOLER_LIBPQ, NEON_HAND_CONVERTED, "postgres://u:pw@db.example.com/db"],
)
def test_normalizing_is_idempotent(database_url: str) -> None:
    """Normalizing an already-normalized URL must be a no-op.

    This is what keeps the URL self-describing: the sslmode an operator asked
    for stays visible in the string instead of vanishing into connect_args,
    where a second pass would silently re-derive a different (stronger) one.
    """
    once, once_args = normalize_database_url(database_url)
    twice, twice_args = normalize_database_url(once)

    assert twice == once
    assert sorted(twice_args) == sorted(once_args)


# --------------------------------------------------------------------------
# SSL posture
# --------------------------------------------------------------------------


def test_remote_host_without_sslmode_defaults_to_verified_tls() -> None:
    """No sslmode + a remote host must not mean cleartext over the internet."""
    _, connect_args = normalize_database_url(
        "postgresql://reader:pw@ep-fake.us-east-1.aws.neon.tech/neondb"
    )
    context = connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_verify_full_becomes_a_real_context_not_a_string() -> None:
    """asyncpg cannot honour the bare string: it hunts for ~/.postgresql/root.crt
    and raises ClientConfigurationError when it is missing, as it always is in a
    container. Only a prebuilt SSLContext actually verifies."""
    _, connect_args = normalize_database_url(
        "postgresql://reader:pw@ep-fake.us-east-1.aws.neon.tech/neondb?sslmode=verify-full"
    )
    context = connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_explicit_require_is_honoured_and_is_encrypt_only() -> None:
    """`require` is deliberately weaker than the default: it encrypts but does
    not authenticate the server. An operator asking for it gets it, and does not
    get silently upgraded to the verify-full default."""
    opts = assert_connectable(
        "postgresql://reader:pw@ep-fake.us-east-1.aws.neon.tech/db?sslmode=require"
    )
    assert opts["ssl"] == "require"
    assert not isinstance(opts["ssl"], ssl.SSLContext)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://codereader:codereader@localhost:5432/codereader",
        "postgresql://codereader:codereader@127.0.0.1:5432/codereader",
        # docker-compose.yml reaches Postgres at the service name. That
        # container speaks no TLS; demanding it here would break compose.
        "postgresql://codereader:codereader@postgres:5432/codereader",
    ],
)
def test_local_urls_get_no_ssl_and_still_normalize(database_url: str) -> None:
    url, connect_args = normalize_database_url(database_url)
    assert url.startswith("postgresql+asyncpg://")
    assert "ssl" not in connect_args


def test_sslmode_disable_is_honoured() -> None:
    """An explicit opt-out beats the remote-host verify-full default."""
    opts = assert_connectable("postgresql://reader:pw@db.example.com/db?sslmode=disable")
    assert opts["ssl"] == "disable"


# --------------------------------------------------------------------------
# PgBouncer transaction pooling
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "database_url",
    [
        NEON_POOLER_LIBPQ,
        "postgresql://reader:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
        "postgresql://reader:pw@db.example.com/db?pgbouncer=true",
    ],
)
def test_pooler_disables_both_statement_caches(database_url: str) -> None:
    """Transaction pooling hands each transaction a different backend, so a
    prepared statement made on one is gone by the next. BOTH caches must go:
    asyncpg's own AND SQLAlchemy's dialect cache. Disabling one is the common
    half-fix and it still raises InvalidSQLStatementNameError under load."""
    url, connect_args = normalize_database_url(database_url)

    assert connect_args["statement_cache_size"] == 0  # asyncpg's own cache
    assert "prepared_statement_cache_size=0" in url  # SQLAlchemy's dialect cache

    # And the dialect really does parse it back out as an int 0, not "0".
    _, opts = PGDialect_asyncpg().create_connect_args(make_url(url))
    assert opts["prepared_statement_cache_size"] == 0

    assert_connectable(database_url)


def test_direct_endpoint_keeps_prepared_statements() -> None:
    """The non-pooler host has no PgBouncer in front of it, so caching stays on:
    the pooler workaround is a real performance cost, not a free default."""
    url, connect_args = normalize_database_url(NEON_LIBPQ)
    assert "statement_cache_size" not in connect_args
    assert "prepared_statement_cache_size" not in url


# --------------------------------------------------------------------------
# Structure preservation and rejection of bad input
# --------------------------------------------------------------------------


def test_special_characters_in_password_survive() -> None:
    """netloc is passed through untouched, so a percent-encoded password does
    not get mangled into an auth failure that looks like a wrong secret."""
    url, _ = normalize_database_url(
        "postgresql://us%40er:p%2Fw%3As@ep-fake.us-east-1.aws.neon.tech:5432/db?sslmode=require"
    )
    assert "us%40er:p%2Fw%3As@" in url
    assert ":5432/db" in url
    assert make_url(url).password == "p/w:s"


def test_bare_postgres_scheme_is_accepted() -> None:
    """Some providers still emit the legacy `postgres://`. The old code did not
    rewrite it at all, so it reached SQLAlchemy as an unknown dialect."""
    url, _ = normalize_database_url("postgres://reader:pw@db.example.com/db?sslmode=require")
    assert url.startswith("postgresql+asyncpg://")


def test_unknown_libpq_params_are_dropped_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dropping must be loud. A silently-swallowed param is how you spend an
    afternoon wondering why a setting had no effect."""
    with caplog.at_level("WARNING", logger="app.db"):
        url, _ = normalize_database_url(
            "postgresql://reader:pw@db.example.com/db"
            "?sslmode=require&channel_binding=require&sslrootcert=/etc/ca.crt"
        )
    assert "channel_binding" not in url
    assert "sslrootcert" not in url
    assert "channel_binding" in caplog.text
    assert "sslrootcert" in caplog.text


def test_known_asyncpg_params_are_preserved() -> None:
    """The filter is an allowlist derived from asyncpg's signature, not a
    denylist of libpq names, so legitimate tuning params must survive it."""
    url, _ = normalize_database_url(
        "postgresql://reader:pw@db.example.com/db?sslmode=require&command_timeout=30"
    )
    assert "command_timeout=30" in url
    assert_connectable(
        "postgresql://reader:pw@db.example.com/db?sslmode=require&command_timeout=30"
    )


@pytest.mark.parametrize(
    "bad_url",
    [
        "mysql://reader:pw@db.example.com/db",
        "redis://localhost:6379/0",
        "https://db.example.com/db",
    ],
)
def test_non_postgres_scheme_is_rejected(bad_url: str) -> None:
    with pytest.raises(ValueError, match="unsupported scheme"):
        normalize_database_url(bad_url)


def test_unrecognised_sslmode_is_rejected() -> None:
    """Fail at boot with a message naming the parameter, rather than handing a
    junk value to asyncpg and getting a ClientConfigurationError from its guts."""
    with pytest.raises(ValueError, match="unrecognised sslmode"):
        normalize_database_url(
            "postgresql://reader:pw@db.example.com/db?sslmode=required"  # not a real mode
        )


# --------------------------------------------------------------------------
# The healthz probe (main.py _check_postgres) connects with asyncpg directly,
# NOT through SQLAlchemy, and the two have opposite requirements.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "database_url",
    [
        NEON_LIBPQ,
        NEON_POOLER_LIBPQ,
        NEON_HAND_CONVERTED,
        "postgresql://codereader:codereader@postgres:5432/codereader",
        "postgresql://codereader:codereader@localhost:5432/codereader",
    ],
)
def test_healthz_probe_kwargs_are_valid_for_every_url_form(database_url: str) -> None:
    """_check_postgres() must be able to connect for ANY form of DATABASE_URL
    the engine accepts, or readiness never goes green and _collect_failures()
    swallows the reason (it records only the check's name)."""
    opts = asyncpg_connect_kwargs(database_url)
    inspect.signature(asyncpg.connect).bind(**opts)
    assert opts["user"] and opts["host"] and opts["database"]


def test_raw_database_url_is_not_a_valid_asyncpg_dsn() -> None:
    """The negative test, and the reason asyncpg_connect_kwargs() exists.

    _check_postgres() used to do `asyncpg.connect(settings.DATABASE_URL)`,
    passing the env var straight through as a DSN. asyncpg's DSN parser knows
    only postgres:// and postgresql://, so the moment DATABASE_URL names the
    driver -- the exact form create_async_engine() requires -- that call dies.
    Together with test_unnormalized_neon_url_would_have_raised_typeerror this
    pins the trap: NO single string satisfies both the engine and the probe.
    """
    with pytest.raises(asyncpg.exceptions.ClientConfigurationError, match="scheme"):
        asyncio.run(asyncpg.connect(NEON_HAND_CONVERTED))


# --------------------------------------------------------------------------
# Redis: Upstash hands out rediss://. Confirm it needs no plumbing at all.
# --------------------------------------------------------------------------


def test_rediss_url_is_accepted_as_is_with_tls() -> None:
    """redis.asyncio maps the rediss:// scheme to SSLConnection natively, so an
    Upstash URL drops into core/redis.py unchanged. Pinned so nobody
    "helpfully" adds TLS plumbing that is not needed."""
    client = Redis.from_url("rediss://default:pw@fake-cat-12345.upstash.io:6379")
    pool = client.connection_pool

    assert pool.connection_class is SSLConnection
    assert pool.connection_kwargs["host"] == "fake-cat-12345.upstash.io"
    assert pool.connection_kwargs["port"] == 6379
    assert pool.connection_kwargs["password"] == "pw"


def test_plain_redis_url_stays_untrusted_free_of_tls() -> None:
    """The negative half: redis:// must NOT silently become TLS, or local
    compose and CI would fail to reach a plaintext Redis."""
    client = Redis.from_url("redis://localhost:6379/0")
    assert client.connection_pool.connection_class is Connection
    assert client.connection_pool.connection_kwargs["db"] == 0
