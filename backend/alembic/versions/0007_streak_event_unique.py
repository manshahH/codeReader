"""streak_events: at most one extend/reset transition per user per local day

Revision ID: 0007_streak_event_unique
Revises: 0006_review_history
Create Date: 2026-07-13 00:00:00.000000

H1/D-104: a streak transition ('extended' or 'reset') happens exactly once per
user per local day -- on the first attempt of that day. Concurrent same-day
submits could previously write TWO transition rows (invariant 5: "every streak
transition writes A streak_events row" -> two rows for one transition). The
per-(user, day) advisory lock in attempts/service.py serializes the race, and
this PARTIAL UNIQUE INDEX is the un-raceable DB backstop underneath it: the
database itself refuses a second extended/reset row for the same
(user_id, local_date), regardless of any application-level race.

Scoped to event IN ('extended','reset') on purpose: 'repaired' (timezone
reconciliation, D-68), 'freeze_used', and 'adjusted' are separate event kinds
that can legitimately co-occur with a transition on the same day, so they are
deliberately NOT constrained.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_streak_event_unique"
down_revision: str | None = "0006_review_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_streak_events_one_transition_per_day
        ON streak_events (user_id, local_date)
        WHERE event IN ('extended', 'reset')
        """,
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_streak_events_one_transition_per_day")
