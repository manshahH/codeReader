"""A3 reminders + recap: the send-once ledger and permanent suppressions

Revision ID: 0010_email_delivery_ledger
Revises: 0009_user_email
Create Date: 2026-07-20 00:00:00.000000

D-137. Two tables, answering two questions that must not be conflated.

email_deliveries answers "have we already sent this user this kind of mail for
this period". The PRIMARY KEY (user_id, kind, period_key) IS the frequency
ceiling: two overlapping job runs both attempt the claim and exactly one INSERT
wins, with no advisory lock needed because there is nothing to
read-modify-write. Same discipline as uq_streak_events_one_transition_per_day.

A ledger rather than a `last_reminder_sent_at` column on users, for the reason
D-116 refused to infer a covered day from the freeze balance: a timestamp makes
"already sent for this period" a computation at read time, and that computation
depends on the user's timezone, which can change underneath it. The period key
IS the answer.

email_suppressions answers "may we send at all", keyed on user_id and NEVER on
the address. That is what makes an unsubscribe survive a re-verify by
construction: DELETE /me/email plus a new address plus a fresh verification
never touches this table. `reason` and `source` exist from day one even though
only 'unsubscribe'/'email_link'/'profile' are written today, so that adding the
deferred Resend bounce+complaint webhook later is an endpoint and not a
migration.

No backfill. Both tables start empty, which is the correct state: nothing has
been sent and nobody has unsubscribed. Absence of a suppression row means
"allowed", so every existing user is opted in to a channel that cannot actually
send anything until EMAIL_SENDING_ENABLED is flipped AND a sending domain
exists (D-137(0)).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_email_delivery_ledger"
down_revision: str | None = "0009_user_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE email_deliveries (
          user_id    uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind       text        NOT NULL CHECK (kind IN ('reminder','recap')),
          period_key text        NOT NULL,
          status     text        NOT NULL DEFAULT 'claimed'
                       CHECK (status IN ('claimed','sent','failed','skipped')),
          attempts   int         NOT NULL DEFAULT 0,
          last_error text,
          claimed_at timestamptz NOT NULL DEFAULT now(),
          sent_at    timestamptz,
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, kind, period_key)
        )
        """,
    )
    op.execute(
        """
        CREATE TRIGGER trg_email_deliveries_touch BEFORE UPDATE ON email_deliveries
          FOR EACH ROW EXECUTE FUNCTION touch_updated_at()
        """,
    )
    op.execute(
        """
        CREATE INDEX idx_email_deliveries_retryable
          ON email_deliveries (kind, period_key)
          WHERE status = 'failed'
        """,
    )
    op.execute(
        """
        CREATE TABLE email_suppressions (
          user_id    uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind       text        NOT NULL CHECK (kind IN ('reminder','recap','all')),
          reason     text        NOT NULL DEFAULT 'unsubscribe'
                       CHECK (reason IN ('unsubscribe','bounce','complaint')),
          source     text        NOT NULL DEFAULT 'email_link'
                       CHECK (source IN ('email_link','profile','webhook','admin')),
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, kind)
        )
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_suppressions")
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_retryable")
    op.execute("DROP TRIGGER IF EXISTS trg_email_deliveries_touch ON email_deliveries")
    op.execute("DROP TABLE IF EXISTS email_deliveries")
