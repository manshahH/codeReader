"""A3 reminders + weekly recap (docs/10; D-137).

Every gate here has a negative, per CLAUDE.md: a gate that cannot prove it
REJECTS a crafted bad input is not a gate. The gates are

  * only VERIFIED addresses are ever mailed          -> unverified / pending negatives
  * a period sends at most once                       -> aggressive-tick negative
  * a user who already practised is not reminded      -> practised-today negative
  * suppression is permanent and address-independent  -> survives-a-re-verify negative
  * a send failure leaves the period retryable        -> and does NOT double-send
  * the off-switch makes a network call impossible    -> structural, like A2's
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import create_engine, create_session_factory
from app.email.deliveries import claim_period, email_preferences, suppress
from app.email.messages import (
    BANNED_REMINDER_PHRASES,
    build_recap_email,
    build_reminder_email,
)
from app.email.recap import build_weekly_recap, week_bounds
from app.email.sender import (
    DisabledEmailSender,
    EmailSendError,
    OutboundEmail,
    get_email_sender,
)
from app.email.unsubscribe import (
    InvalidUnsubscribeToken,
    mint_unsubscribe_token,
    parse_unsubscribe_token,
)
from app.jobs.reminders import send_daily_reminders
from app.jobs.weekly_email import send_weekly_recaps
from app.models import User
from tests.factories_m4 import (  # noqa: F401
    auth_headers,
    clean_m4_tables,
    clean_redis,
    m4_env,
    make_user,
)

# --------------------------------------------------------------------------
# Doubles and helpers
# --------------------------------------------------------------------------


class RecordingSender:
    """Stands in for the provider. Records, never transports."""

    def __init__(self) -> None:
        self.sent: list[OutboundEmail] = []

    async def send(self, message: OutboundEmail) -> None:
        self.sent.append(message)


class FailingSender:
    """Always raises the DEFINITE failure the sweep knows how to record."""

    def __init__(self) -> None:
        self.attempts = 0

    async def send(self, message: OutboundEmail) -> None:
        self.attempts += 1
        raise EmailSendError("provider refused")


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    """A real factory, because the sweep opens a session PER RECIPIENT.

    The jobs cannot be handed the test's `db_session`: the whole point of
    D-137(3) is that the claim is committed in its own transaction before the
    send, so a shared, rolled-back session would not exercise the mechanism
    under test.

    Built with app.db's OWN create_engine, not a hand-rolled
    create_async_engine. Rolling one by hand skips normalize_database_url and,
    more importantly, pool_pre_ping -- and a pool with no pre-ping happily
    hands out a connection that was invalidated by something else in the
    session, which showed up here as later tests in this file failing on a
    foreign key to a user that demonstrably existed.
    """
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def make_verified_user(
    session: AsyncSession,
    *,
    email: str = "dev@example.com",
    timezone: str = "UTC",
    reminder: str | None = "08:00",
) -> User:
    user = await make_user(session, timezone=timezone)
    user.email = email
    user.email_verified_at = dt.datetime.now(dt.UTC)
    if reminder is not None:
        user.reminder_local_time = dt.time.fromisoformat(reminder)
    await session.commit()
    return user


async def ledger_rows(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, str, int]]:
    rows = await session.execute(
        text(
            "SELECT kind, status, attempts FROM email_deliveries "
            "WHERE user_id = :u ORDER BY kind, period_key",
        ),
        {"u": str(user_id)},
    )
    return [tuple(row) for row in rows.all()]


# 09:00 UTC on Tuesday 2026-07-21: past an 08:00 reminder, and NOT a Monday, so
# the reminder tests are never accidentally also recap tests.
TUESDAY_0900 = dt.datetime(2026, 7, 21, 9, 0, tzinfo=dt.UTC)
# 09:00 UTC on Monday 2026-07-20, which is the recap slot.
MONDAY_0900 = dt.datetime(2026, 7, 20, 9, 0, tzinfo=dt.UTC)


# --------------------------------------------------------------------------
# Gate 1: only verified addresses are ever mailed
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reminder_goes_to_a_verified_address(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    user = await make_verified_user(db_session)

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 1
    assert len(sender.sent) == 1
    assert sender.sent[0].to == "dev@example.com"
    assert await ledger_rows(db_session, user.id) == [("reminder", "sent", 1)]


@pytest.mark.asyncio
async def test_no_reminder_to_an_unverified_address(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. An address sitting in `email` with no `email_verified_at` is
    not deliverable, and the job must not take the column's presence as proof."""
    user = await make_user(db_session)
    user.email = "unverified@example.com"
    user.email_verified_at = None
    user.reminder_local_time = dt.time(8, 0)
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []
    assert await ledger_rows(db_session, user.id) == []


@pytest.mark.asyncio
async def test_no_reminder_to_a_pending_address(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. A pending address is one somebody TYPED, not one they proved
    they control. Mailing it would send someone else's reminder to a stranger."""
    user = await make_user(db_session)
    user.pending_email = "typo@example.com"
    user.reminder_local_time = dt.time(8, 0)
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []


@pytest.mark.asyncio
async def test_no_reminder_to_a_soft_deleted_user(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. A deleted account keeps its row; it must stop receiving mail."""
    user = await make_verified_user(db_session)
    user.deleted_at = dt.datetime.now(dt.UTC)
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []


# --------------------------------------------------------------------------
# Gate 2: the frequency ceiling
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_running_the_job_twice_sends_one_reminder(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    user = await make_verified_user(db_session)

    first = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)
    second = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert first["sent"] == 1
    # NEGATIVE: the second run finds the period already claimed and sends
    # nothing. `not_claimed` rather than `sent` is what proves the ledger did
    # it, rather than the candidate query happening to miss the user.
    assert second["sent"] == 0
    assert second["not_claimed"] == 1
    assert len(sender.sent) == 1
    assert await ledger_rows(db_session, user.id) == [("reminder", "sent", 1)]


@pytest.mark.asyncio
async def test_ceiling_holds_under_an_aggressive_tick(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """The ceiling is not "the scheduler is well behaved". Ten ticks inside one
    local day, at different times, still produce exactly one email."""
    user = await make_verified_user(db_session)

    for minute in range(0, 50, 5):
        await send_daily_reminders(
            session_factory, sender, now=TUESDAY_0900 + dt.timedelta(minutes=minute)
        )

    assert len(sender.sent) == 1
    assert await ledger_rows(db_session, user.id) == [("reminder", "sent", 1)]


@pytest.mark.asyncio
async def test_a_new_local_day_sends_again(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """The ceiling is per PERIOD, not forever. Without this, a passing
    send-once test could be satisfied by a job that never sends twice at all."""
    await make_verified_user(db_session)

    await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)
    await send_daily_reminders(
        session_factory, sender, now=TUESDAY_0900 + dt.timedelta(days=1)
    )

    assert len(sender.sent) == 2


@pytest.mark.asyncio
async def test_claim_period_is_atomic_and_single_winner(db_session: AsyncSession) -> None:
    """The ceiling at its lowest level: the same claim twice yields one True."""
    user = await make_verified_user(db_session)

    first = await claim_period(db_session, user.id, "reminder", "2026-07-21")
    await db_session.commit()
    second = await claim_period(db_session, user.id, "reminder", "2026-07-21")
    await db_session.commit()

    assert first is True
    assert second is False


# --------------------------------------------------------------------------
# Gate 3: nobody who already practised today is reminded
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reminder_when_already_practised_today(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. Reminding somebody to do the thing they already did is the
    single most obvious way to look broken."""
    user = await make_verified_user(db_session)
    await db_session.execute(
        text(
            "INSERT INTO user_stats (user_id, last_active_local_date) "
            "VALUES (:u, :d)",
        ),
        {"u": str(user.id), "d": TUESDAY_0900.date()},
    )
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []


@pytest.mark.asyncio
async def test_reminder_still_sent_when_last_practice_was_yesterday(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """The positive half: yesterday's activity must not suppress today."""
    user = await make_verified_user(db_session)
    await db_session.execute(
        text("INSERT INTO user_stats (user_id, last_active_local_date) VALUES (:u, :d)"),
        {"u": str(user.id), "d": TUESDAY_0900.date() - dt.timedelta(days=1)},
    )
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 1


# --------------------------------------------------------------------------
# Gate 4: the schedule half
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reminder_before_the_chosen_local_time(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE: 07:00 UTC is before an 08:00 reminder."""
    await make_verified_user(db_session, reminder="08:00")

    result = await send_daily_reminders(
        session_factory, sender, now=TUESDAY_0900.replace(hour=7)
    )

    assert result["sent"] == 0


@pytest.mark.asyncio
async def test_no_reminder_when_no_time_is_set(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. NULL reminder_local_time has meant "off" since the column
    existed, and A3 must not quietly start mailing that cohort."""
    await make_verified_user(db_session, reminder=None)

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0


@pytest.mark.asyncio
async def test_timezone_decides_the_local_time(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """09:00 UTC is 04:00 in New York, so an 08:00 reminder is not yet due --
    the schedule is the USER's clock, not the server's."""
    await make_verified_user(db_session, timezone="America/New_York", reminder="08:00")

    early = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)
    # 13:00 UTC is 09:00 in New York, past the reminder.
    late = await send_daily_reminders(
        session_factory, sender, now=TUESDAY_0900.replace(hour=13)
    )

    assert early["sent"] == 0
    assert late["sent"] == 1


# --------------------------------------------------------------------------
# Gate 5: suppression is permanent and address-independent
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suppressed_user_gets_no_reminder(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    user = await make_verified_user(db_session)
    await suppress(db_session, user.id, "reminder")
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []


@pytest.mark.asyncio
async def test_unsubscribe_survives_removing_and_reverifying_an_address(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """THE ONE THIS DESIGN EXISTS FOR (D-137(6)).

    Suppression is keyed on user_id, never on the address, so the whole
    remove-then-add-then-verify cycle cannot resurrect it. If it were keyed on
    the address, every one of these steps would look reasonable and the user
    would start receiving mail they explicitly turned off.
    """
    user = await make_verified_user(db_session, email="first@example.com")
    await suppress(db_session, user.id, "reminder")
    await db_session.commit()

    # Withdraw the address entirely, exactly as DELETE /me/email does.
    user.email = None
    user.email_verified_at = None
    user.pending_email = None
    await db_session.commit()

    # Then add and verify a DIFFERENT address.
    user.email = "second@example.com"
    user.email_verified_at = dt.datetime.now(dt.UTC)
    await db_session.commit()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["sent"] == 0
    assert sender.sent == []
    assert (await email_preferences(db_session, user.id))["reminders_enabled"] is False


@pytest.mark.asyncio
async def test_suppressing_one_kind_leaves_the_other_alone(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """Per-type, not one blunt switch."""
    user = await make_verified_user(db_session)
    await suppress(db_session, user.id, "recap")
    await db_session.commit()

    prefs = await email_preferences(db_session, user.id)

    assert prefs == {"reminders_enabled": True, "recap_enabled": False}
    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)
    assert result["sent"] == 1


@pytest.mark.asyncio
async def test_suppress_all_stops_both_kinds(db_session: AsyncSession) -> None:
    """'all' is what a spam complaint means, and it must expand rather than
    match only a literal 'all' kind nobody ever sends."""
    user = await make_verified_user(db_session)
    await suppress(db_session, user.id, "all", reason="complaint", source="webhook")
    await db_session.commit()

    assert await email_preferences(db_session, user.id) == {
        "reminders_enabled": False,
        "recap_enabled": False,
    }


@pytest.mark.asyncio
async def test_suppress_is_idempotent_and_keeps_the_original_reason(
    db_session: AsyncSession,
) -> None:
    """A provider may deliver one-click twice, and a user may click two links.
    Neither may error, and a later click must not rewrite a bounce as a choice."""
    user = await make_verified_user(db_session)
    await suppress(db_session, user.id, "reminder", reason="bounce", source="webhook")
    await suppress(db_session, user.id, "reminder", reason="unsubscribe", source="email_link")
    await db_session.commit()

    row = await db_session.execute(
        text("SELECT reason, source FROM email_suppressions WHERE user_id = :u"),
        {"u": str(user.id)},
    )
    assert row.all() == [("bounce", "webhook")]


# --------------------------------------------------------------------------
# Gate 6: failure handling
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_failure_leaves_the_period_retryable_without_double_sending(
    db_session: AsyncSession, session_factory
) -> None:
    """A failure must not mark the period sent, must not kill the job, and must
    be retryable -- and the retry must not produce a second delivered email."""
    user = await make_verified_user(db_session)
    failing = FailingSender()

    first = await send_daily_reminders(session_factory, failing, now=TUESDAY_0900)

    assert first["failed"] == 1
    assert first["sent"] == 0
    assert await ledger_rows(db_session, user.id) == [("reminder", "failed", 1)]

    # The retry succeeds, and the ledger ends at exactly one 'sent' row: the
    # failed attempt did NOT also deliver.
    recovered = RecordingSender()
    second = await send_daily_reminders(session_factory, recovered, now=TUESDAY_0900)

    assert second["sent"] == 1
    assert len(recovered.sent) == 1
    assert await ledger_rows(db_session, user.id) == [("reminder", "sent", 2)]


@pytest.mark.asyncio
async def test_retry_is_bounded_by_the_attempt_cap(
    db_session: AsyncSession, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE. Retrying forever is how a broken address becomes a permanent
    load and, past Resend's 24h idempotency window, a duplicate risk."""
    monkeypatch.setenv("EMAIL_SEND_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()
    user = await make_verified_user(db_session)
    failing = FailingSender()

    for _ in range(5):
        await send_daily_reminders(session_factory, failing, now=TUESDAY_0900)

    # Two attempts, then the claim stops being granted.
    assert failing.attempts == 2
    assert await ledger_rows(db_session, user.id) == [("reminder", "failed", 2)]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_one_failing_recipient_does_not_end_the_sweep(
    db_session: AsyncSession, session_factory
) -> None:
    """Per-recipient isolation, which is the inner ring of D-137's two."""

    class FailsOnce:
        def __init__(self) -> None:
            self.sent: list[OutboundEmail] = []

        async def send(self, message: OutboundEmail) -> None:
            if message.to == "boom@example.com":
                raise EmailSendError("provider refused")
            self.sent.append(message)

    await make_verified_user(db_session, email="boom@example.com")
    await make_verified_user(db_session, email="fine@example.com")
    sender = FailsOnce()

    result = await send_daily_reminders(session_factory, sender, now=TUESDAY_0900)

    assert result["failed"] == 1
    assert result["sent"] == 1
    assert [m.to for m in sender.sent] == ["fine@example.com"]


# --------------------------------------------------------------------------
# Gate 7: the off-switch, proven structurally like A2's
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_switch_makes_a_network_call_impossible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STRUCTURAL, not "no test happened to call the network".

    With EMAIL_SENDING_ENABLED false, get_email_sender() -- which is the only
    place a real sender is constructed, and the one both A3 jobs default to --
    returns a sender with no transport at all. There is no branch inside the
    real client that could be reached.
    """
    monkeypatch.setenv("EMAIL_SENDING_ENABLED", "false")
    get_settings.cache_clear()

    resolved = get_email_sender()

    assert isinstance(resolved, DisabledEmailSender)
    assert not hasattr(resolved, "_client")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_jobs_run_end_to_end_with_sending_off_and_nothing_leaves(
    db_session: AsyncSession, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole flow is walkable locally: the ledger fills in, the message is
    fully built, and nothing is transported."""
    monkeypatch.setenv("EMAIL_SENDING_ENABLED", "false")
    get_settings.cache_clear()
    user = await make_verified_user(db_session)

    disabled = get_email_sender()
    result = await send_daily_reminders(session_factory, disabled, now=TUESDAY_0900)

    assert result["sent"] == 1
    assert isinstance(disabled, DisabledEmailSender)
    assert len(disabled.sent) == 1
    assert await ledger_rows(db_session, user.id) == [("reminder", "sent", 1)]
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Unsubscribe tokens
# --------------------------------------------------------------------------


def test_unsubscribe_token_round_trips() -> None:
    user_id = uuid.uuid4()
    token = mint_unsubscribe_token(user_id, "reminder")

    assert parse_unsubscribe_token(token) == (user_id, "reminder")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-token",
        "onlyonepart",
        "a.b.c",
        "aGVsbG8.d3Jvbmc",
    ],
)
def test_malformed_unsubscribe_tokens_are_refused(bad: str) -> None:
    """NEGATIVE."""
    with pytest.raises(InvalidUnsubscribeToken):
        parse_unsubscribe_token(bad)


def test_tampered_unsubscribe_token_is_refused() -> None:
    """NEGATIVE, and the important one: swapping the payload for another user's
    id while keeping a valid-looking MAC must fail. Without the MAC covering
    the payload this would be an unsubscribe-anybody primitive."""
    victim = uuid.uuid4()
    attacker_token = mint_unsubscribe_token(uuid.uuid4(), "reminder")
    _, mac = attacker_token.split(".")
    import base64

    forged_payload = (
        base64.urlsafe_b64encode(f"{victim}:reminder".encode()).decode().rstrip("=")
    )

    with pytest.raises(InvalidUnsubscribeToken):
        parse_unsubscribe_token(f"{forged_payload}.{mac}")


# --------------------------------------------------------------------------
# Recap content
# --------------------------------------------------------------------------


def test_week_bounds_is_the_week_that_just_ended() -> None:
    """Monday 2026-07-20 reports Mon 13th to Sun 19th, not the current week."""
    start, end = week_bounds(dt.date(2026, 7, 20))

    assert (start, end) == (dt.date(2026, 7, 13), dt.date(2026, 7, 19))
    assert start.weekday() == 0 and end.weekday() == 6


@pytest.mark.asyncio
async def test_empty_week_is_skipped_not_sent(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE. "Here is your week: nothing" is guilt copy however it is
    worded, and docs/10 rules that out. The period is still CLOSED, so later
    ticks that day do not re-derive the same nothing."""
    user = await make_verified_user(db_session)

    result = await send_weekly_recaps(session_factory, sender, now=MONDAY_0900)

    assert result["sent"] == 0
    assert result["skipped"] == 1
    assert sender.sent == []
    assert await ledger_rows(db_session, user.id) == [("recap", "skipped", 1)]


@pytest.mark.asyncio
async def test_recap_only_goes_out_on_the_configured_weekday(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """NEGATIVE: Tuesday is not recap day."""
    await make_verified_user(db_session)

    result = await send_weekly_recaps(session_factory, sender, now=TUESDAY_0900)

    assert result["considered"] == 0
    assert sender.sent == []


@pytest.mark.asyncio
async def test_recap_does_not_require_a_reminder_time(
    db_session: AsyncSession, session_factory, sender: RecordingSender
) -> None:
    """The two channels are independent (D-137(6)). A user with no reminder
    time still gets a recap, and the ledger proves the job considered them."""
    user = await make_verified_user(db_session, reminder=None)

    result = await send_weekly_recaps(session_factory, sender, now=MONDAY_0900)

    assert result["considered"] == 1
    assert await ledger_rows(db_session, user.id) == [("recap", "skipped", 1)]


@pytest.mark.asyncio
async def test_recap_counts_are_derived_from_attempts(db_session: AsyncSession) -> None:
    user = await make_verified_user(db_session)
    week_start, week_end = week_bounds(dt.date(2026, 7, 20))

    recap = await build_weekly_recap(
        db_session, user.id, week_start=week_start, week_end=week_end
    )

    assert recap.is_empty is True
    # None, not 0: a week with nothing resolved is not a 0% week, and saying so
    # would be a false statement about the reader's performance.
    assert recap.accuracy_pct is None


# --------------------------------------------------------------------------
# Copy rules (docs/10: no guilt, no streak-loss threat)
# --------------------------------------------------------------------------


def test_reminder_copy_contains_no_guilt_or_streak_threat() -> None:
    message = build_reminder_email(to="dev@example.com", user_id=uuid.uuid4())
    body = f"{message.subject}\n{message.text}\n{message.html}".lower()

    for phrase in BANNED_REMINDER_PHRASES:
        assert phrase not in body, f"reminder copy contains banned phrase {phrase!r}"
    # It does not reach for the streak at all, in either direction.
    assert "streak" not in body


def test_reminder_carries_both_rfc_8058_headers() -> None:
    """Both or neither: List-Unsubscribe-Post without a URL is meaningless."""
    message = build_reminder_email(to="dev@example.com", user_id=uuid.uuid4())

    assert message.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message.headers["List-Unsubscribe"].startswith("<")
    assert "/v1/unsubscribe?token=" in message.headers["List-Unsubscribe"]


def test_recap_copy_reports_without_evaluating() -> None:
    from app.email.recap import WeeklyRecap

    recap = WeeklyRecap(
        week_start=dt.date(2026, 7, 13),
        week_end=dt.date(2026, 7, 19),
        sessions_completed=3,
        exercises_attempted=9,
        correct=7,
        graded=9,
        concepts=["off-by-one-slicing"],
        current_streak=4,
        longest_streak=9,
    )
    message = build_recap_email(to="dev@example.com", user_id=uuid.uuid4(), recap=recap)
    body = f"{message.subject}\n{message.text}".lower()

    assert "7 of 9" in message.text
    assert "off-by-one-slicing" in message.text
    for phrase in BANNED_REMINDER_PHRASES:
        assert phrase not in body, f"recap copy contains banned phrase {phrase!r}"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_one_click_unsubscribe_needs_no_login_and_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The RFC 8058 target. No Authorization header anywhere in this test."""
    user = await make_verified_user(db_session)
    token = mint_unsubscribe_token(user.id, "reminder")

    first = await client.post(f"/v1/unsubscribe?token={token}")
    # A provider may deliver it twice; the second is a 200, not an error.
    second = await client.post(f"/v1/unsubscribe?token={token}")

    assert first.status_code == 200
    assert first.json() == {"unsubscribed": "reminder"}
    assert second.status_code == 200
    assert (await email_preferences(db_session, user.id))["reminders_enabled"] is False


@pytest.mark.asyncio
async def test_unsubscribe_preview_does_not_unsubscribe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """NEGATIVE, and the reason the preview is a separate route: a GET that
    acted would let a mail-client prefetcher unsubscribe people silently."""
    user = await make_verified_user(db_session)
    token = mint_unsubscribe_token(user.id, "reminder")

    response = await client.get(f"/v1/unsubscribe/preview?token={token}")

    assert response.status_code == 200
    assert response.json() == {"kind": "reminder"}
    assert (await email_preferences(db_session, user.id))["reminders_enabled"] is True


@pytest.mark.asyncio
async def test_bad_unsubscribe_token_is_one_generic_failure(client: AsyncClient) -> None:
    """NEGATIVE."""
    response = await client.post("/v1/unsubscribe?token=garbage.garbage")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsubscribe_failed"


@pytest.mark.asyncio
async def test_profile_toggle_and_email_link_share_one_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The in-app control reflects the SAME suppression rows the link writes, so
    the two can never disagree about what is on."""
    user = await make_verified_user(db_session)
    token = mint_unsubscribe_token(user.id, "recap")

    await client.post(f"/v1/unsubscribe?token={token}")
    me = await client.get("/v1/me", headers=auth_headers(user))

    assert me.json()["user"]["email_prefs"] == {
        "reminders_enabled": True,
        "recap_enabled": False,
    }

    # And turning it back on in-app is the only path that clears it.
    back_on = await client.patch(
        "/v1/me/email-prefs",
        headers=auth_headers(user),
        json={"recap_enabled": True},
    )
    assert back_on.json() == {"reminders_enabled": True, "recap_enabled": True}


@pytest.mark.asyncio
async def test_me_exposes_reminder_local_time(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """docs/05 section 3 has always promised this field; it was never actually
    in the allowlist, so the client could set it and never read it back."""
    user = await make_verified_user(db_session, reminder="07:30")

    response = await client.get("/v1/me", headers=auth_headers(user))

    assert response.json()["user"]["reminder_local_time"] == "07:30"


@pytest.mark.asyncio
async def test_email_prefs_rejects_unknown_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """NEGATIVE. The request model is extra='forbid', like every other one.

    400 rather than FastAPI's native 422: main.py normalizes
    RequestValidationError into the app's one error envelope, and this route
    must not be the single endpoint that answers in a different shape.
    """
    user = await make_verified_user(db_session)

    response = await client.patch(
        "/v1/me/email-prefs",
        headers=auth_headers(user),
        json={"reminders_enabled": False, "marketing_enabled": True},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
