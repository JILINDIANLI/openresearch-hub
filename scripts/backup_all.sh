#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
./scripts/backup_postgres.sh
./scripts/backup_minio.sh
./scripts/backup_gitea.sh
echo "Backups complete. Keep .env.production outside backup archives; protect backups with encrypted off-host storage."
