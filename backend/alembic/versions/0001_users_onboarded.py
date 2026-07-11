"""users.onboarded column

Revision ID: 0001_users_onboarded
Revises: 0000_schema_sql
Create Date: 2026-07-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_users_onboarded"
down_revision: str | None = "0000_schema_sql"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN onboarded boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN onboarded")
