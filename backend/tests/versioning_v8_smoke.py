"""Live acceptance checks for OpenResearch Hub V8 Resource Versioning."""

from __future__ import annotations

import json
import os
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


BASE_URL = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def request(path: str, *, method: str = "GET", payload: dict | bytes | None = None, headers: dict | None = None, token: str | None = None, redirects: bool = True):
    body = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
    request_headers = dict(headers or {})
    if isinstance(payload, dict):
        request_headers.setdefault("Content-Type", "application/json")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    opener = urlopen if redirects else build_opener(NoRedirect()).open
    try:
        with opener(Request(f"{BASE_URL}{path}", data=body, method=method, headers=request_headers), timeout=25) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}, dict(response.headers)
    except HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return error.code, parsed, dict(error.headers)


def expect(actual: int, expected: int, body) -> None:
    assert actual == expected, f"expected {expected}, got {actual}: {body}"


def multipart(name: str, content: bytes, kind: str) -> tuple[bytes, str]:
    boundary = f"----OpenResearchV8{uuid.uuid4().hex}"
    fields = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_kind\"\r\n\r\n{kind}\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"description\"\r\n\r\nV8 smoke artifact\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: {'application/pdf' if name.endswith('.pdf') else 'application/octet-stream'}\r\n\r\n",
    ]
    return "".join(fields).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8"), boundary


def login(identifier: str, password: str) -> str:
    code, body, _ = request("/api/auth/login", method="POST", payload={"identifier": identifier, "password": password})
    expect(code, 200, body)
    return body["access_token"]


def run() -> None:
    suffix = uuid.uuid4().hex[:8]
    password = "OpenResearch-V8!"
    username_a, username_b = f"v8a_{suffix}", f"v8b_{suffix}"
    token_a = token_b = None
    resource_id = None
    repo_created = False
    try:
        for username, label in ((username_a, "V8 User A"), (username_b, "V8 User B")):
            code, body, _ = request("/api/auth/register", method="POST", payload={"username": username, "display_name": label, "email": f"{username}@openresearchhub.com", "password": password, "confirm_password": password})
            expect(code, 201, body)
        token_a, token_b = login(username_a, password), login(username_b, password)
        admin_token = login("kai-shen", "openresearch")
        code, resource, _ = request("/api/resources", method="POST", token=token_a, payload={"title": f"V8 Versioning Resource {suffix}", "type": "MODEL", "description": "Temporary resource used for V8 version release acceptance tests.", "model": {"framework": "PyTorch", "task": "Object Detection"}})
        expect(code, 201, resource)
        resource_id = resource["id"]

        code, repository, _ = request(f"/api/resources/{resource_id}/repository", method="POST", token=token_a, payload={"name": f"v8-release-{suffix}", "description": "V8 acceptance repository", "private": False, "initialize_readme": True})
        expect(code, 201, repository)
        repo_created = True
        code, commits, _ = request(f"/api/resources/{resource_id}/repository/commits", token=token_a)
        expect(code, 200, commits)
        commit = commits[0]["sha"]

        version_payload = {"version": "v1.0.0", "title": "Initial Release", "release_notes": "First stable release.", "git_branch": "main", "git_commit_sha": commit}
        code, v1, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload=version_payload, token=token_a)
        expect(code, 201, v1)
        assert v1["version"] == "1.0.0" and v1["status"] == "DRAFT"
        code, body, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload=version_payload, token=token_a)
        expect(code, 409, body)
        code, body, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload={**version_payload, "version": "1.0.1"}, token=token_b)
        expect(code, 403, body)
        code, body, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload={**version_payload, "version": "1.0.1"})
        expect(code, 401, body)
        code, body, _ = request(f"/api/resources/{resource_id}/versions/1.0.0", token=token_b)
        expect(code, 404, body)

        code, _private_resource, _ = request(
            f"/api/resources/{resource_id}",
            method="PUT",
            token=token_a,
            payload={"visibility": "private"},
        )
        expect(code, 200, _private_resource)
        code, body, _ = request(f"/api/resources/{resource_id}", token=token_b)
        expect(code, 404, body)
        code, body, _ = request(f"/api/resources/{resource_id}/activity", token=token_b)
        expect(code, 404, body)
        code, _public_resource, _ = request(
            f"/api/resources/{resource_id}",
            method="PUT",
            token=token_a,
            payload={"visibility": "public"},
        )
        expect(code, 200, _public_resource)
        code, approved_resource, _ = request(
            f"/api/admin/resources/{resource_id}/status",
            method="PATCH",
            payload={"status": "PUBLISHED"},
            token=admin_token,
        )
        expect(code, 200, approved_resource)
        assert approved_resource["review_status"] == "PUBLISHED"

        for filename, data, kind in (("model-v1.pt", b"v8-model-weight", "MODEL_WEIGHT"), ("release-v1.pdf", b"%PDF-1.4\nV8 release", "PAPER")):
            body, boundary = multipart(filename, data, kind)
            code, uploaded, _ = request(f"/api/resources/{resource_id}/versions/1.0.0/files", method="POST", payload=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, token=token_a)
            expect(code, 201, uploaded)
            assert uploaded["version_id"] == v1["id"]
        code, files, _ = request(f"/api/resources/{resource_id}/versions/1.0.0/files", token=token_a)
        expect(code, 200, files)
        assert len(files) == 2

        code, published_v1, _ = request(f"/api/resources/{resource_id}/versions/1.0.0/publish", method="POST", token=token_a)
        expect(code, 200, published_v1)
        assert published_v1["status"] == "PUBLISHED" and published_v1["is_latest"]
        code, visible_v1, _ = request(f"/api/resources/{resource_id}/versions/1.0.0", token=token_b)
        expect(code, 200, visible_v1)
        code, _, _ = request(f"/api/resources/{resource_id}/versions/1.0.0", method="DELETE", token=token_a)
        expect(code, 409, _)

        code, v11, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload={"version": "1.1.0", "title": "Second Release", "release_notes": "Improved model package.", "git_branch": "main", "git_commit_sha": commit}, token=token_a)
        expect(code, 201, v11)
        body, boundary = multipart("config-v11.yaml", b"epochs: 10\n", "CONFIG")
        code, uploaded_v11, _ = request(f"/api/resources/{resource_id}/versions/1.1.0/files", method="POST", payload=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, token=token_a)
        expect(code, 201, uploaded_v11)
        code, published_v11, _ = request(f"/api/resources/{resource_id}/versions/1.1.0/publish", method="POST", token=token_a)
        expect(code, 200, published_v11)
        assert published_v11["is_latest"]
        code, old_v1, _ = request(f"/api/resources/{resource_id}/versions/1.0.0", token=token_a)
        expect(code, 200, old_v1)
        assert not old_v1["is_latest"]
        code, latest, _ = request(f"/api/resources/{resource_id}/versions/latest")
        expect(code, 200, latest)
        assert latest["version"] == "1.1.0"

        for value in ("1.2.0", "1.10.0", "2.0.0", "10.0.0"):
            code, created, _ = request(f"/api/resources/{resource_id}/versions", method="POST", payload={"version": value, "title": f"Draft {value}"}, token=token_a)
            expect(code, 201, created)
        code, all_versions, _ = request(f"/api/resources/{resource_id}/versions", token=token_a)
        expect(code, 200, all_versions)
        assert [item["version"] for item in all_versions][:4] == ["10.0.0", "2.0.0", "1.10.0", "1.2.0"]
        code, public_versions, _ = request(f"/api/resources/{resource_id}/versions", token=token_b)
        expect(code, 200, public_versions)
        assert all(item["status"] != "DRAFT" for item in public_versions)

        code, comparison, _ = request(f"/api/resources/{resource_id}/versions/compare?from=1.0.0&to=1.1.0", token=token_b)
        expect(code, 200, comparison)
        assert comparison["version_changed"] and "config-v11.yaml" in comparison["files_added"]
        code, _, _ = request(uploaded_v11["download_url"], token=token_b, redirects=False)
        expect(code, 307, _)
        code, v11_after_download, _ = request(f"/api/resources/{resource_id}/versions/1.1.0", token=token_a)
        expect(code, 200, v11_after_download)
        assert v11_after_download["downloads_count"] >= 1
        code, resource_after_download, _ = request(f"/api/resources/{resource_id}", token=token_a)
        expect(code, 200, resource_after_download)
        assert resource_after_download["downloads_count"] >= 1 and resource_after_download["latest_version"] == "1.1.0"

        code, archived, _ = request(f"/api/resources/{resource_id}/versions/1.1.0/archive", method="POST", token=token_a)
        expect(code, 200, archived)
        assert archived["status"] == "ARCHIVED" and not archived["is_latest"]
        code, restored_latest, _ = request(f"/api/resources/{resource_id}/versions/latest")
        expect(code, 200, restored_latest)
        assert restored_latest["version"] == "1.0.0"
        code, _, _ = request(f"/api/resources/{resource_id}/versions/10.0.0", method="DELETE", token=token_a)
        expect(code, 204, _)
        print("V8 Resource Versioning smoke checks passed.")
    finally:
        if resource_id and token_a:
            if repo_created:
                request(f"/api/resources/{resource_id}/repository", method="DELETE", token=token_a)
            request(f"/api/resources/{resource_id}", method="DELETE", token=token_a)


if __name__ == "__main__":
    try:
        run()
    except AssertionError as error:
        print(f"V8 smoke check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
