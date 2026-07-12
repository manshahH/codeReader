# Ops Runbook

Populated during M7. Every procedure below has been executed at least once
against the local docker-compose Postgres; commands, real output, and
timestamps are recorded, not just described.

## 1. Backup and restore drill

**Choice: `pg_dump` (custom format), not base backup + WAL.** docs/04 names
base+WAL as the end-state approach; at MVP scale (docs/03: ~25k attempts/day,
one small Postgres box, no read replicas, no tenants to isolate) a nightly
`pg_dump` gives a full, portable, human-inspectable backup with a trivial
restore procedure, at the cost of losing only up-to-24h of data on a disaster
(no point-in-time recovery). Base+WAL buys sub-minute RPO but needs an
archive_command target (S3), a WAL retention policy, and a `pg_basebackup` +
replay restore procedure -- real operational surface with no current
justification at this data volume. Revisit (this is the seam, not a rewrite)
once daily attempt volume or the RPO requirement changes. Recorded as
docs/07-decisions.md D-64.

**Scripts** (both executed for real, see the drill record below):
- `backend/scripts/backup_db.sh` -- `pg_dump -F c`, timestamped filename,
  prunes backups older than `RETENTION_DAYS` (default 14). Works against
  either a docker-compose container (`POSTGRES_CONTAINER=<name>`) or a
  managed Postgres via `DATABASE_URL`.
- `backend/scripts/restore_db.sh <dump-file> [--replace]` -- restores into
  `TARGET_DB_NAME` (default `codereader_restore_drill`, a SCRATCH database;
  pass `--replace` to drop-and-recreate the target in place for a real
  incident, never done by default).

**Cron** (daily, 02:00 local, on whatever host runs backups):
```
0 2 * * * POSTGRES_CONTAINER=codereader-postgres-1 BACKUP_DIR=/var/backups/codereader /path/to/backend/scripts/backup_db.sh >> /var/log/codereader-backup.log 2>&1
```
On managed Postgres in production, prefer the provider's own automated
daily snapshot (RDS/Cloud SQL/etc. automated backups) as the primary
mechanism and keep `backup_db.sh` (pointed at `DATABASE_URL`) as a
secondary, portable, provider-independent copy.

**Always back up before running a content batch.** `python -m
pipeline.orchestrator` and `python -m pipeline.ingest` both write real,
often paid-for content straight into the dev/prod database; at this
project's data volume `backup_db.sh` takes about a second (see the drill
record below), so there is no cost-based reason to skip it before a batch
you can't cheaply reproduce. This is not hypothetical: D-88 records ~37,
then a further 24, real generated exercises lost to a SEPARATE hazard
(pytest wiping the shared database, section 7) that a pre-batch backup
would have made a non-event instead of a loss.

### Executed drill record

Run **2026-07-11, 20:20-20:20 UTC**, against the local docker-compose
Postgres (`codereader-postgres-1`), seeded with one user (via
`CODEREADER_ALLOW_SEED=1 python backend/scripts/seed_e2e.py`), 3 exercises,
and one hand-inserted `attempts` / `user_stats` / `streak_events` row (to
prove the partitioned table and the precomputed-stats tables all survive,
not just static content).

Pre-drill source-of-truth row counts:
```
$ docker exec codereader-postgres-1 psql -U codereader -d codereader -t -c "
    SELECT 'users', count(*) FROM users
    UNION ALL SELECT 'exercises', count(*) FROM exercises
    UNION ALL SELECT 'attempts', count(*) FROM attempts
    UNION ALL SELECT 'user_stats', count(*) FROM user_stats
    UNION ALL SELECT 'streak_events', count(*) FROM streak_events;"
 users         |     1
 exercises     |     3
 attempts      |     1
 user_stats    |     1
 streak_events |     1
```

Backup:
```
$ POSTGRES_CONTAINER=codereader-postgres-1 BACKUP_DIR=backend/data/backups \
  ./backend/scripts/backup_db.sh
backup_db: wrote backend/data/backups/codereader_2026-07-11T2020Z.dump

backup_started_at=2026-07-11T20:20:39Z
backup_finished_at=2026-07-11T20:20:40Z   (1s)
-> file size 45473 bytes
```

Restore, into a fresh scratch database (`--replace` drops it first if a
prior drill left one behind):
```
$ POSTGRES_CONTAINER=codereader-postgres-1 \
  ./backend/scripts/restore_db.sh backend/data/backups/codereader_2026-07-11T2020Z.dump --replace
restore_db: DROPPING and recreating codereader_restore_drill (--replace)
NOTICE:  database "codereader_restore_drill" does not exist, skipping
DROP DATABASE
CREATE DATABASE
restore_db: restored backend/data/backups/codereader_2026-07-11T2020Z.dump into database codereader_restore_drill

restore_started_at=2026-07-11T20:20:48Z
restore_finished_at=2026-07-11T20:20:50Z
```

Post-restore verification (exact match to pre-drill counts, plus the seeded
attempt row's content spot-checked field-by-field, not just counted):
```
$ docker exec codereader-postgres-1 psql -U codereader -d codereader_restore_drill -t -c "..."
 users         |     1
 exercises     |     3
 attempts      |     1
 user_stats    |     1
 streak_events |     1

$ docker exec codereader-postgres-1 psql -U codereader -d codereader_restore_drill -c \
  "SELECT user_id, exercise_id, is_correct, time_taken_ms FROM attempts;"
               user_id                |             exercise_id              | is_correct | time_taken_ms
--------------------------------------+--------------------------------------+------------+---------------
 3bc655e7-1865-4707-b4e0-738b301d3450 | d9de714d-a659-52e1-9710-23d8f89b9fd0 | t          |          4200
```
Scratch database dropped after verification (`DROP DATABASE
codereader_restore_drill;`), matching normal drill hygiene.

**Measured RTO: ~2 seconds restore time** (backup 1s + restore 2s + manual
verification, ~11s wall clock end to end) at this drill's tiny data volume.
This is not a projection of production RTO -- `pg_restore`'s cost scales
with actual data volume (indexes rebuild, constraints re-validate), so the
number to track going forward is RTO measured against a production-sized
copy, not this drill's. **Next scheduled drill: quarterly, per docs/04** (add
to the alert/ops calendar; the next one is due by 2026-10-11).

## 2. Attempts partition management

Monthly partitions (`attempts_YYYY_MM`) are created by `app/jobs/partitions.py`,
run automatically by the in-process scheduler (`app/jobs/runner.py`,
`JOB_PARTITIONS_INTERVAL_S`, default daily, plus once at startup) and
available for manual/external-cron invocation:
```
python -m app.jobs.partitions
```

**Self-recovery (M7 fix).** Two bugs closed:
1. The job used to create only "next month"'s partition. If it went
   uninvoked for two+ consecutive months, the gap could never close --every
   run only ever tried the one month after "now". It now walks every month
   from the last existing partition through next month, closing a gap of
   any size in one run (capped at 72 months as a runaway-loop backstop).
2. `count_attempts_default_rows` existed but nothing acted on it. A
   `CREATE TABLE ... PARTITION OF attempts FOR VALUES FROM (...) TO (...)`
   for a month that already has rows sitting in `attempts_default` fails
   outright (Postgres refuses an overlapping range partition). The job now
   checks for overlapping `attempts_default` rows before creating each
   month's partition and, if any exist, **logs loudly**
   (`attempts_default_has_rows`, includes the row count and target
   partition) and drains them: creates a plain table shaped like `attempts`
   (`LIKE attempts INCLUDING ALL`), moves the rows
   (`DELETE ... RETURNING` + `INSERT ... OVERRIDING SYSTEM VALUE`), then
   attaches it as the partition (`ALTER TABLE attempts ATTACH PARTITION`).
   The common case (no gap, `attempts_default` empty for the target month)
   is unchanged: a direct, cheap `CREATE TABLE ... PARTITION OF`.

**`attempts_default` should be empty in steady state.** Its only job is
absorbing writes during a missed-partition window; if
`count_attempts_default_rows()` (or the `attempts_default_has_rows` log line)
ever reports rows, that means the partition cron was down for at least one
full month and needs investigation (see the alert catalog, section 6).

Verified: `backend/tests/test_m7_partition_recovery.py` seeds a row directly
into `attempts_default` for a month with no partition (simulating a missed
month), then runs the job and asserts it recovers -- creates the missing
month's partition plus every month up through next month, drains the stray
row out of `attempts_default`, and the row is provably still present (not
lost) via the parent `attempts` table afterward.

## 3. Pulling a disputed exercise

Tooling exists since D-58/M7:
```
python -m pipeline.review_cli pull <exercise_id> <version>
```
Effect: flips the exercise's `status` to `'pulled'` (the only content-free
status transition D-58's immutability guard permits on a live row), then
purges every still-servable `daily_sessions` row referencing it (yesterday
onward -- older rows can no longer be served, the session cache TTL is 36h)
and the matching `session:{user}:{date}` Redis keys, committing the DB
change BEFORE the Redis deletes so a racing `GET /session/today` cannot
re-cache a session that's about to disappear. A pulled exercise is gone from
both already-cached and freshly-built sessions immediately; it is NOT
deleted (immutability per version, D-5) and remains queryable for the
dispute's own resolution record.

This is the incident path for "wrong answer key is live" -- the scenario the
per-exercise dispute-rate signal in `GET /admin/metrics` (section 6) exists
to catch early.

## 4. Rotating secrets

### `JWT_SECRET`
Rotate-capable BY DESIGN (docs/06): `JWT_SECRET` accepts a comma-separated
list, and `verify_access_token` accepts any secret in that list
(`Settings.jwt_secrets`). Zero-downtime rotation:
1. Set `JWT_SECRET=<new>,<old>` and deploy -- both secrets now verify;
   `issue_access_token` still signs with the FIRST entry (still `<old>` at
   this point, so no behavior change yet, just added acceptance).
2. Set `JWT_SECRET=<new>` alone (drop `<old>`) and deploy again, at least
   `ACCESS_TOKEN_TTL` seconds (15 min) after step 1 -- every token issued
   under `<old>` has expired by then, so nothing breaks.
What breaks if skipped/rushed: any access token signed before step 2 that
hasn't yet expired stops verifying the moment `<old>` is dropped -- affected
users get `401 invalid_token` and must re-auth via `/v1/auth/refresh`
(their refresh cookie is unaffected, this is a same-visit blip, not a
logout).

### `TOKEN_ENC_KEY`
**Not rotate-capable today** -- `core/security.py` takes a single key
(AES-GCM), no key list, no versioning. Rotating it makes every
`auth_identities.access_token_enc` value encrypted under the OLD key
permanently undecryptable under the new one. **What this actually breaks:
nothing live** -- grep shows `decrypt_token` is called only from the test
suite; no production code path currently reads the stored GitHub token back
(it's persisted for a currently-unbuilt future capability, e.g.
re-verifying scopes or revoking on GitHub's side). Rotation procedure:
change `TOKEN_ENC_KEY` and deploy; existing encrypted rows become inert
(harmless, since nothing reads them) rather than corrupted-looking. If a
future feature depends on decrypting historical tokens, either force
affected users through OAuth again (mints a freshly-encrypted row) or add
key-list support to `core/security.py` (mirroring `JWT_SECRET`'s pattern)
BEFORE that feature ships, not after.

### `OPENAI_API_KEY` (and `ANTHROPIC_API_KEY` if `GRADER_PROVIDER=anthropic`)
Stateless credential, no stored-data implication. Rotate by updating the env
var and deploying; the grader client reads it per-request via
`get_settings()` (cached, so a rotation requires an actual redeploy/restart
to take effect, not just an env change on a running host). No in-flight
requests are lost -- the OLD key keeps working until the new process starts,
and `grade_rubric`'s existing timeout/retry path (section 5) already
tolerates a handful of failed calls during the cutover window.

### `GITHUB_CLIENT_SECRET`
Update the env var and deploy. GitHub OAuth app secrets do not support a
grace-period list the way `JWT_SECRET` does -- there IS a short window where
an in-flight `/v1/auth/github/callback` (state already issued, user mid-flow
on GitHub's consent screen) using the OLD secret will fail the code
exchange. Mitigate by rotating during low-traffic hours; a failed exchange
routes the user to `/login?error=oauth_denied` (docs/05), a normal retry, not
a hard failure.

## 5. LLM/grader degradation playbook

**Signal:** `app/core/grader_health.py`, Redis-only, self-healing via TTL.
`FAILURE_THRESHOLD = 3` consecutive `grade_rubric()` failures (any
exception -- timeout, transport error, or an API error like
`insufficient_quota`, see below) marks the grader **degraded** for
`DEGRADED_TTL_SECONDS = 300` (5 minutes); any success clears both the streak
and the degraded flag immediately.

**What degrades, concretely:** `sessions/service.py::_build_and_persist_session`
checks `grader_health.is_degraded()` on every FIRST-of-day session build and,
if degraded, samples from `DETERMINISTIC_TYPES` only (`spot_the_bug`,
`trace`) -- no `summarize` slots. Already-issued sessions from before the
degradation are unaffected (docs/05: "already-issued sessions are
unchanged"). Individual in-flight `summarize` submissions are NOT blocked by
this flag -- `POST /attempts` still calls `grade_rubric()` regardless; the
degraded flag only affects what NEW sessions get sampled.

**What to watch:**
- `GET /admin/metrics` -> `attempt_insert_error_rate` and
  `pending_grade_count` (the two non-negotiable golden signals, docs/06 M7).
  A climbing `pending_grade_count` is the earliest signal something is
  wrong with the grader, well before `grading_failed` rows accumulate.
- Redis keys directly, if metrics access isn't handy:
  `GET grader:failure_streak`, `EXISTS grader:degraded`.
- Log line `periodic job 'grading_retry' ran: {...}` (INFO, every
  `JOB_GRADING_RETRY_INTERVAL_S`, default 30s) -- `resolved`/`failed`/
  `still_pending` counts show the retry job's own view of the backlog.

**The `insufficient_quota` (429) case** (hit in production testing, D-43
area): `rubric.py::grade_rubric`'s call to the LLM client is wrapped in a
broad `except Exception as exc: raise RubricGradingTimeout(...)` -- an
OpenAI `insufficient_quota` 429 is caught by this and treated EXACTLY like a
network timeout: the attempt lands `status="grading_pending"`,
`grader_health.mark_failure()` fires, and `jobs/grading_retry.py` retries it
on its normal schedule. The critical difference from a transient timeout:
**quota exhaustion does not resolve on retry** -- every retry attempt fails
the same way until the account's quota/billing is fixed. After
`MAX_RETRY_ATTEMPTS = 3` failed retries (roughly `3 * JOB_GRADING_RETRY_INTERVAL_S`
after the original submit, ~90s at defaults, though batching across many
pending rows can stretch this), the attempt is marked terminal:
`status="grading_failed"`, `grader_output=None`.
**What the user sees:** the streak already counted at submit time (D-19,
unaffected by any of this). While pending, the session player shows
"Reviewing your answer…"; once the poll (`GET /attempts/{id}`, `Retry-After:
3`) observes `grading_failed`, the frontend (`Session.tsx`) shows: *"We
couldn't grade this one. Your streak still counts."* with a Next button --
no score, no rubric hits/misses, no reference answer for that one exercise;
the session otherwise continues normally. If the poll itself runs past
`MAX_POLL_MS` (2 minutes) before a terminal state is reached, the frontend
instead shows *"We'll grade this shortly. Your streak already counted, so
keep going."* and lets the user move on -- a stuck grade can never freeze
the session (D-60).
**First response to an `insufficient_quota` alert:** this is a billing/quota
issue, not a code bug -- check the OpenAI dashboard, top up or fix billing,
no redeploy needed (the very next `grading_retry` tick after quota is
restored will pick up and resolve any still-`grading_pending` rows; only
rows that already exhausted their 3 retries and flipped to `grading_failed`
are permanently lost and need a manual note to affected users, there is no
"unfail" path today).

## 6. Alert catalog

No paging integration (PagerDuty/Opsgenie/etc.) exists in this codebase at
MVP -- everything below is a structured log line (and, for unhandled
exceptions, a Sentry event) today. Wire whichever of these your log
aggregation / Sentry alert rules should page on; this table is the
prioritized list of what's worth paging on and the first response, not a
description of an already-wired pipeline.

| Signal | Where it fires | Page? | First response |
|---|---|---|---|
| `refresh_token_reuse_detected` | `core/events.py::alert_refresh_reuse`, on any reuse of a rotated/revoked refresh token (`auth/service.py`) | Yes, if the rate is anomalous (a handful/day can be normal client retry races; a spike is credential-stuffing) | Check the logged `user_id`/`family_id`; family-kill is post-MVP (D-4), so today the response is manual: consider forcing that user's re-auth, watch for a broader pattern across users |
| `dispute_opened` | `core/events.py::alert_dispute_opened`, on every `POST /.../dispute` | No (informational); DO page on a rate spike -- see the metrics-based alert below | Read the dispute body; if it names a wrong answer key, pull the exercise (section 3) |
| Per-exercise dispute rate spike | `GET /admin/metrics` -> `dispute_rate_by_exercise` (open disputes / graded attempts, top 20 by open-dispute count) | **Yes** -- this is one of the two non-negotiable golden signals (docs/06 M7): a spiking rate on ONE exercise means a bad answer key is live | Pull the exercise immediately (section 3), then investigate via `pipeline/review_cli show <id> <version>` |
| Climbing `pending_grade_count` | `GET /admin/metrics` -> `pending_grade_count` (`SELECT count(*) FROM attempts WHERE status='grading_pending'`) | **Yes** -- the other non-negotiable signal: a climbing count means the grader is failing | Follow section 5's degradation playbook; check `insufficient_quota` first (the most common real-world cause) |
| `attempt_insert_error_rate` spike | `GET /admin/metrics` -> `attempt_insert_error_rate` (Redis counters, `attempts/router.py`) | Yes, on a sustained nonzero rate | Check Sentry for the underlying exception; `POST /attempts` errors are unhandled exceptions (`ApiError`s are excluded from the numerator on purpose -- see the metric's own docstring) |
| `attempts_default_has_rows` | `jobs/partitions.py`, logged whenever the drain path runs | Yes, always -- steady state is zero rows | Confirm the job actually ran and recovered (section 2); if it's recurring, the cron/scheduler itself is unhealthy, not just one missed month |
| `attempts_partition_gap_recovered` | `jobs/partitions.py`, logged when more than one month is created in a single run | Yes -- this means the job was down for 1+ months | Find out why the scheduler/cron stopped running (deploy gap? `JOBS_ENABLED=false` left on?) before it happens again |
| Unhandled exception / 500 | Sentry (`app/core/sentry.py`), every request | Yes, on rate or on any exception touching payment/auth-adjacent code (there is none at MVP, but auth flows are the closest) | Look up by `request_id` (attached as a Sentry tag on every request, and returned in every error body) |
| `rate_limited` (429) spike from one identity | `core/ratelimit.py` buckets, visible via `X-RateLimit-*` response headers and application logs | No by default; yes if sustained and NOT correlated with a known abusive client | Check whether it's a single IP/user (likely abuse, no action needed -- the limiter is doing its job) vs. broad (likely a legitimate traffic spike or a client-side retry-storm bug) |
| One periodic job's `error_counts` climbing | `app/jobs/runner.py`, `periodic job %r failed` log line | Yes, if a job errors on every tick (one-off transient errors are expected and self-heal) | Read the traceback in the log; jobs are isolated (one failing never stops the others), so this is never itself an outage, but investigate before it becomes one |
| Disk usage > 80% | Infra-level (managed Postgres / host monitoring), not app code | Yes | Standard DB disk-pressure response: check `attempts` partition growth first (the hottest-growing table), consider WAL/backup retention if base+WAL is ever adopted (section 1) |
| Uptime check failure (`GET /healthz`) | Infra-level (external uptime monitor) | Yes, immediately | `/healthz` reports which dependency failed (`postgres`/`redis`) in its `503` body -- start there |
| `pytest` refuses to start (`DatabaseGuardError`) | `backend/tests/_db_guard.py`, raised at collection time from `conftest.py`'s module-level setup | No -- this is the guard working, not an incident | See section 7: point `DATABASE_URL`/`TEST_DATABASE_URL` at a database whose name ends in `_test`, or set `CODEREADER_TEST_DB=1` to explicitly confirm the target is disposable. Never silence this by editing the guard to pass |

## 7. Test-database isolation (pytest safety, D-88)

**The hazard.** `backend/tests/conftest.py`'s `migrated_db` fixture is
session-scoped and `autouse=True`: it runs `DROP SCHEMA public CASCADE`,
recreates the schema, and runs every migration to head, unconditionally, at
the start of every `pytest` invocation. Before D-88 this ran against
whatever `DATABASE_URL` resolved to -- and in this project, both the root
`.env` and `backend/.env` point `DATABASE_URL` at the SAME Postgres the API
and pipeline use for real content. A plain `pytest` run therefore silently
destroyed every table's real content. Confirmed by direct reproduction
during the D-87 (handauthored ingestion) work session: it happened twice in
one afternoon, destroying ~37 and then a further 24 real, some paid-for,
generated exercises.

**The fix.** `backend/tests/_db_guard.py` + a module-level block at the top
of `conftest.py`, executed before pytest imports any test module:
1. Resolve a target database: `TEST_DATABASE_URL` if explicitly set, else
   `app.config.get_settings().DATABASE_URL` with `_test` appended to the
   database name (e.g. `codereader` -> `codereader_test`). The base is read
   from `get_settings()`, not raw `os.environ`, because `DATABASE_URL` is
   normally supplied via the `.env` FILE, which pydantic-settings parses
   without ever writing it back into `os.environ` -- reading `os.environ`
   directly here previously produced a silently-wrong guessed default.
2. **Refuse to proceed** (`DatabaseGuardError`, loud, before any DB I/O)
   unless the target's database name ends in `_test`, or `CODEREADER_TEST_DB=1`
   is explicitly set -- mirrors the `CODEREADER_ALLOW_SEED=1` pattern
   (D-62): a destructive operation must be a conscious, structurally-guarded
   opt-in, never pytest's default side effect.
3. `CREATE DATABASE` the target if it does not exist yet ("created on
   demand" -- nothing to provision by hand, in dev or in CI).
4. Override the `DATABASE_URL` env var itself (clearing
   `get_settings`'s `@lru_cache` around the override) so every code path
   that resolves a database connection -- `alembic/env.py`, `app/db.py`'s
   `create_engine()` default, `app/main.py`'s lifespan, and three test files'
   own bare `create_engine()` calls -- transparently targets the isolated
   database with zero per-call-site changes. There is no code path left that
   can silently keep pointing at the real one.
5. `migrated_db` itself re-checks the guard immediately before its DROP
   SCHEMA, reading whatever `DATABASE_URL` actually resolves to at that
   moment -- belt and suspenders, independent of step 2 above.

**Result:** `pytest` on a dev machine, run with zero special configuration,
targets `codereader_test` (auto-created, freshly migrated every session) and
never touches `codereader`. Verified directly, not just by code review: a
342-test full-suite run's live-database row count was captured before and
after and found unchanged (`backend/tests/test_m7_db_isolation_guard.py`
also unit-tests the guard, the derivation, and the create-on-demand behavior
in isolation, without needing a second real wipe to prove any of it).

**If you need pytest to target something other than the default:** set
`TEST_DATABASE_URL` to any Postgres URL whose database name ends in `_test`
(no other configuration needed), or set both `TEST_DATABASE_URL` and
`CODEREADER_TEST_DB=1` if the disposable database's name doesn't happen to
end in `_test`. CI (`.github/workflows/ci.yml`, `pytest` job) sets
`TEST_DATABASE_URL` explicitly on the `pytest backend/tests` step so this is
never implicit there either.

**Do not** "fix" a `DatabaseGuardError` by editing `_db_guard.py` to accept
a non-`_test`-suffixed name without the flag, or by pointing `DATABASE_URL`
at the real database and setting `CODEREADER_TEST_DB=1` to force it through
-- that flag exists for a genuinely disposable database with an unusual
name, not as a bypass for "I don't want to rename my database."
