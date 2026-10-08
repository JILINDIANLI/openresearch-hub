"""Verify that a published V8 release survives a backend container restart."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def request(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(f"{BASE_URL}{path}", data=body, method=method, headers=headers), timeout=25) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read().decode("utf-8")
        return error.code, json.loads(raw) if raw else {}


def expect(actual: int, expected: int, body: object) -> None:
    assert actual == expected, f"expected {expected}, got {actual}: {body}"


def wait_for_backend() -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            code, health = request("/api/health")
            if code == 200 and health.get("status") == "ok":
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("后端容器重启后未在 45 秒内恢复")


def run() -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"v8persist_{suffix}"
    password = "OpenResearch-V8!"
    token = None
    resource_id = None
    try:
        code, body = request(
            "/api/auth/register",
            method="POST",
            payload={
                "username": username,
                "display_name": "V8 Persistence Check",
                "email": f"{username}@openresearchhub.com",
                "password": password,
                "confirm_password": password,
            },
        )
        expect(code, 201, body)
        code, body = request("/api/auth/login", method="POST", payload={"identifier": username, "password": password})
        expect(code, 200, body)
        token = body["access_token"]
        code, admin_login = request("/api/auth/login", method="POST", payload={"identifier": "kai-shen", "password": "openresearch"})
        expect(code, 200, admin_login)
        admin_token = admin_login["access_token"]

        code, resource = request(
            "/api/resources",
            method="POST",
            token=token,
            payload={
                "title": f"V8 Persistence Resource {suffix}",
                "type": "MODEL",
                "description": "Temporary resource for Docker restart persistence verification.",
            },
        )
        expect(code, 201, resource)
        resource_id = resource["id"]
        code, approved = request(f"/api/admin/resources/{resource_id}/status", method="PATCH", payload={"status": "PUBLISHED"}, token=admin_token)
        expect(code, 200, approved)
        code, version = request(
            f"/api/resources/{resource_id}/versions",
            method="POST",
            token=token,
            payload={"version": "3.2.1", "title": "Persistence Release", "release_notes": "Must remain after restart."},
        )
        expect(code, 201, version)
        code, published = request(f"/api/resources/{resource_id}/versions/3.2.1/publish", method="POST", token=token)
        expect(code, 200, published)
        assert published["is_latest"] and published["status"] == "PUBLISHED"

        subprocess.run(["docker", "compose", "restart", "backend"], cwd=PROJECT_ROOT, check=True, timeout=60)
        wait_for_backend()

        code, saved_version = request(f"/api/resources/{resource_id}/versions/3.2.1")
        expect(code, 200, saved_version)
        assert saved_version["status"] == "PUBLISHED" and saved_version["is_latest"]
        code, latest = request(f"/api/resources/{resource_id}/versions/latest")
        expect(code, 200, latest)
        assert latest["id"] == saved_version["id"] and latest["version"] == "3.2.1"
        print("V8 Docker restart persistence check passed.")
    finally:
        if token and resource_id:
            request(f"/api/resources/{resource_id}", method="DELETE", token=token)


if __name__ == "__main__":
    try:
        run()
    except AssertionError as error:
        print(f"V8 persistence check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
