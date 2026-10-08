#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -ne 1 || ! -d "$1" ]]; then echo "Usage: $0 backup/private/minio-TIMESTAMP" >&2; exit 2; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
set -a; source .env.production; set +a
echo "This mirrors backup contents into bucket $MINIO_BUCKET. Existing objects are retained unless overwritten."
read -r -p "Type RESTORE to continue: " answer; [[ "$answer" == RESTORE ]] || exit 1
docker run --rm --network openresearch_internal -v "$(realpath "$1"):/backup:ro" \
  -e MINIO_ACCESS_KEY -e MINIO_SECRET_KEY -e MINIO_BUCKET minio/mc:RELEASE.2025-04-16T18-13-26Z \
  sh -c 'mc alias set target http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" && mc mb --ignore-existing "target/$MINIO_BUCKET" && mc mirror --overwrite /backup "target/$MINIO_BUCKET"'
