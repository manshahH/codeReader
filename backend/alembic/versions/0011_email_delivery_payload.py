"""A3: snapshot the rendered email on the delivery row so a retry resends it

Revision ID: 0011_email_delivery_payload
Revises: 0010_email_delivery_ledger
Create Date: 2026-07-20 00:00:00.000000

D-137 addendum. Closes a hole the Resend docs opened after 0010 shipped.

Resend's idempotency contract is not "same key -> same outcome". It is:

  * same key + SAME payload  -> returns the original response, sends nothing
  * same key + DIFFERENT payload -> 409 invalid_idempotent_request

A3's retry path could legitimately change the payload between attempts. The
reminder names today's exercise count when a session row exists and omits it
otherwise, so a user who opens the app between a failed send and its retry
changes the rendered body. The retry then presents the original key with new
bytes and is refused forever: not a duplicate, but a reminder that can never
succeed, failing quietly all the way to the attempt cap.

The fix is to make the payload immutable per period rather than to make the key
vary. A payload hash in the key would ALSO avoid the 409, and it is the wrong
fix: if the first attempt did reach Resend before the failure was observed, a
new key is a new email, which is precisely the duplicate the whole ledger
exists to prevent. Dropping exercise_count would "fix" it by deleting content.

So the first attempt renders once and stores the exact bytes here; every retry
resends THOSE bytes under THAT key. Committed before the provider call, for the
same reason the claim is: a crash between render and send must leave the retry
something to resend.

jsonb rather than text: it is a structured record (to/subject/text/html/
headers), it is queryable when someone asks "what exactly did we send this
person", and it costs nothing over text at this size.

No backfill. Existing rows are 'sent' or terminal, so nothing outstanding needs
a payload; a NULL payload simply means "not rendered yet", which is exactly the
state a fresh claim is in.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_email_delivery_payload"
down_revision: str | None = "0010_email_delivery_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE email_deliveries ADD COLUMN payload jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE email_deliveries DROP COLUMN IF EXISTS payload")
