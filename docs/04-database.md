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
