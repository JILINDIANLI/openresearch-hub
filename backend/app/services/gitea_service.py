from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..core.config import settings


class GiteaError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class GiteaService:
    def __init__(self):
        self.api_url = settings.gitea_api_url
        self.public_url = settings.gitea_url
        self.token = settings.gitea_token

    def _request(self, path: str, method: str = "GET", payload: dict | None = None):
        if not self.token:
            raise GiteaError("Gitea token is not configured", 503)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "Authorization": f"token {self.token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with urlopen(Request(f"{self.api_url}{path}", data=body, method=method, headers=headers), timeout=settings.gitea_timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw).get("message") or json.loads(raw).get("error")
            except json.JSONDecodeError:
                detail = None
            if exc.code == 404:
                raise GiteaError("Gitea repository was not found", 404) from exc
            if exc.code in {401, 403}:
                raise GiteaError("Gitea service token is invalid or lacks permission", 502) from exc
            if exc.code == 409:
                raise GiteaError("A repository with this name already exists", 409) from exc
            raise GiteaError(detail or "Gitea request failed", 502) from exc
        except (URLError, TimeoutError) as exc:
            raise GiteaError("Gitea is unavailable or timed out", 503) from exc

    def _public_url(self, value: str | None) -> str:
        if not value:
            return ""
        value = value.replace("http://gitea:3000", self.public_url).replace("https://gitea:3000", self.public_url)
        public_host = self.public_url.removeprefix("https://").removeprefix("http://")
        value = value.replace("ssh://git@gitea:22", f"ssh://git@{public_host}:{settings.gitea_ssh_port}")
        return value

    @staticmethod
    def _date(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    def _normalize(self, data: dict) -> dict:
        owner = (data.get("owner") or {}).get("login") or settings.gitea_default_owner
        name = data.get("name") or ""
        return {"provider": "GITEA", "owner": owner, "name": name, "full_name": data.get("full_name") or f"{owner}/{name}", "clone_url": self._public_url(data.get("clone_url")), "ssh_url": self._public_url(data.get("ssh_url")), "web_url": self._public_url(data.get("html_url") or data.get("website")), "default_branch": data.get("default_branch") or "main", "description": data.get("description") or "", "language": data.get("language"), "stars_count": int(data.get("stars_count") or 0), "forks_count": int(data.get("forks_count") or 0), "open_issues_count": int(data.get("open_issues_count") or 0), "last_commit_at": self._date(data.get("updated_at")), "visibility": "PRIVATE" if data.get("private") else "PUBLIC"}

    def _latest_commit_at(self, owner: str, name: str):
        data = self._request(f"/repos/{quote(owner)}/{quote(name)}/commits?limit=1")[1]
        if not data:
            return None
        details = data[0].get("commit") or {}
        author = details.get("author") or {}
        committer = details.get("committer") or {}
        return self._date(author.get("date") or committer.get("date"))

    def create(self, payload: dict) -> dict:
        data = self._normalize(self._request("/user/repos", "POST", {"name": payload["name"], "description": payload.get("description", ""), "private": payload.get("private", False), "auto_init": payload.get("initialize_readme", True), "default_branch": "main"})[1])
        try:
            data["last_commit_at"] = self._latest_commit_at(data["owner"], data["name"])
        except GiteaError:
            pass
        return data

    def get(self, owner: str, name: str) -> dict:
        data = self._normalize(self._request(f"/repos/{quote(owner)}/{quote(name)}")[1])
        data["last_commit_at"] = self._latest_commit_at(owner, name)
        return data

    def delete(self, owner: str, name: str) -> None:
        self._request(f"/repos/{quote(owner)}/{quote(name)}", "DELETE")

    def commits(self, owner: str, name: str) -> list[dict]:
        data = self._request(f"/repos/{quote(owner)}/{quote(name)}/commits?limit=20")[1]
        return [{"sha": item.get("sha", ""), "message": ((item.get("commit") or {}).get("message") or "").splitlines()[0], "author": ((item.get("commit") or {}).get("author") or {}).get("name") or ((item.get("author") or {}).get("login")), "created_at": self._date(((item.get("commit") or {}).get("author") or {}).get("date")), "url": self._public_url(item.get("html_url"))} for item in data]

    def commit(self, owner: str, name: str, sha: str) -> dict:
        """Verify that a commit exists in the linked Gitea repository."""
        value = self._request(f"/repos/{quote(owner)}/{quote(name)}/git/commits/{quote(sha)}")[1]
        return {"sha": value.get("sha", sha), "message": value.get("message", "")}

    def branches(self, owner: str, name: str) -> list[dict]:
        data = self._request(f"/repos/{quote(owner)}/{quote(name)}/branches")[1]
        return [{"name": item.get("name", ""), "protected": bool(item.get("protected", False)), "commit_sha": ((item.get("commit") or {}).get("id"))} for item in data]

    def contents(self, owner: str, name: str, path: str = "", ref: str | None = None) -> list[dict]:
        suffix = f"?ref={quote(ref)}" if ref else ""
        value = self._request(f"/repos/{quote(owner)}/{quote(name)}/contents/{quote(path, safe='/')}{suffix}")[1]
        values = value if isinstance(value, list) else [value]
        return [{"path": item.get("path", ""), "name": item.get("name", ""), "type": item.get("type", "file"), "size": item.get("size"), "sha": item.get("sha"), "url": self._public_url(item.get("url")), "html_url": self._public_url(item.get("html_url"))} for item in values]

    def file(self, owner: str, name: str, path: str, ref: str | None = None) -> dict:
        suffix = f"?ref={quote(ref)}" if ref else ""
        item = self._request(f"/repos/{quote(owner)}/{quote(name)}/contents/{quote(path, safe='/')}{suffix}")[1]
        encoded = (item.get("content") or "").replace("\n", "")
        try:
            content = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (ValueError, binascii.Error):
            content = ""
        raw_url = self._public_url(item.get("download_url"))
        return {"path": item.get("path", path), "name": item.get("name", path.rsplit("/", 1)[-1]), "size": int(item.get("size") or len(content.encode("utf-8"))), "language": item.get("type"), "content": content, "raw_url": raw_url, "download_url": raw_url}


gitea_service = GiteaService()
