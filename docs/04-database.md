# 04 : Database

DDL: db/schema.sql (statically audited: FK targets, partition-key/PK rule,
paren balance; run `psql -f db/schema.sql` on scratch before first use, this
was not executable in the authoring environment). Postgres 16+. Conventions:
text + CHECK over enums (constraint swap beats ALTER TYPE), timestamptz
everywhere, user-local dates as `date`, soft delete only on users, JSONB blobs
server-written only.

## Table-by-table rationale

**users / auth_identities**: split so multi-provider and Teams SSO are a row
type later, not a migration. citext username. IANA timezone validated in app.

**users.email / pending_email / email_verification_tokens** (A2, D-120): the
first PII here. GitHub OAuth stays scoped `read:user`, so the address is
self-asserted and we verify it ourselves rather than widening scope and forcing
re-consent on every existing user. `email` holds ONLY a verified address;
`pending_email` holds one awaiting confirmation, so a typo cannot take a working
notification channel offline and A3 always sees either a proven-deliverable
address or NULL, never a maybe. Uniqueness is a PARTIAL index (`WHERE
email_verified_at IS NOT NULL AND deleted_at IS NULL`): a plain UNIQUE would be
an address-squatting primitive, since typing a victim's address into your own
profile would block them from ever registering it. Uniqueness must attach to
proven control, not to typing. Two rows may therefore hold the same
`pending_email`; the first to verify wins the index and the loser's promotion
fails the constraint, which is the correct arbiter (an app-level pre-check would
be TOCTOU anyway). `email_verification_tokens` mirrors refresh_tokens' storage
exactly (sha256 of a `secrets.token_urlsafe(32)`) and carries the address the
token was issued FOR, so a stale link can only promote that address and never a
newer one. `invalidated_at` rather than deleting superseded rows, for the same
reason streak_events is a ledger: "why did my link stop working" has to be
answerable in one query.

**email_deliveries / email_suppressions** (A3, D-137): the send-once ledger and
the permanent opt-out, and they answer two different questions that must not be
conflated. `email_deliveries` answers "have we already sent this user this kind
of mail for this period", and its PRIMARY KEY `(user_id, kind, period_key)` IS
the frequency ceiling: two overlapping job runs both attempt the claim and
exactly one INSERT wins, with no advisory lock needed because there is nothing
to read-modify-write. A ledger rather than a `last_reminder_sent_at` column for
the same reason D-116 refused to infer a covered day from the freeze balance: a
timestamp makes "already sent" a computation at read time, and that computation
depends on the user's timezone, which can change underneath it. The period key
IS the answer, so it cannot drift. `status` carries a three-way outcome where
the middle value is the interesting one: 'sent' and 'skipped' are terminal,
'failed' is a DEFINITE failure we committed and is therefore retryable, and
'claimed' is the ambiguous state (the process died between claim and outcome)
which is terminal ON PURPOSE, because a duplicate reminder is the expensive
direction of that guess. `email_suppressions` answers "may we send at all" and
is keyed on `user_id`, NEVER on the address: that is exactly what makes an
unsubscribe survive a re-verify, since removing an address, adding a new one and
confirming it never touches this table. There is no expiry column and nothing in
the job path deletes a row; the only way back on is an authenticated opt-in on
Profile. `reason` and `source` are carried from day one so that adding the
deferred Resend bounce/complaint webhook later is an endpoint, not a migration.

**refresh_tokens**: opaque token sha256-hashed at rest; family_id present NOW
so post-MVP reuse-detection family kill is a code change. MVP behavior on
reuse of a rotated token: 401 + alert.

**exercises**: PK (id, version), immutable per version. payload / grading /
explanation as three separate JSONB columns because the serialization boundary
is the security boundary: grading and explanation must be structurally easy to
exclude. Serving indexes are partial (WHERE status='live').
exercises_current view = latest live version per id.

**daily_sessions**: durable record of what was in today's session. Exists
because Redis is a cache, not the truth: a Redis flush mid-morning must not
resample a different session (looks like a bug, corrupts completion logic).

**attempts**: hottest table. Partitioned monthly FROM DAY ONE (declaring it
now is one line; partitioning 50M rows later is a weekend). PK must include
the partition key, hence (id, created_at); consequence: nothing can FK to
attempts, so disputes.attempt_id is a deliberate soft link. Append-only; the
ONLY updates are rubric grading results onto the same row (MVP simplification;
splits to grading_results if update contention ever shows). grading_mode is
denormalized on so the pending-grading cron scans without joining exercises.
Exactly two indexes; every extra index taxes the hottest write path.
Idempotency lives in Redis (24h), not a DB constraint (a partitioned unique
would need created_at, defeating it); accepted tradeoff: replay after Redis
loss can duplicate, stats job dedupes. attempts_default partition = safety net
if the monthly partition cron is missed; ALERT if it ever has rows, and move
them out BEFORE creating the overlapping monthly partition or the create
fails.

**user_stats / user_concept_state**: precomputed aggregates; nothing
user-facing ever aggregates attempts at request time, even at MVP.
user_concept_state keys the spaced repetition (next_review_at) and skill
graph; concept strings validated app-side against the versioned taxonomy.
A4 "peek at tomorrow" (D-142) adds a READ-ONLY use with no schema change:
`GET /session/today` reads the single `next_review_at` falling within the
user's local day after today to tease one concept on the Dashboard's completed
state. It writes nothing and persists no "tomorrow's session" -- tomorrow's set
depends on inputs (next_review_at, mastery, recently-seen) that today's attempts
are still mutating, so it can only be honestly derived at request time, never
frozen ahead.

**streak_events**: every streak transition audited. Streaks are the retention
crown jewel; "my streak vanished" must be answerable in one query.

**exercise_stats**: periodic-job output for percentile display; app hides
until attempts_count >= 30.

**disputes**: user reports; partial index on open ones; operator alert on
insert; resolution manual at MVP.

## Ops
- Monthly cron creates the next attempts partition ahead of time.
- Daily base backup + WAL; one restore drill BEFORE launch, quarterly after.
- Attempt events also appended as JSONL to S3 (analytics later; ClickHouse
  phase 2).
- gen_random_uuid() is v4; when index locality matters, switch to
  app-generated UUIDv7, zero schema change.
