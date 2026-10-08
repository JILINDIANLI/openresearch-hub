"""Inspect MinIO objects against resource-file records.

Run from the backend container. It is dry-run by default; use
``--delete-orphans`` only after reviewing the output and a backup.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from backend.app.database.database import SessionLocal
from backend.app.database.models import ResourceFile
from backend.app.services.storage_service import storage_service
from backend.app.storage.minio_client import get_minio_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile OpenResearch MinIO resource objects")
    parser.add_argument("--delete-orphans", action="store_true", help="Delete MinIO objects not referenced by the database")
    args = parser.parse_args()

    with SessionLocal() as db:
        referenced = {key for key in db.scalars(select(ResourceFile.object_key).where(ResourceFile.object_key.is_not(None))).all() if key}

    client = get_minio_client()
    objects = {item.object_name for item in client.list_objects(storage_service.bucket, prefix="resources/", recursive=True)}
    orphaned = sorted(objects - referenced)
    missing = sorted(referenced - objects)

    print(f"Referenced database objects: {len(referenced)}")
    print(f"Stored MinIO objects: {len(objects)}")
    print(f"Unreferenced MinIO objects: {len(orphaned)}")
    print(f"Database records with missing objects: {len(missing)}")
    for key in orphaned:
        print(f"ORPHAN {key}")
    for key in missing:
        print(f"MISSING {key}")

    if args.delete_orphans:
        for key in orphaned:
            client.remove_object(storage_service.bucket, key)
        print(f"Deleted {len(orphaned)} unreferenced object(s).")
    elif orphaned:
        print("Dry run only. Re-run with --delete-orphans after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
