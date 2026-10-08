# OpenResearch Hub Production Deployment

## Status and architecture

This repository contains production deployment preparation, not a completed public deployment. No server, registered domain, DNS control, or real TLS certificate was supplied.

```text
Internet -> DNS -> Nginx (80 redirect / 443 TLS)
                       |-> backend (FastAPI + static frontend)
                       |-> Gitea (git subdomain)
                       `-> MinIO S3 API (storage subdomain; no Console)
Internal Docker network: PostgreSQL, Redis, MinIO, Gitea, backend
Persistent volumes: postgres_data, redis_data, minio_data, gitea_data
```

See `docker-compose.prod.yml` and `deploy/nginx/openresearch.conf`. Only Nginx 80/443 and optional Gitea SSH 2222 are host-published. Database, Redis, MinIO, Gitea HTTP, and backend have no host port mapping.

## Host and DNS

Suggested starting point: 4 CPU / 8 GB RAM / 100 GB SSD for a small internal deployment; 8+ CPU / 16+ GB RAM and SSD for regular multi-user use. Size storage from uploaded files, repositories, database growth, concurrency, and backup retention.

Create A/AAAA records for `research.example.com`, `git.example.com`, `storage.example.com`. Point all names at the server. Gitea advertises HTTPS clone URLs and SSH URLs using its dedicated hostname. MinIO Console remains private; only its S3 API hostname is proxied for presigned downloads.

## Environment and secrets

Copy `.env.production.example` to `.env.production`. Set all placeholders to unique credentials. `SECRET_KEY`, `JWT_SECRET`, PostgreSQL, Redis, MinIO, and Gitea credentials must not be committed or included in backup archives. Restrict the file to the deployment operator. `CORS_ORIGINS` must be the exact HTTPS frontend origin; never use `*`. `TRUSTED_HOSTS` must enumerate actual hostnames. Set `MAX_UPLOAD_SIZE` to the same value allowed by Nginx. API docs are disabled at the proxy by default.

## Docker, migration, and start

Install Docker Engine and Compose plugin on Linux, clone the repository, configure environment, DNS, and certificates, then run `./scripts/deploy.sh`. The script validates Compose, backs up, builds, starts dependencies, runs Alembic, starts backend/Nginx, and checks the backend health endpoint. Migration failure aborts deployment. Never use `docker compose down -v` on production. Take an independent snapshot before schema changes; an Alembic downgrade is not guaranteed to restore data.

Let's Encrypt: request a SAN certificate for the three hostnames with Certbot standalone while ports 80/443 are available, then start Compose. Schedule `certbot renew` twice daily and reload Nginx after successful renewal. Nginx enforces HTTPS redirects and security headers.

## First administrator

Do not use the seeded demo credentials. The backend provides a controlled one-time `POST /api/auth/bootstrap-admin` endpoint only when `APP_ENV=production`, `ALLOW_ADMIN_BOOTSTRAP=true`, and a matching `ADMIN_BOOTSTRAP_KEY` header are configured. It refuses to run after any account exists. Set `ALLOW_ADMIN_BOOTSTRAP=false` and remove the bootstrap key immediately after the first administrator is created.

## Backup and restore

Run `scripts/backup_all.sh` for PostgreSQL, MinIO, and Gitea. Backups are placed under `BACKUP_DIR` (default `backup/private`, gitignored) and should be encrypted and copied off-host. PostgreSQL dumps are compressed; MinIO is mirrored; Gitea uses its native dump. Configure off-host retention: daily 7 days, weekly 4 weeks, monthly 6 months. Do not archive `.env.production`. Run `python scripts/reconcile_storage.py` from the backend container at least weekly as a dry run; only use `--delete-orphans` after reviewing the report and confirming a backup.

PostgreSQL restore is destructive and requires typing `RESTORE`. MinIO restore mirrors objects and preserves unrelated target objects. Gitea restore currently requires a maintenance window and documented manual native dump restoration into a separately snapshotted volume; the provided restore helper intentionally refuses to replace a live volume. Restore tests must run in an isolated environment, not against production.

## Upgrade and rollback

Set `BACKEND_IMAGE` to a dated immutable image tag and retain the prior image. Deploy after backup. On application failure, restore the previous image tag and restart backend/Nginx. If a migration is irreversible or incompatible with the old image, application rollback alone is unsafe; restore a tested database backup into an isolated replacement and follow an approved recovery window. Never delete persistent volumes during rollback.

## Known readiness gaps

The source now uses Alembic in production deployment, exposes only a minimal health response, has request IDs, TrustedHost checks, readiness checks, Redis-backed rate limiting, explicit administrator-delete confirmation, resource visibility enforcement, and session-token revocation. Remaining launch work is environmental: public DNS and HTTPS validation, an isolated restore rehearsal, off-host backup retention verification, a malware-scanning integration appropriate for uploaded research artifacts, and long-running production load testing. Do not describe localhost checks as public production deployment.
