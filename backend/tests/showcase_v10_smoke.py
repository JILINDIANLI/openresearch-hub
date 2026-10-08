"""Live acceptance checks for V10 Research Showcase."""
from __future__ import annotations

import json
import os
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")


def api(path: str, method: str = "GET", payload=None, token: str | None = None, body: bytes | None = None, content_type: str | None = None):
    if body is None and payload is not None:
        body = json.dumps(payload).encode()
        content_type = "application/json"
    headers = {"Content-Type": content_type} if content_type else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request(BASE + path, data=body, headers=headers, method=method), timeout=30) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        return exc.code, data


def check(actual, expected, body):
    assert actual == expected, (actual, expected, body)


def register(username: str, password: str) -> str:
    status, data = api("/api/auth/register", "POST", {"username": username, "display_name": username, "email": username + "@openresearchhub.com", "password": password, "confirm_password": password})
    check(status, 201, data)
    status, data = api("/api/auth/login", "POST", {"identifier": username, "password": password})
    check(status, 200, data)
    return data["access_token"]


def multipart(fields: dict[str, str], filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "----OpenResearchV10" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode() + content + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def run() -> None:
    suffix = uuid.uuid4().hex[:8]
    password = "OpenResearch-V10!"
    user_a = f"v10a_{suffix}"
    user_b = f"v10b_{suffix}"
    token_a = register(user_a, password)
    token_b = register(user_b, password)
    status, admin_login = api("/api/auth/login", "POST", {"identifier": "kai-shen", "password": "openresearch"})
    check(status, 200, admin_login)
    admin_token = admin_login["access_token"]
    resource_id = None
    try:
        status, resource = api("/api/resources", "POST", {"title": "V10 Showcase Test " + suffix, "type": "PROJECT", "description": "A test resource for the V10 research showcase."}, token_a)
        check(status, 201, resource)
        resource_id = resource["id"]

        payload = {
            "title": "V10 Research Story",
            "short_description": "A complete research showcase.",
            "abstract": "## Abstract\nA safe Markdown abstract. <script>window.alert('xss')</script>",
            "research_background": "The research background.",
            "methodology": "```python\nprint('safe')\n```",
            "contributions": "- Contribution one\n- Contribution two",
            "experiments": "CEC2020 and a reproducible setup.",
            "results_summary": "The new method is faster.",
            "citation_text": "Author et al. (2026). V10 Showcase.",
            "bibtex": "@article{v10, title={V10 Showcase}}",
        }
        status, showcase = api(f"/api/resources/{resource_id}/showcase", "POST", payload, token_a)
        check(status, 201, showcase)
        showcase_id = showcase["id"]
        assert showcase["resource_id"] == resource_id
        assert "<script>" in showcase["abstract"]

        status, resource_detail = api(f"/api/resources/{resource_id}", token=token_a)
        check(status, 200, resource_detail)
        assert resource_detail["has_showcase"] is True
        status, hidden_search = api(f"/api/search?q={suffix}")
        check(status, 200, hidden_search)
        assert all(item["id"] != resource_id for item in hidden_search["items"])
        status, hidden_showcase = api(f"/api/resources/{resource_id}/showcase")
        check(status, 404, hidden_showcase)

        status, approved_resource = api(
            f"/api/admin/resources/{resource_id}/status",
            "PATCH",
            {"status": "PUBLISHED"},
            admin_token,
        )
        check(status, 200, approved_resource)
        assert approved_resource["review_status"] == "PUBLISHED"
        status, search = api(f"/api/search?q={suffix}")
        check(status, 200, search)
        assert any(item["id"] == resource_id and item["has_showcase"] for item in search["items"])

        status, public = api(f"/api/resources/{resource_id}/showcase")
        check(status, 200, public)
        assert public["bibtex"] == payload["bibtex"]

        status, _ = api(f"/api/resources/{resource_id}/showcase", "PATCH", {"title": "Should fail"}, token_b)
        check(status, 403, _)

        status, result = api(f"/api/showcases/{showcase_id}/results", "POST", {"title": "Comparison", "description": "Metrics", "table_data": [{"algorithm": "EBKA", "cost": 100}]}, token_a)
        check(status, 201, result)
        result_id = result["id"]
        status, results = api(f"/api/showcases/{showcase_id}/results")
        check(status, 200, results)
        assert results[0]["id"] == result_id

        body, content_type = multipart({"title": "Architecture", "description": "An architecture figure.", "order_index": "0"}, "architecture.png", b"\x89PNG\r\n\x1a\n", "image/png")
        status, media = api(f"/api/showcases/{showcase_id}/media", "POST", token=token_a, body=body, content_type=content_type)
        check(status, 201, media)
        assert media["media_type"] == "IMAGE"
        status, media_list = api(f"/api/showcases/{showcase_id}/media")
        check(status, 200, media_list)
        assert media_list[0]["id"] == media["id"]

        status, _ = api(f"/api/showcases/media/{media['id']}", "DELETE", token=token_b)
        check(status, 403, _)
        status, _ = api(f"/api/showcases/media/{media['id']}", "DELETE", token=token_a)
        check(status, 204, _)
        status, _ = api(f"/api/showcase/results/{result_id}", "DELETE", token=token_a)
        check(status, 204, _)
        status, _ = api(f"/api/resources/{resource_id}/showcase", "DELETE", token=token_a)
        check(status, 204, _)
        status, _ = api(f"/api/resources/{resource_id}")
        check(status, 200, _)
        print("V10 Research Showcase smoke checks passed.")
    finally:
        if resource_id:
            api(f"/api/resources/{resource_id}", "DELETE", token=token_a)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("V10 smoke failed:", exc, file=sys.stderr)
        raise
