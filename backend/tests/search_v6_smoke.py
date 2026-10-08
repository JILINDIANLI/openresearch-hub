"""Live API smoke checks for OpenResearch Hub V6.

Run after Docker is started: ``python backend/tests/search_v6_smoke.py``.
The checks use only public API routes plus the seeded Kai Shen account.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("OPENRESEARCH_URL", "http://127.0.0.1:8000").rstrip("/")


def request(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None) -> tuple[int, dict | list]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(f"{BASE_URL}{path}", data=body, method=method, headers=headers), timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def search(**query) -> dict:
    encoded = urlencode(query, doseq=True)
    status, payload = request(f"/api/search?{encoded}")
    assert status == 200, payload
    assert isinstance(payload, dict)
    return payload


def descending(values: list[int]) -> bool:
    return all(left >= right for left, right in zip(values, values[1:]))


def run() -> None:
    health_status, health = request("/api/health")
    assert health_status == 200 and health["status"] == "ok", health

    transformer = search(q="transformer")
    titles = {item["title"] for item in transformer["items"]}
    assert {"Transformer Forecasting", "Vision Transformer", "Transformer Paper"}.issubset(titles), titles
    assert search(q="TRANSFORMER")["total"] == transformer["total"]
    assert search(q="transf")["total"] >= 3

    model_only = search(q="transformer", type="MODEL")
    assert model_only["items"] and all(item["resource_type"] == "model" for item in model_only["items"])
    tag_filtered = search(tag="Reinforcement Learning")
    assert tag_filtered["items"] and all("Reinforcement Learning" in {tag["name"] for tag in item["tags"]} for item in tag_filtered["items"])
    framework_filtered = search(type="model", framework="PyTorch")
    assert framework_filtered["items"] and all(item["details"].get("model", {}).get("framework") == "PyTorch" for item in framework_filtered["items"])
    year_filtered = search(year=2025)
    assert year_filtered["items"] and all(item["details"].get("paper", {}).get("year") == 2025 for item in year_filtered["items"])

    stars = search(sort="stars")
    assert descending([item["stars_count"] for item in stars["items"]])
    downloads = search(sort="downloads")
    assert descending([item["downloads_count"] for item in downloads["items"]])
    paged = search(page=2, page_size=2)
    assert paged["page"] == 2 and paged["page_size"] == 2 and paged["total"] >= 3
    capped = search(page_size=999)
    assert capped["page_size"] == 100

    suggestion_status, suggestions = request("/api/search/suggestions?q=trans")
    assert suggestion_status == 200 and any(item["kind"] == "resource" for item in suggestions), suggestions
    empty = search(q="this-resource-does-not-exist-zzzz")
    assert empty["items"] == [] and empty["total"] == 0
    safe = search(q="%' OR 1=1 --")
    assert isinstance(safe["items"], list)

    login_status, login = request("/api/auth/login", method="POST", payload={"identifier": "kai-shen", "password": "openresearch"})
    assert login_status == 200 and login.get("access_token"), login
    authenticated_status, authenticated = request("/api/search?q=transformer", token=login["access_token"])
    assert authenticated_status == 200 and authenticated["total"] == transformer["total"]
    print("V6 Search & Discovery smoke checks passed (15 assertion groups).")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as error:
        print(f"V6 smoke check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
