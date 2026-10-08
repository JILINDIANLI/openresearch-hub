"""Verify that a V10 Showcase survives a Docker backend restart.

Run this script on the Windows host from the atlas-platform project root.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def api(path: str, method: str = "GET", payload=None, token: str | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request(BASE + path, data=body, headers=headers, method=method), timeout=30) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw) if raw else {}
    except (URLError, OSError) as exc:
        return 0, {"detail": str(exc)}


def expect(actual: int, expected: int, body) -> None:
    assert actual == expected, (actual, expected, body)


def run() -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"v10persist_{suffix}"
    password = "OpenResearch-V10!"
    resource_id = None
    token = None
    try:
        status, body = api("/api/auth/register", "POST", {"username": username, "display_name": username, "email": username + "@openresearchhub.com", "password": password, "confirm_password": password})
        expect(status, 201, body)
        status, body = api("/api/auth/login", "POST", {"identifier": username, "password": password})
        expect(status, 200, body)
        token = body["access_token"]
        status, admin_login = api("/api/auth/login", "POST", {"identifier": "kai-shen", "password": "openresearch"})
        expect(status, 200, admin_login)
        admin_token = admin_login["access_token"]
        status, resource = api("/api/resources", "POST", {"title": "V10 Persistence " + suffix, "type": "PROJECT", "description": "Temporary resource used to verify Showcase persistence."}, token)
        expect(status, 201, resource)
        resource_id = resource["id"]
        status, approved = api(f"/api/admin/resources/{resource_id}/status", "PATCH", {"status": "PUBLISHED"}, admin_token)
        expect(status, 200, approved)
        status, showcase = api(f"/api/resources/{resource_id}/showcase", "POST", {"title": "Persistence Showcase", "short_description": "Stored in PostgreSQL", "abstract": "This Showcase must survive a backend restart."}, token)
        expect(status, 201, showcase)
        showcase_id = showcase["id"]
        subprocess.run(["docker", "compose", "restart", "backend"], cwd=PROJECT_ROOT, check=True, timeout=90)
        status, restored = 0, {}
        for _ in range(30):
            status, restored = api(f"/api/resources/{resource_id}/showcase")
            if status == 200:
                break
            time.sleep(1)
        expect(status, 200, restored)
        assert restored["id"] == showcase_id and restored["title"] == "Persistence Showcase"
        print("V10 Showcase persistence check passed.")
    finally:
        if resource_id and token:
            for _ in range(30):
                status, _ = api(f"/api/resources/{resource_id}", "DELETE", token=token)
                if status in {204, 404}:
                    break
                time.sleep(1)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("V10 persistence check failed:", exc, file=sys.stderr)
        raise
