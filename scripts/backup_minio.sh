#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
set -a; source .env.production; set +a
DEST="${BACKUP_DIR:-./backup/private}/minio-$(date -u +%Y%m%d_%H%M)"
mkdir -p "$DEST"; chmod 700 "$DEST"
docker run --rm --network openresearch_internal -v "$DEST:/backup" \
  -e MINIO_ACCESS_KEY -e MINIO_SECRET_KEY -e MINIO_BUCKET minio/mc:RELEASE.2025-04-16T18-13-26Z \
  sh -c 'mc alias set source http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" && mc mirror --overwrite "source/$MINIO_BUCKET" /backup'
echo "MinIO backup: $DEST"
