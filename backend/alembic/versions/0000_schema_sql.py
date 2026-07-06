"""schema sql baseline

Revision ID: 0000_schema_sql
Revises:
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Iterator, Sequence

from alembic import op

revision: str = "0000_schema_sql"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA_SQL = r"""
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TABLE users (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  username            citext      NOT NULL UNIQUE,
  display_name        text,
  avatar_url          text,
  timezone            text        NOT NULL DEFAULT 'UTC',
  level               text        NOT NULL DEFAULT 'mid'
                        CHECK (level IN ('junior','mid','senior')),
  reminder_local_time time,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  deleted_at          timestamptz
);

CREATE TRIGGER trg_users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE auth_identities (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider           text        NOT NULL CHECK (provider IN ('github')),
  provider_user_id   text        NOT NULL,
  provider_login     text,
  access_token_enc   bytea,
  token_scopes       text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_auth_identities_user ON auth_identities (user_id);

CREATE TABLE refresh_tokens (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id    uuid        NOT NULL,
  token_hash   bytea       NOT NULL UNIQUE,
  issued_at    timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  rotated_at   timestamptz,
  revoked_at   timestamptz,
  user_agent   text,
  ip           inet
);

CREATE INDEX idx_refresh_tokens_user   ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

CREATE TABLE exercises (
  id                    uuid        NOT NULL,
  version               int         NOT NULL DEFAULT 1 CHECK (version >= 1),
  language              text        NOT NULL CHECK (language IN ('python')),
  type                  text        NOT NULL
                          CHECK (type IN ('spot_the_bug','trace','summarize')),
  grading_mode          text        NOT NULL
                          CHECK (grading_mode IN ('deterministic','rubric')),
  difficulty_authored   smallint    NOT NULL CHECK (difficulty_authored BETWEEN 1 AND 10),
  difficulty_empirical  numeric(4,2),
  concepts              text[]      NOT NULL CHECK (cardinality(concepts) >= 1),
  tags                  text[]      NOT NULL DEFAULT '{}',
  est_time_s            int         NOT NULL DEFAULT 90,
  status                text        NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','in_review','live','pulled','retired')),
  source                jsonb       NOT NULL,
  payload               jsonb       NOT NULL,
  grading               jsonb       NOT NULL,
  explanation           jsonb       NOT NULL,
  validation_report_url text,
  human_reviewed        boolean     NOT NULL DEFAULT false,
  created_at            timestamptz NOT NULL DEFAULT now(),
  validated_at          timestamptz,
  published_at          timestamptz,
  PRIMARY KEY (id, version)
);

CREATE INDEX idx_exercises_serve
  ON exercises (language, type, status, difficulty_authored)
  WHERE status = 'live';
CREATE INDEX idx_exercises_concepts ON exercises USING gin (concepts);

CREATE VIEW exercises_current AS
SELECT DISTINCT ON (id) *
FROM exercises
WHERE status = 'live'
ORDER BY id, version DESC;

CREATE TABLE daily_sessions (
  user_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_date  date        NOT NULL,
  exercise_list jsonb       NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  PRIMARY KEY (user_id, session_date)
);

CREATE TABLE attempts (
  id               bigint      GENERATED ALWAYS AS IDENTITY,
  user_id          uuid        NOT NULL REFERENCES users(id),
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  session_date     date        NOT NULL,
  answer           jsonb       NOT NULL,
  grading_mode     text        NOT NULL CHECK (grading_mode IN ('deterministic','rubric')),
  status           text        NOT NULL DEFAULT 'graded'
                     CHECK (status IN ('graded','grading_pending','grading_failed')),
  is_correct       boolean,
  score            numeric(4,3) CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  grader_output    jsonb,
  time_taken_ms    int,
  client           text        NOT NULL DEFAULT 'web' CHECK (client IN ('web','pwa')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  graded_at        timestamptz,
  PRIMARY KEY (id, created_at),
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_attempts_user ON attempts (user_id, created_at DESC);
CREATE INDEX idx_attempts_ex   ON attempts (exercise_id, exercise_version, created_at);

CREATE TABLE attempts_2026_07 PARTITION OF attempts
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE attempts_2026_08 PARTITION OF attempts
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE attempts_default PARTITION OF attempts DEFAULT;

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

CREATE TABLE user_concept_state (
  user_id        uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  concept        text        NOT NULL,
  mastery        numeric(4,3) NOT NULL DEFAULT 0 CHECK (mastery >= 0 AND mastery <= 1),
  attempts       int         NOT NULL DEFAULT 0,
  correct        int         NOT NULL DEFAULT 0,
  last_seen_at   timestamptz,
  next_review_at timestamptz,
  PRIMARY KEY (user_id, concept)
);

CREATE INDEX idx_ucs_due ON user_concept_state (user_id, next_review_at);

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
  attempt_id       bigint,
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
"""


DOWNGRADE_SQL = """
DROP INDEX IF EXISTS idx_disputes_ex;
DROP INDEX IF EXISTS idx_disputes_open;
DROP TABLE IF EXISTS disputes;
DROP TABLE IF EXISTS exercise_stats;
DROP INDEX IF EXISTS idx_ucs_due;
DROP TABLE IF EXISTS user_concept_state;
DROP INDEX IF EXISTS idx_streak_events_user;
DROP TABLE IF EXISTS streak_events;
DROP TRIGGER IF EXISTS trg_user_stats_touch ON user_stats;
DROP TABLE IF EXISTS user_stats;
DROP TABLE IF EXISTS attempts;
DROP TABLE IF EXISTS daily_sessions;
DROP VIEW IF EXISTS exercises_current;
DROP INDEX IF EXISTS idx_exercises_concepts;
DROP INDEX IF EXISTS idx_exercises_serve;
DROP TABLE IF EXISTS exercises;
DROP INDEX IF EXISTS idx_refresh_tokens_family;
DROP INDEX IF EXISTS idx_refresh_tokens_user;
DROP TABLE IF EXISTS refresh_tokens;
DROP INDEX IF EXISTS idx_auth_identities_user;
DROP TABLE IF EXISTS auth_identities;
DROP TRIGGER IF EXISTS trg_users_touch ON users;
DROP TABLE IF EXISTS users;
DROP FUNCTION IF EXISTS touch_updated_at();
"""


def _split_sql(sql: str) -> Iterator[str]:
    start = 0
    index = 0
    in_dollar_quote = False
    while index < len(sql):
        if sql.startswith("$$", index):
            in_dollar_quote = not in_dollar_quote
            index += 2
            continue
        if sql[index] == ";" and not in_dollar_quote:
            statement = sql[start:index].strip()
            if statement:
                yield statement
            start = index + 1
        index += 1

    statement = sql[start:].strip()
    if statement:
        yield statement


def _execute_sql_batch(sql: str) -> None:
    for statement in _split_sql(sql):
        op.execute(statement)


def upgrade() -> None:
    # Raw SQL is intentional for parity with db/schema.sql. SQLAlchemy models do
    # not own declarative partition DDL, views, or triggers.
    _execute_sql_batch(SCHEMA_SQL)


def downgrade() -> None:
    _execute_sql_batch(DOWNGRADE_SQL)
