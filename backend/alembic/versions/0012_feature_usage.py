"""feature_usage: one row per (user, feature, local day) first use

Revision ID: 0012_feature_usage
Revises: 0011_email_delivery_payload
Create Date: 2026-07-23 00:00:00.000000

D-145(g). Per-feature usage tracking so the eventual decision about what goes
paid (D-145 decision 6) is made on evidence rather than taste.

The PRIMARY KEY (user_id, feature, local_date) IS the once-per-day ceiling,
inserted ON CONFLICT DO NOTHING -- the same construction email_deliveries uses:
a recorded fact with a uniqueness constraint, never a recomputation. One small
row per user per feature per day is bounded and needs no partitioning at this
scale.

No new PII (D-120 posture): user_id + a date is already the shape of
streak_events, daily_sessions and attempts. No free text, no content, no IP, no
user agent. Rows are deleted with the account by ON DELETE CASCADE.

New table, no dependencies, no backfill: it starts empty, which is correct --
nothing has been recorded yet. RELEASE SEQUENCING is a launch-plan decision
(D-145 item 4, HANDOFF outstanding launch mechanics): production is on 0008 with
0009-0011 already unreleased, and this is the fourth unapplied migration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_feature_usage"
down_revision: str | None = "0011_email_delivery_payload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE feature_usage (
          user_id    uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          feature    text        NOT NULL,          -- a registry key (entitlements.Feature)
          local_date date        NOT NULL,          -- the user's LOCAL day
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, feature, local_date)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feature_usage")
