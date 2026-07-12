"""review_history: append-only record of every review submission

Revision ID: 0006_review_history
Revises: 0005_reviews
Create Date: 2026-07-13 00:00:00.000000

Beta feedback request: reviews stays the upserted "current opinion" (D-93c),
but the upsert was destroying the prior rating on every resubmit -- for beta
feedback the delta ("rated 3 on day one, 5 on day thirty") is the signal, not
either number alone. review_history is append-only: one row per POST
/v1/me/review call, never updated or deleted, so a rating change is visible
after the fact instead of overwritten in place.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_review_history"
down_revision: str | None = "0005_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_history (
          id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          rating      smallint    NOT NULL CHECK (rating BETWEEN 1 AND 5),
          body        text,
          created_at  timestamptz NOT NULL DEFAULT now()
        )
        """,
    )
    op.execute(
        "CREATE INDEX idx_review_history_user ON review_history (user_id, created_at)",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS review_history")
