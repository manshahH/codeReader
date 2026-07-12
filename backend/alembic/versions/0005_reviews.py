"""reviews: beta feedback, one review per user

Revision ID: 0005_reviews
Revises: 0004_skip_contract
Create Date: 2026-07-12 00:00:00.000000

D-93c: POST /v1/me/review is an upsert, so uniqueness on user_id is enforced
at the DB layer, not just in application code -- a race between two
concurrent submits for the same user still can't produce two rows.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_reviews"
down_revision: str | None = "0004_skip_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE reviews (
          id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
          rating      smallint    NOT NULL CHECK (rating BETWEEN 1 AND 5),
          body        text,
          created_at  timestamptz NOT NULL DEFAULT now(),
          updated_at  timestamptz NOT NULL DEFAULT now()
        )
        """,
    )
    op.execute(
        """
        CREATE TRIGGER trg_reviews_touch BEFORE UPDATE ON reviews
          FOR EACH ROW EXECUTE FUNCTION touch_updated_at()
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reviews")
