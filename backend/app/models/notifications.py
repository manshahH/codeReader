"""Outbound notification state (A3, D-137).

Two tables, and they answer two different questions that must not be conflated
(D-137(6)):

* `email_deliveries` answers "have we already sent this user this kind of mail
  for this period", and it is a LEDGER, not a timestamp. The primary key IS the
  send-once guarantee: two overlapping job runs both attempt the claim and
  exactly one INSERT wins. Same un-raceable-DB-backstop discipline as
  uq_streak_events_one_transition_per_day (H1/D-104), and the same reason D-116
  reads a covered day from the streak_events ledger rather than inferring it --
  a recorded fact survives a timezone change, a recomputation does not.
* `email_suppressions` answers "may we send at all", and it is keyed on
  `user_id`, NEVER on the address. That is precisely what makes an unsubscribe
  survive a re-verify: DELETE /me/email plus a new address plus a fresh
  verification never touches this table.

Neither table's CHECK constraints are duplicated on these models beyond what
SQLAlchemy needs, matching the house convention that SQL is canonical
(db/schema.sql) and partial indexes live in SQL only.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# The kinds of mail a user can be sent, and separately suppress. 'all' is a
# suppression-only value: it is what a spam complaint means (stop everything),
# and it is never a delivery kind because nothing is ever sent as "all".
DELIVERY_KINDS = ("reminder", "recap")
SUPPRESSION_KINDS = ("reminder", "recap", "all")


class EmailDelivery(Base):
    """One row per (user, kind, period). The PK is the frequency ceiling.

    `status` carries the three-way outcome D-137(3) turns on:

    * 'sent'    -- the provider accepted. Terminal.
    * 'failed'  -- we caught a definite EmailSendError and committed that fact,
                   so we KNOW no send succeeded. Retryable, bounded.
    * 'claimed' -- ambiguous: the process died between claim and outcome, or a
                   send is in flight. TERMINAL on purpose. We cannot tell "died
                   before the POST" from "died after Resend accepted it", and a
                   duplicate reminder is the expensive direction of that guess.
    * 'skipped' -- deliberately not sent (an empty recap week, D-137(8)).
                   Terminal, and recorded rather than left absent so the period
                   is not re-evaluated on every later tick.
    """

    __tablename__ = "email_deliveries"
    __table_args__ = (
        CheckConstraint("kind IN ('reminder','recap')"),
        CheckConstraint("status IN ('claimed','sent','failed','skipped')"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    # The user-LOCAL period this send belongs to: 'YYYY-MM-DD' for a reminder,
    # ISO year-week 'GGGG-Www' for a recap. Text rather than a date so both
    # shapes share one column and one constraint; the key is an identity, not
    # something we do date arithmetic on.
    period_key: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'claimed'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # The exception TYPE only, never the message and never the body: an httpx
    # error can carry the request body, and that body is somebody's mail
    # (D-120's logging discipline).
    last_error: Mapped[str | None] = mapped_column(Text)
    # The rendered email, snapshotted on the FIRST attempt so every retry
    # resends the exact original bytes under the exact original key. Resend
    # refuses a reused key carrying a CHANGED payload (409), and changing the
    # key instead would risk the duplicate this whole table exists to prevent.
    payload: Mapped[dict | None] = mapped_column(JSONB)
    claimed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EmailSuppression(Base):
    """A permanent opt-out. Keyed on the USER, never on the address (D-137(6)).

    There is no expiry column and nothing in the job path ever deletes a row.
    The only way back on is an explicit authenticated opt-in on Profile, which
    is the only defensible basis for re-consent.

    `reason` and `source` are carried from day one even though only
    'unsubscribe' is written today: bounce/complaint suppression is deferred
    (D-137), and shaping the columns now is what makes adding the Resend webhook
    later an endpoint rather than a migration.
    """

    __tablename__ = "email_suppressions"
    __table_args__ = (
        CheckConstraint("kind IN ('reminder','recap','all')"),
        CheckConstraint("reason IN ('unsubscribe','bounce','complaint')"),
        CheckConstraint("source IN ('email_link','profile','webhook','admin')"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unsubscribe'")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'email_link'"))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
