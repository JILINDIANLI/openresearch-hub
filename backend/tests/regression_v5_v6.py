"""Non-persistent regression check for V5 and V6 running against Docker.

It creates one temporary resource, exercises engagement and MinIO file routes,
then removes that resource in ``finally`` so no test resource remains.
"""

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
    data = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
    request_headers = dict(headers or {})
    if isinstance(payload, dict):
        request_headers.setdefault("Content-Type", "application/json")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    opener = urlopen if redirects else build_opener(NoRedirect()).open
    def decode(body: str):
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body
    try:
        with opener(Request(f"{BASE_URL}{path}", data=data, method=method, headers=request_headers), timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, decode(body), dict(response.headers)
    except HTTPError as error:
        body = error.read().decode("utf-8")
        return error.code, decode(body), dict(error.headers)


def multipart_pdf() -> tuple[bytes, str]:
    boundary = f"----OpenResearch{uuid.uuid4().hex}"
    fields = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_kind\"\r\n\r\nPAPER\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"description\"\r\n\r\nTemporary regression file\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"v6-regression.pdf\"\r\nContent-Type: application/pdf\r\n\r\n",
    ]
    return "".join(fields).encode("utf-8") + b"%PDF-1.4\n% OpenResearch regression\n" + f"\r\n--{boundary}--\r\n".encode("utf-8"), boundary


def expect(status: int, actual: int, body) -> None:
    assert actual == status, f"expected {status}, got {actual}: {body}"


def run() -> None:
    for path in ("/", "/docs", "/publish", "/users/kai-shen", "/resources/4"):
        status, _, _ = request(path)
        expect(200, status, path)
    status, health, _ = request("/api/health")
    expect(200, status, health)
    assert health["status"] == "ok"
    for path in ("/api/resources", "/api/resources/4", "/api/resources/4/stars", "/api/trending", "/api/resources/popular?type=model&sort=stars", "/api/users/kai-shen", "/api/users/kai-shen/resources", "/api/tags"):
        status, _, body_headers = request(path)
        expect(200, status, body_headers)

    status, login, _ = request("/api/auth/login", method="POST", payload={"identifier": "kai-shen", "password": "openresearch"})
    expect(200, status, login)
    token = login["access_token"]
    status, me, _ = request("/api/auth/me", token=token)
    expect(200, status, me)
    assert me["username"] == "kai-shen"
    for path in ("/api/me/stars", "/api/me/favorites"):
        status, body, _ = request(path, token=token)
        expect(200, status, body)

    resource_id = None
    try:
        title = f"V6 Regression Resource {uuid.uuid4().hex[:10]}"
        create_payload = {
            "title": title,
            "type": "PAPER",
            "description": "Temporary resource used only for an automated regression check.",
            "license": "MIT",
            "research_field": "AI & Deep Learning",
            "tags": ["Deep Learning"],
            "paper": {"authors": ["Kai Shen"], "year": 2026, "journal": "OpenResearch QA"},
        }
        status, created, _ = request("/api/resources", method="POST", payload=create_payload, token=token)
        expect(201, status, created)
        resource_id = created["id"]

        for path, method in ((f"/api/resources/{resource_id}/star", "POST"), (f"/api/resources/{resource_id}/favorite", "POST")):
            status, body, _ = request(path, method=method, token=token)
            expect(200, status, body)
        status, detail, _ = request(f"/api/resources/{resource_id}", token=token)
        expect(200, status, detail)
        assert detail["is_starred"] and detail["is_favorited"] and detail["views_count"] >= 1

        payload, boundary = multipart_pdf()
        status, uploaded, _ = request(f"/api/resources/{resource_id}/files", method="POST", payload=payload, token=token, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        expect(201, status, uploaded)
        file_id = uploaded["id"]
        status, files, _ = request(f"/api/resources/{resource_id}/files", token=token)
        expect(200, status, files)
        assert any(item["id"] == file_id for item in files)
        status, _, preview_headers = request(f"/api/files/{file_id}/preview", token=token, redirects=False)
        expect(307, status, preview_headers)
        assert "location" in {key.lower() for key in preview_headers}
        status, _, download_headers = request(f"/api/files/{file_id}/download", token=token, redirects=False)
        expect(307, status, download_headers)
        status, _, _ = request(f"/api/resources/{resource_id}/files/{file_id}", method="DELETE", token=token)
        expect(204, status, {})

        for path, method in ((f"/api/resources/{resource_id}/star", "DELETE"), (f"/api/resources/{resource_id}/favorite", "DELETE")):
            status, body, _ = request(path, method=method, token=token)
            expect(200, status, body)
        status, activity, _ = request(f"/api/resources/{resource_id}/activity", token=token)
        expect(200, status, activity)
        assert {"RESOURCE_CREATED", "FILE_UPLOADED", "FILE_DELETED", "STARRED"}.issubset({row["activity_type"] for row in activity})
    finally:
        if resource_id:
            status, body, _ = request(f"/api/resources/{resource_id}", method="DELETE", token=token)
            expect(204, status, body)
    print("V5 regression and V6 integration checks passed; temporary test resource removed.")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as error:
        print(f"Regression check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
