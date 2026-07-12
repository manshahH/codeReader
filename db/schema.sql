-- ============================================================
-- Code Reading App : MVP Schema
-- Postgres 16+
-- Conventions:
--   * text + CHECK instead of enums (cheaper to migrate at MVP)
--   * timestamptz everywhere; user-local dates stored as date
--   * soft delete only on users; everything else is append/immutable
--   * all JSONB blobs are written by the server only, never by clients
-- ============================================================

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ------------------------------------------------------------
-- updated_at helper
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ============================================================
-- IDENTITY
-- ============================================================

CREATE TABLE users (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  username            citext      NOT NULL UNIQUE,          -- seeded from GitHub login
  display_name        text,
  avatar_url          text,
  timezone            text        NOT NULL DEFAULT 'UTC',   -- IANA name, validated in app
  level               text        NOT NULL DEFAULT 'mid'
                        CHECK (level IN ('junior','mid','senior')),
  onboarded           boolean     NOT NULL DEFAULT false,     -- set true by PATCH /me's level pick
  beta_allowed        boolean     NOT NULL DEFAULT false,     -- gates login/session access (M8)
  reminder_local_time time,                                  -- NULL = reminders off
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  deleted_at          timestamptz                            -- soft delete
);

CREATE TRIGGER trg_users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Provider-agnostic identities. MVP has exactly one row per user
-- (provider = 'github') but the shape is multi-provider from day one.
CREATE TABLE auth_identities (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider           text        NOT NULL CHECK (provider IN ('github')),
  provider_user_id   text        NOT NULL,                  -- GitHub numeric id as text
  provider_login     text,                                  -- GitHub handle at link time
  access_token_enc   bytea,                                 -- AES-GCM sealed, key in KMS
  token_scopes       text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_auth_identities_user ON auth_identities (user_id);

-- Rotating opaque refresh tokens. family_id exists now (cheap) so the
-- post-MVP reuse-detection "kill the family" upgrade is a code change,
-- not a migration. MVP behavior on reuse: log + alert only.
CREATE TABLE refresh_tokens (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id    uuid        NOT NULL,                 -- constant across rotations
  token_hash   bytea       NOT NULL UNIQUE,          -- sha256 of the opaque token
  issued_at    timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  rotated_at   timestamptz,                          -- set when superseded
  revoked_at   timestamptz,                          -- logout / admin action
  user_agent   text,
  ip           inet
);

CREATE INDEX idx_refresh_tokens_user   ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

-- Beta allowlist (M8): an admin invites a GitHub handle here BEFORE that
-- person ever logs in; upsert_github_user() flips users.beta_allowed on the
-- matching row the moment they authenticate. Also the record of "who did we
-- invite", independent of whether they've shown up yet.
CREATE TABLE beta_invites (
  github_login citext      PRIMARY KEY,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- CONTENT
-- ============================================================
-- Exercises are IMMUTABLE per (id, version). Fixing anything bumps
-- version. Serving picks the max live version per id.
-- payload  : what the client may see BEFORE answering
-- grading  : answer key / rubric. NEVER serialized to clients pre-answer.
-- explanation : revealed only in the grade response.

CREATE TABLE exercises (
  id                    uuid        NOT NULL,
  version               int         NOT NULL DEFAULT 1 CHECK (version >= 1),
  language              text        NOT NULL CHECK (language IN ('python')),
  type                  text        NOT NULL
                          CHECK (type IN ('spot_the_bug','trace','summarize','predict_the_fix')),
  grading_mode          text        NOT NULL
                          CHECK (grading_mode IN ('deterministic','rubric')),
  difficulty_authored   smallint    NOT NULL CHECK (difficulty_authored BETWEEN 1 AND 10),
  difficulty_empirical  numeric(4,2),                -- backfilled post-launch
  concepts              text[]      NOT NULL CHECK (cardinality(concepts) >= 1),
  tags                  text[]      NOT NULL DEFAULT '{}',
  est_time_s            int         NOT NULL DEFAULT 90,
  status                text        NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','in_review','live','pulled','retired')),
  source                jsonb       NOT NULL,        -- origin/model/prompt_template_id/...
  payload               jsonb       NOT NULL,
  grading               jsonb       NOT NULL,
  explanation           jsonb       NOT NULL,
  validation_report_url text,                        -- s3:// pointer
  human_reviewed        boolean     NOT NULL DEFAULT false,
  created_at            timestamptz NOT NULL DEFAULT now(),
  validated_at          timestamptz,
  published_at          timestamptz,
  PRIMARY KEY (id, version)
);

-- Serving-path indexes
CREATE INDEX idx_exercises_serve
  ON exercises (language, type, status, difficulty_authored)
  WHERE status = 'live';
CREATE INDEX idx_exercises_concepts ON exercises USING gin (concepts);

-- Convenience: latest live version per exercise id
CREATE VIEW exercises_current AS
SELECT DISTINCT ON (id) *
FROM exercises
WHERE status = 'live'
ORDER BY id, version DESC;

-- ============================================================
-- DAILY SESSIONS
-- ============================================================
-- The durable record of "what was in your session today".
-- Redis caches it; if Redis flushes, we re-read this row instead of
-- re-sampling (users must not see a different session on re-open).

CREATE TABLE daily_sessions (
  user_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_date  date        NOT NULL,                -- user-local date
  exercise_list jsonb       NOT NULL,                -- [{exercise_id, version, slot, is_boss}]
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  PRIMARY KEY (user_id, session_date)
);

-- ============================================================
-- ATTEMPTS  (hottest table; partitioned from day one)
-- ============================================================
-- Append-only. Rubric grading updates ONLY status/is_correct/score/
-- grader_output/graded_at on the same row (MVP simplification; splits
-- into grading_results post-MVP if the update contention ever shows).

CREATE TABLE attempts (
  id               bigint      GENERATED ALWAYS AS IDENTITY,
  user_id          uuid        NOT NULL REFERENCES users(id),
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  session_date     date        NOT NULL,             -- user-local date it counted toward
  answer           jsonb       NOT NULL,             -- shape depends on exercise type
  grading_mode     text        NOT NULL CHECK (grading_mode IN ('deterministic','rubric')),
  status           text        NOT NULL DEFAULT 'graded'
                     CHECK (status IN ('graded','grading_pending','grading_failed','skipped')),
  is_correct       boolean,                          -- NULL while rubric pending
  score            numeric(4,3) CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  grader_output    jsonb,                            -- rubric hits/misses, for the UI
  time_taken_ms    int,
  client           text        NOT NULL DEFAULT 'web' CHECK (client IN ('web','pwa')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  graded_at        timestamptz,
  PRIMARY KEY (id, created_at),                      -- partition key must be in PK
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
) PARTITION BY RANGE (created_at);

-- NOTE: uniqueness of Idempotency-Key is enforced in Redis (24h TTL),
-- not here; a partitioned unique constraint would have to include
-- created_at, which defeats it. Accepted MVP tradeoff: a replay after
-- Redis data loss inserts a duplicate, which the stats job dedupes.

CREATE INDEX idx_attempts_user ON attempts (user_id, created_at DESC);
CREATE INDEX idx_attempts_ex   ON attempts (exercise_id, exercise_version, created_at);

-- Bootstrap partitions + safety net. A monthly cron creates the next
-- partition; the DEFAULT partition guarantees inserts never fail if
-- the cron is missed (alert if it ever receives rows).
CREATE TABLE attempts_2026_07 PARTITION OF attempts
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE attempts_2026_08 PARTITION OF attempts
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE attempts_default PARTITION OF attempts DEFAULT;

-- ============================================================
-- PRECOMPUTED USER STATE  (nothing user-facing aggregates attempts live)
-- ============================================================

CREATE TABLE user_stats (
  user_id                uuid        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  current_streak         int         NOT NULL DEFAULT 0,
  longest_streak         int         NOT NULL DEFAULT 0,
  last_active_local_date date,
  streak_freezes         int         NOT NULL DEFAULT 0,
  total_attempts         int         NOT NULL DEFAULT 0,
  total_correct          int         NOT NULL DEFAULT 0,
  accuracy_by_type       jsonb       NOT NULL DEFAULT '{}',
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_user_stats_touch BEFORE UPDATE ON user_stats
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Streaks are the retention crown jewel: every transition is audited
-- so any "my streak vanished" ticket is answerable in one query.
CREATE TABLE streak_events (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event       text        NOT NULL
                CHECK (event IN ('extended','reset','freeze_used','repaired','adjusted')),
  from_value  int         NOT NULL,
  to_value    int         NOT NULL,
  local_date  date        NOT NULL,
  note        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_streak_events_user ON streak_events (user_id, created_at DESC);

-- H1/D-104: a streak transition ('extended'/'reset') happens at most once per
-- user per local day. This partial unique index is the un-raceable DB backstop
-- (under the per-(user, day) advisory lock in attempts/service.py) against a
-- concurrent same-day submit writing two transition rows for one transition.
-- 'repaired'/'freeze_used'/'adjusted' are separate event kinds and unconstrained.
CREATE UNIQUE INDEX uq_streak_events_one_transition_per_day
  ON streak_events (user_id, local_date)
  WHERE event IN ('extended', 'reset');

-- Spaced repetition + skill graph state, keyed to the controlled
-- concept taxonomy (validated app-side against a versioned list).
CREATE TABLE user_concept_state (
  user_id        uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  concept        text        NOT NULL,
  mastery        numeric(4,3) NOT NULL DEFAULT 0 CHECK (mastery >= 0 AND mastery <= 1),
  attempts       int         NOT NULL DEFAULT 0,
  correct        int         NOT NULL DEFAULT 0,
  declined       int         NOT NULL DEFAULT 0,   -- "I don't know" count; never inflates attempts/correct
  last_seen_at   timestamptz,
  next_review_at timestamptz,
  PRIMARY KEY (user_id, concept)
);

CREATE INDEX idx_ucs_due ON user_concept_state (user_id, next_review_at);

-- ============================================================
-- CONTENT FEEDBACK LOOP
-- ============================================================

-- Periodic job output; "only 31% caught this". App hides until n >= 30.
CREATE TABLE exercise_stats (
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  attempts_count   int         NOT NULL DEFAULT 0,
  correct_count    int         NOT NULL DEFAULT 0,
  solve_rate       numeric(4,3),
  median_time_ms   int,
  computed_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (exercise_id, exercise_version),
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
);

CREATE TABLE disputes (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  user_id          uuid        NOT NULL REFERENCES users(id),
  attempt_id       bigint,                           -- soft link (partitioned parent)
  reason           text        NOT NULL
                     CHECK (reason IN ('wrong_answer','ambiguous','broken_code',
                                       'bad_explanation','other')),
  body             text,
  status           text        NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','accepted','rejected')),
  resolution_note  text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  resolved_at      timestamptz,
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
);

CREATE INDEX idx_disputes_open ON disputes (status, created_at) WHERE status = 'open';
CREATE INDEX idx_disputes_ex   ON disputes (exercise_id, exercise_version);

-- Beta feedback (D-93c): one review per user, upserted. Separate from
-- disputes -- a dispute is about a specific exercise/answer key, a review is
-- about the product as a whole.
CREATE TABLE reviews (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  rating      smallint    NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body        text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_reviews_touch BEFORE UPDATE ON reviews
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Append-only: one row per POST /v1/me/review call, never updated or
-- deleted. reviews (above) stays the current opinion via upsert; this is
-- the record of how it got there, so a rating change over time is visible.
CREATE TABLE review_history (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating      smallint    NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_review_history_user ON review_history (user_id, created_at);

-- ============================================================
-- OPERATIONAL NOTES (not DDL)
-- ============================================================
-- * Redis owns: idempotency keys, OAuth state, rate limits, session cache.
-- * Attempt events additionally appended as JSONL to S3 (analytics later).
-- * Backups: daily base + WAL; restore drill BEFORE launch.
-- * Monthly cron: create next attempts partition; alert if attempts_default
--   ever has rows.
