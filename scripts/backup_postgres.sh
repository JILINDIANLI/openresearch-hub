#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
set -a; source .env.production; set +a
DEST="${BACKUP_DIR:-./backup/private}"
mkdir -p "$DEST"
chmod 700 "$DEST"
STAMP="$(date -u +%Y%m%d_%H%M)"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner --no-privileges \
  | gzip -9 > "$DEST/postgres_${STAMP}.sql.gz"
chmod 600 "$DEST/postgres_${STAMP}.sql.gz"
echo "PostgreSQL backup: $DEST/postgres_${STAMP}.sql.gz"
