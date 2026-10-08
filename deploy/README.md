# Production deployment quick start

Production deployment uses Docker Compose; no service is installed directly on the host. The project currently has no supplied server or real domain. Replace every `example.com` value before starting.

## Prerequisites

Use a supported Linux server with Docker Engine and the Compose plugin. For a small internal deployment, plan around 4 CPU, 8 GB RAM, and 100 GB SSD; for regular multi-user use, start around 8 CPU, 16 GB RAM, and SSD storage. File and Git growth determine actual storage needs. Open TCP 80 and 443; optionally open the configured Gitea SSH port (default 2222). Do not expose 5432, 6379, 9000, 9001, 3000, or 8000 publicly.

Create DNS A/AAAA records for `research.example.com`, `git.example.com`, and `storage.example.com` pointing to the server. This deployment uses separate Gitea and MinIO API hostnames. MinIO Console is not proxied. The MinIO API hostname is intended for short-lived presigned file URLs only.

## Configure and obtain HTTPS

Copy `.env.production.example` to `.env.production` on the server and use unique generated secrets for every credential. Set `APP_DOMAIN`, `APP_BASE_URL`, `GITEA_DOMAIN`, `MINIO_PUBLIC_ENDPOINT`, `CORS_ORIGINS`, `TRUSTED_HOSTS`, `CERTBOT_EMAIL`, and make `MAX_UPLOAD_SIZE` match Nginx's `client_max_body_size` (currently 200 MiB). Set `REDIS_PASSWORD`; it is required by Compose. Keep `.env.production` mode 600 and out of source control/backups.

Before the first HTTPS start, request a certificate in standalone mode while ports 80/443 are free:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm --service-ports certbot certonly --standalone --preferred-challenges http -d "$APP_DOMAIN" -d "$GITEA_DOMAIN" -d "$MINIO_PUBLIC_ENDPOINT" --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email
```

Then start the edge proxy and services with `./scripts/deploy.sh`. Certbot renewal should run at least twice daily with a host scheduler; after a successful renewal run `docker compose --env-file .env.production -f docker-compose.prod.yml exec nginx nginx -s reload`. A renewal timer/unit is an operator responsibility. Nginx redirects all ordinary HTTP requests to HTTPS.

## Database and first admin

The deployment script takes a backup, builds the backend, waits for dependencies, runs `alembic upgrade head`, then starts the app and checks health. It never removes volumes. In production, backend startup skips demo seeding, `create_all`, and schema compatibility mutations; the deploy script applies Alembic migrations before starting the app. For initial setup, temporarily set `ALLOW_ADMIN_BOOTSTRAP=true` and a long random `ADMIN_BOOTSTRAP_KEY`, then POST the normal registration payload to `/api/auth/bootstrap-admin` with the `X-Admin-Bootstrap-Key` header. This endpoint only works while the user table is empty. Immediately set bootstrap back to false and remove the key, then recreate the backend container. Public registration is blocked until an active administrator exists.

## Acceptance

Check `docker compose --env-file .env.production -f docker-compose.prod.yml ps`, `https://$APP_DOMAIN/`, `/api/health`, `/statistics`, login, resource publish, upload/download, Gitea clone, Showcase/community, and an administrator-only API with both normal and admin users. Confirm external access to the internal service ports fails. Run a backup and restore drill in an isolated environment before accepting production data.

## Backups and recovery

Run `./scripts/backup_all.sh` to create PostgreSQL, MinIO object, and Gitea dump backups under the private backup directory. Restrict directory access and copy backups to encrypted off-host storage; `.env.production` is deliberately excluded and must be backed up separately using your secrets-management process. Keep matching application secrets and deployment configuration with the recovery record.

Restore PostgreSQL with `./scripts/restore_postgres.sh <dump.sql.gz>` and MinIO objects with `./scripts/restore_minio.sh <backup-directory>`. Gitea recovery is intentionally a documented operator procedure and is not automated, because it replaces persistent application data. Perform it only against an isolated recovery copy after taking a snapshot. None of these scripts constitutes a tested isolated restore drill; do not declare recovery readiness until that drill passes.
