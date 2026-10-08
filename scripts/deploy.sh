#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
[[ -f .env.production ]] || { echo "Create .env.production from .env.production.example first" >&2; exit 2; }
compose=(docker compose --env-file .env.production -f docker-compose.prod.yml)
"${compose[@]}" config --quiet
"${compose[@]}" build backend
"${compose[@]}" up -d postgres redis minio gitea
./scripts/backup_all.sh
"${compose[@]}" run --rm --no-deps backend sh -c 'cd /app/backend && alembic upgrade head'
"${compose[@]}" up -d backend nginx
for attempt in $(seq 1 30); do
  if "${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"; then
    echo "Deployment healthy"; exit 0
  fi
  sleep 4
done
echo "Health check failed. Previous image tag: ${BACKEND_IMAGE:-openresearch-backend:local}. Review logs; volumes were not removed." >&2
"${compose[@]}" ps
exit 1
