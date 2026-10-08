"""Live V7 acceptance checks for the Gitea repository integration.

Run after ``docker compose up -d --build``. The script creates temporary users,
a resource, and a Gitea repository, exercises the public/private and ownership
rules, then removes the temporary records and repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")


def clone_url_for_environment(repository: dict) -> str:
    """Use the service hostname only when this smoke test runs inside Docker."""
    internal_base = os.getenv("GITEA_SMOKE_CLONE_BASE", "").rstrip("/")
    if internal_base:
        return f"{internal_base}/{repository['full_name']}.git"
    return repository["clone_url"]


def request(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(f"{BASE_URL}{path}", data=body, method=method, headers=headers), timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = raw
        return error.code, body


def expect(actual: int, expected: int, body) -> None:
    assert actual == expected, f"expected {expected}, got {actual}: {body}"


def login(identifier: str, password: str) -> str:
    status, body = request("/api/auth/login", method="POST", payload={"identifier": identifier, "password": password})
    expect(status, 200, body)
    return body["access_token"]


def run() -> None:
    suffix = uuid.uuid4().hex[:8]
    username_a = f"v7a_{suffix}"
    username_b = f"v7b_{suffix}"
    password = "OpenResearch-V7!"
    resource_id = None
    repo_name = f"v7-smoke-{suffix}"
    token_a = token_b = None
    try:
        for username, label in ((username_a, "User A"), (username_b, "User B")):
            status, body = request("/api/auth/register", method="POST", payload={"username": username, "display_name": label, "email": f"{username}@openresearchhub.com", "password": password, "confirm_password": password, "organization": "V7 smoke"})
            expect(status, 201, body)
        token_a, token_b = login(username_a, password), login(username_b, password)
        admin_token = login("kai-shen", "openresearch")

        status, body = request("/api/resources", method="POST", token=token_a, payload={"title": f"V7 Repository Smoke {suffix}", "type": "PROJECT", "description": "Temporary resource for V7 repository integration acceptance tests.", "project": {"members": [username_a]}})
        expect(status, 201, body)
        resource_id = body["id"]

        status, body = request(f"/api/resources/{resource_id}/repository", method="POST", token=token_b, payload={"name": repo_name, "description": "V7 smoke repository", "private": False, "initialize_readme": True})
        expect(status, 403, body)
        status, body = request(f"/api/resources/{resource_id}/repository", method="POST", payload={"name": repo_name})
        expect(status, 401, body)

        status, repository = request(f"/api/resources/{resource_id}/repository", method="POST", token=token_a, payload={"name": repo_name, "description": "V7 smoke repository", "private": False, "initialize_readme": True})
        expect(status, 201, repository)
        assert repository["provider"] == "GITEA" and repository["full_name"].endswith(repo_name)
        with tempfile.TemporaryDirectory(prefix="openresearch-v7-clone-") as clone_dir:
            subprocess.run(["git", "clone", clone_url_for_environment(repository), clone_dir], check=True, capture_output=True, text=True, timeout=30)
            assert Path(clone_dir, "README.md").exists()

        for path in ("", "/commits", "/branches", "/tree", "/file?path=README.md"):
            status, body = request(f"/api/resources/{resource_id}/repository{path}", token=token_a)
            expect(status, 200, body)
        status, readme = request(f"/api/resources/{resource_id}/repository/file?path=README.md", token=token_a)
        expect(status, 200, readme)
        assert "content" in readme and readme["path"] == "README.md"

        status, pending_repository = request(f"/api/resources/{resource_id}/repository")
        expect(status, 404, pending_repository)
        status, approved_resource = request(
            f"/api/admin/resources/{resource_id}/status",
            method="PATCH",
            token=admin_token,
            payload={"status": "PUBLISHED"},
        )
        expect(status, 200, approved_resource)
        assert approved_resource["review_status"] == "PUBLISHED"
        status, public_repository = request(f"/api/resources/{resource_id}/repository")
        expect(status, 200, public_repository)
        status, _ = request(f"/api/resources/{resource_id}/repository/sync", method="POST", token=token_a)
        expect(status, 200, _)
        status, _ = request(f"/api/resources/{resource_id}/repository", method="DELETE", token=token_b)
        expect(status, 403, _)

        status, _ = request(f"/api/resources/{resource_id}/repository", method="DELETE", token=token_a)
        expect(status, 204, _)
        private_name = f"v7-private-{suffix}"
        status, private_repository = request(f"/api/resources/{resource_id}/repository", method="POST", token=token_a, payload={"name": private_name, "description": "V7 private smoke repository", "private": True, "initialize_readme": True})
        expect(status, 201, private_repository)
        status, _ = request(f"/api/resources/{resource_id}/repository", token=token_b)
        expect(status, 404, _)
        status, _ = request(f"/api/resources/{resource_id}/repository", token=token_a)
        expect(status, 200, _)
        print("V7 Gitea repository smoke checks passed.")
    finally:
        if resource_id and token_a:
            request(f"/api/resources/{resource_id}/repository", method="DELETE", token=token_a)
            request(f"/api/resources/{resource_id}", method="DELETE", token=token_a)


if __name__ == "__main__":
    try:
        run()
    except AssertionError as error:
        print(f"V7 smoke check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
