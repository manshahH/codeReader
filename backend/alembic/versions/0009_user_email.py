"""A2 email capture: users.email/pending_email + verification tokens

Revision ID: 0009_user_email
Revises: 0008_validation_report_relpath
Create Date: 2026-07-18 00:00:00.000000

D-120. Adds the first PII in the system.

No backfill: `users` has no email column today, so every existing row lands on
NULL, which is exactly the intended "no email captured" state. (Contrast D-118,
which needed a backfill because its column already existed with a default that
was wrong for the pre-existing cohort.)

`email` holds ONLY a verified address; a newly submitted one waits in
`pending_email` so a typo cannot take a working address offline (D-120(2)).

The unique index is PARTIAL on purpose (D-120(3)): scoping it to verified,
non-deleted rows is what stops an attacker from squatting an address they do
not control simply by typing it into their own profile. Same shape as
uq_streak_events_one_transition_per_day: partial, SQL-only, not on the model.

email_verification_tokens stores the sha256 of a secrets.token_urlsafe(32),
matching refresh_tokens.token_hash exactly (auth/tokens.py). It carries the
target `email` so a stale link can only ever promote the address it was issued
for, never whatever pending_email happens to say at consume time.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_user_email"
down_revision: str | None = "0008_validation_report_relpath"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
          ADD COLUMN email             citext,
          ADD COLUMN email_verified_at timestamptz,
          ADD COLUMN pending_email     citext
        """,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_users_email_verified
          ON users (email)
          WHERE email_verified_at IS NOT NULL AND deleted_at IS NULL
        """,
    )
    op.execute(
        """
        CREATE TABLE email_verification_tokens (
          id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id        uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          email          citext      NOT NULL,
          token_hash     bytea       NOT NULL UNIQUE,
          expires_at     timestamptz NOT NULL,
          consumed_at    timestamptz,
          invalidated_at timestamptz,
          created_at     timestamptz NOT NULL DEFAULT now()
        )
        """,
    )
    op.execute(
        """
        CREATE INDEX idx_evt_user_live ON email_verification_tokens (user_id)
          WHERE consumed_at IS NULL AND invalidated_at IS NULL
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_verification_tokens")
    op.execute("DROP INDEX IF EXISTS uq_users_email_verified")
    op.execute(
        """
        ALTER TABLE users
          DROP COLUMN IF EXISTS email,
          DROP COLUMN IF EXISTS email_verified_at,
          DROP COLUMN IF EXISTS pending_email
        """,
    )
