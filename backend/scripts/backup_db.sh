#!/usr/bin/env bash
# Daily Postgres backup (M7). pg_dump custom-format, not base backup + WAL --
# see docs/07-decisions.md D-64 for why pg_dump is sufficient at MVP scale
# (docs/03: ~25k attempts/day, one small box, no tenants to isolate).
#
# Usage: BACKUP_DIR=/var/backups/codereader ./backup_db.sh
# Cron (daily at 02:00 local): 0 2 * * * BACKUP_DIR=/var/backups/codereader DATABASE_URL=... /path/to/backup_db.sh
#
# Requires: pg_dump on PATH (or POSTGRES_CONTAINER set to run it via `docker
# exec` instead, for the docker-compose dev/staging topology).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backend/data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u '+%Y-%m-%dT%H%MZ')"
FILENAME="codereader_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

if [ -n "${POSTGRES_CONTAINER:-}" ]; then
  # docker-compose dev/staging: dump inside the container, then copy out.
  # `docker exec ... sh -c '...'` (one compound string argument), not a
  # bare /tmp/... argv entry, so Git-Bash/MSYS on Windows won't try to
  # rewrite it into a host path before it reaches docker.exe -- keeps this
  # script runnable from either environment; a no-op wrapper on Linux.
  docker exec "$POSTGRES_CONTAINER" sh -c \
    "pg_dump -U '${POSTGRES_USER:-codereader}' -d '${POSTGRES_DB:-codereader}' -F c -f /tmp/${FILENAME}"
  docker cp "${POSTGRES_CONTAINER}:/tmp/${FILENAME}" "${BACKUP_DIR}/${FILENAME}"
  docker exec "$POSTGRES_CONTAINER" sh -c "rm /tmp/${FILENAME}"
else
  # Managed Postgres (production): DATABASE_URL carries the connection info.
  pg_dump "${DATABASE_URL:?DATABASE_URL is required when POSTGRES_CONTAINER is unset}" \
    -F c -f "${BACKUP_DIR}/${FILENAME}"
fi

echo "backup_db: wrote ${BACKUP_DIR}/${FILENAME}"

# Prune backups older than RETENTION_DAYS. Fails loudly if BACKUP_DIR is
# somehow empty/unset rather than silently deleting from the wrong place.
find "$BACKUP_DIR" -maxdepth 1 -name 'codereader_*.dump' -mtime "+${RETENTION_DAYS}" -print -delete
