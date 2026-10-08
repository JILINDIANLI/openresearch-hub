#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -ne 1 || ! -f "$1" ]]; then echo "Usage: $0 postgres_YYYYMMDD_HHMM.sql.gz" >&2; exit 2; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
set -a; source .env.production; set +a
echo "This overwrites objects in $POSTGRES_DB. A current backup is required."
read -r -p "Type RESTORE to continue: " answer
[[ "$answer" == RESTORE ]] || { echo "Cancelled"; exit 1; }
gzip -dc -- "$1" | docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
