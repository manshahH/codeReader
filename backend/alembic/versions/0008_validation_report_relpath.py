r"""exercises.validation_report_url: absolute writer-machine paths -> repo-relative

Revision ID: 0008_validation_report_relpath
Revises: 0007_streak_event_unique
Create Date: 2026-07-13 00:00:00.000000

D-109. publish.write_validation_report used to store `str(path)` -- an
ABSOLUTE path rooted at the repo root as seen by the writing process. The
pipeline runs containerised with the repo bind-mounted at /work, so it
persisted /work/pipeline/validation_reports/<uuid>_v<n>.json, while review_cli
resolves that string on the host, where /work does not exist. The reader
degrades gracefully to None, so 92 of 98 exercises rendered as "no validation
report on disk" in the review packet while every report sat on disk. The ~6
that resolved were published from a host-side run and carry a D:\... path.

The writer now stores a repo-relative POSIX path, which resolves identically
in both contexts. This backfills the rows written before that change.

Only the pointer is rewritten -- no exercise status is touched. Idempotent:
rows already in the canonical form are excluded by the WHERE clause, and it is
scoped to the pipeline/validation_reports segment so a reports dir deliberately
configured outside the repo is left alone.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_validation_report_relpath"
down_revision: str | None = "0007_streak_event_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
        UPDATE exercises
           SET validation_report_url =
               'pipeline/validation_reports/'
               || regexp_replace(validation_report_url, '^.*[/\\]', '')
         WHERE validation_report_url IS NOT NULL
           AND validation_report_url ~ 'pipeline[/\\]validation_reports[/\\]'
           AND validation_report_url !~ '^pipeline/validation_reports/[^/\\]+$'
        """,
    )


def downgrade() -> None:
    r"""Deliberately a no-op.

    The original values encoded the filesystem root of whichever machine wrote
    each row (/work for the container, D:\... for the host); that root is not
    recoverable from the stored string, and re-deriving it would just restore
    the bug. The repo-relative form is readable from every context the absolute
    form was, so there is nothing to undo.
    """
