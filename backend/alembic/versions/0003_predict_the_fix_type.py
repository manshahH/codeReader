"""predict_the_fix exercise type: widen the exercises.type CHECK constraint

Revision ID: 0003_predict_the_fix_type
Revises: 0002_beta_allowlist
Create Date: 2026-07-12 00:00:00.000000

D-80: predict_the_fix is a new deterministic (choice-graded) exercise type
derived from a verified spot_the_bug. The only schema change it needs is a
wider type CHECK -- payload/grading/explanation are already JSONB. db/schema.sql
is updated to match (M1 precedent).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_predict_the_fix_type"
down_revision: str | None = "0002_beta_allowlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "('spot_the_bug','trace','summarize')"
_NEW = "('spot_the_bug','trace','summarize','predict_the_fix')"


def upgrade() -> None:
    op.execute("ALTER TABLE exercises DROP CONSTRAINT IF EXISTS exercises_type_check")
    op.execute(f"ALTER TABLE exercises ADD CONSTRAINT exercises_type_check CHECK (type IN {_NEW})")


def downgrade() -> None:
    # Reversible only if no predict_the_fix rows exist; the ADD would fail
    # otherwise, which is the correct, loud behavior (do not silently drop data).
    op.execute("ALTER TABLE exercises DROP CONSTRAINT IF EXISTS exercises_type_check")
    op.execute(f"ALTER TABLE exercises ADD CONSTRAINT exercises_type_check CHECK (type IN {_OLD})")
