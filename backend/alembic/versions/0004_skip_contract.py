""""I don't know" contract: attempts.status gains 'skipped',
user_concept_state gains declined

Revision ID: 0004_skip_contract
Revises: 0003_predict_the_fix_type
Create Date: 2026-07-12 00:00:00.000000

D-93: an honest {"skipped": true} answer needs its own terminal status,
distinct from graded/grading_pending/grading_failed -- is_correct stays None
(consistent with its existing "no verdict" meaning for pending/failed), the
new status value is what disambiguates why. user_concept_state.declined
tracks "I don't know" counts separately from attempts/correct so a skip never
inflates the accuracy denominator those two drive.

The status CHECK is a column-level constraint on the partitioned parent
`attempts`; Postgres propagates a parent CHECK to every existing and future
partition automatically, so altering it here (same pattern as
0003_predict_the_fix_type's widened `exercises_type_check`) is the only DDL
needed -- no per-partition ALTER.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_skip_contract"
down_revision: str | None = "0003_predict_the_fix_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUS = "('graded','grading_pending','grading_failed')"
_NEW_STATUS = "('graded','grading_pending','grading_failed','skipped')"


_DROP_STATUS_CHECK = "ALTER TABLE attempts DROP CONSTRAINT IF EXISTS attempts_status_check"
_ADD_STATUS_CHECK = "ALTER TABLE attempts ADD CONSTRAINT attempts_status_check CHECK (status IN {})"


def upgrade() -> None:
    op.execute(_DROP_STATUS_CHECK)
    op.execute(_ADD_STATUS_CHECK.format(_NEW_STATUS))
    op.execute("ALTER TABLE user_concept_state ADD COLUMN declined int NOT NULL DEFAULT 0")


def downgrade() -> None:
    # Reversible only if no skipped rows exist; the ADD would fail otherwise,
    # which is the correct, loud behavior (do not silently drop data).
    op.execute("ALTER TABLE user_concept_state DROP COLUMN declined")
    op.execute(_DROP_STATUS_CHECK)
    op.execute(_ADD_STATUS_CHECK.format(_OLD_STATUS))
