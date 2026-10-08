# Operations

## Status and logs

From the repository directory, check services with `docker compose --env-file .env.production -f docker-compose.prod.yml ps`. Inspect logs with the matching service name:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 backend
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 nginx
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 postgres
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 redis
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 minio
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 gitea
```

Docker JSON logs rotate at 10 MB, five files. Never paste credentials, authorization headers, or environment dumps into tickets.

## Restart and health

Restart a single service with `docker compose --env-file .env.production -f docker-compose.prod.yml restart backend`. Check `https://research.example.com/api/health` and the Admin system page. A service restart does not remove persistent data. Check Nginx syntax with `docker compose ... exec nginx nginx -t` before reload.

## Backup and recovery

Run `./scripts/backup_all.sh`; verify files exist and copy encrypted backups off-host. Use `scripts/restore_postgres.sh` only after a separate current backup and a maintenance window. Restore MinIO from a dated mirror using `scripts/restore_minio.sh`. Gitea restoration is a maintenance procedure: stop Gitea, snapshot its volume, restore its native dump into a disposable environment first, then execute an approved recovery. Do not test restores against live volumes.

## Disk and storage

Check host capacity with `df -h` and Docker usage with `docker system df`. Do not prune volumes. MinIO growth is the sum of uploaded objects and versions; alert before the data filesystem reaches 80%, expand storage or apply an approved retention policy, then verify backups. The current admin UI does not yet provide disk-capacity alerts or top-file reporting.

## Service incidents

PostgreSQL: inspect health and logs, disk capacity, and recent migrations; take a snapshot before repairs. Redis: cache loss is recoverable, but verify connectivity/password configuration. MinIO: check volume and health; do not recreate its volume. Gitea: verify its persistent volume and advertised hostname; repositories/config/database are in its native dump. Nginx: verify certificate expiry and `nginx -t`; renew with Certbot and reload after renewal.
