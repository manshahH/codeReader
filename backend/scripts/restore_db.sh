#!/usr/bin/env bash
# Restore a pg_dump backup produced by backup_db.sh (M7). Restores into a
# NEW database by default (never overwrites TARGET_DB_NAME's existing data
# out from under a running app) -- pass --replace to drop and recreate
# TARGET_DB_NAME in place instead, for an actual incident.
#
# Usage:
#   ./restore_db.sh path/to/codereader_2026-07-11T2015Z.dump [--replace]
#
# Docker-compose dev/staging: set POSTGRES_CONTAINER. Managed Postgres
# (production): set DATABASE_URL (the restore target's connection string,
# database name in DATABASE_URL is ignored -- TARGET_DB_NAME wins).
set -euo pipefail

DUMP_FILE="${1:?usage: restore_db.sh <dump-file> [--replace]}"
REPLACE="${2:-}"
TARGET_DB_NAME="${TARGET_DB_NAME:-codereader_restore_drill}"
ADMIN_DB_NAME="${ADMIN_DB_NAME:-codereader}"
DB_USER="${POSTGRES_USER:-codereader}"

if [ ! -f "$DUMP_FILE" ]; then
  echo "restore_db: dump file not found: $DUMP_FILE" >&2
  exit 1
fi

run_psql() {
  if [ -n "${POSTGRES_CONTAINER:-}" ]; then
    docker exec "$POSTGRES_CONTAINER" psql -U "$DB_USER" -d "$ADMIN_DB_NAME" -c "$1"
  else
    psql "${DATABASE_URL:?DATABASE_URL is required when POSTGRES_CONTAINER is unset}" -c "$1"
  fi
}

if [ "$REPLACE" = "--replace" ]; then
  echo "restore_db: DROPPING and recreating ${TARGET_DB_NAME} (--replace)" >&2
  run_psql "DROP DATABASE IF EXISTS ${TARGET_DB_NAME};"
fi
run_psql "CREATE DATABASE ${TARGET_DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true

if [ -n "${POSTGRES_CONTAINER:-}" ]; then
  # See backup_db.sh: `sh -c '...'` avoids Git-Bash/MSYS path mangling on
  # Windows and is a no-op on Linux.
  REMOTE_NAME="$(basename "$DUMP_FILE")"
  docker cp "$DUMP_FILE" "${POSTGRES_CONTAINER}:/tmp/${REMOTE_NAME}"
  docker exec "$POSTGRES_CONTAINER" sh -c \
    "pg_restore -U '$DB_USER' -d '$TARGET_DB_NAME' --no-owner --exit-on-error /tmp/${REMOTE_NAME}"
  docker exec "$POSTGRES_CONTAINER" sh -c "rm /tmp/${REMOTE_NAME}"
else
  pg_restore -d "$TARGET_DB_NAME" --no-owner --exit-on-error "$DUMP_FILE"
fi

echo "restore_db: restored ${DUMP_FILE} into database ${TARGET_DB_NAME}"
