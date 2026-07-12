"""beta allowlist: users.beta_allowed + beta_invites

Revision ID: 0002_beta_allowlist
Revises: 0001_users_onboarded
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_beta_allowlist"
down_revision: str | None = "0001_users_onboarded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN beta_allowed boolean NOT NULL DEFAULT false")
    op.execute(
        """
        CREATE TABLE beta_invites (
          github_login citext      PRIMARY KEY,
          note         text,
          created_at   timestamptz NOT NULL DEFAULT now()
        )
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS beta_invites")
    op.execute("ALTER TABLE users DROP COLUMN beta_allowed")
