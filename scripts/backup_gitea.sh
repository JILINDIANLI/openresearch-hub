#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
DEST="${BACKUP_DIR:-./backup/private}/gitea-$(date -u +%Y%m%d_%H%M)"
mkdir -p "$DEST"; chmod 700 "$DEST"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T gitea \
  su git -c 'gitea dump -c /data/gitea/conf/app.ini -f /tmp/gitea-dump.zip'
docker compose --env-file .env.production -f docker-compose.prod.yml cp gitea:/tmp/gitea-dump.zip "$DEST/gitea-dump.zip"
chmod 600 "$DEST/gitea-dump.zip"
echo "Gitea backup: $DEST/gitea-dump.zip"
