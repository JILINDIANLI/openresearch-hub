from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
DB_PATH = DATA_DIR / "atlas.db"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Atlas Project Hub API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                category TEXT NOT NULL,
                owner TEXT NOT NULL,
                code_url TEXT,
                video_url TEXT,
                code_file TEXT,
                video_file TEXT,
                is_public INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        migrations = {
            "description": "TEXT NOT NULL DEFAULT ''",
            "tags": "TEXT NOT NULL DEFAULT ''",
            "version": "TEXT NOT NULL DEFAULT 'v1.0'",
            "status": "TEXT NOT NULL DEFAULT 'draft'",
        }
        for name, definition in migrations.items():
            if name not in existing_columns:
                connection.execute(f"ALTER TABLE projects ADD COLUMN {name} {definition}")
        connection.execute("UPDATE projects SET status = 'published' WHERE is_public = 1 AND status = 'draft'")
        if connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            samples = [
                ("demo-drone", "园区无人机智能巡检", "面向园区设施巡检的自主飞行、缺陷识别与报告生成方案。", "robotics", "周思远", "https://github.com/", "https://www.youtube.com/"),
                ("demo-vision", "工业视觉缺陷检测平台", "将多模型检测能力封装为可配置的产线质检服务，缩短上线周期。", "ai", "陈卓", "https://github.com/", "https://www.youtube.com/"),
                ("demo-delivery", "客户交付项目看板", "从启动到验收统一追踪里程碑、风险与关键交付物。", "delivery", "孟然", "https://github.com/", "https://www.youtube.com/"),
            ]
            for project_id, title, summary, category, owner, code_url, video_url in samples:
                now = datetime.now(timezone.utc).isoformat()
                connection.execute("INSERT INTO projects (id,title,summary,category,owner,code_url,video_url,is_public,status,version,tags,created_at,updated_at) VALUES (?,?,?,?,?,?,?,1,'published','v1.0','示例项目',?,?)", (project_id, title, summary, category, owner, code_url, video_url, now, now))


def row_to_project(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["is_public"] = bool(item["is_public"])
    return item


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(
        ROOT / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "atlas-project-hub"}


@app.get("/api/projects")
def list_projects(public_only: bool = True) -> list[dict]:
    query = "SELECT * FROM projects"
    params: tuple = ()
    if public_only:
        query += " WHERE status = 'published'"
    query += " ORDER BY updated_at DESC"
    with connect() as connection:
        return [row_to_project(row) for row in connection.execute(query, params)]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return row_to_project(row)


@app.post("/api/projects")
def create_project(
    title: str = Form(...),
    summary: str = Form(...),
    category: str = Form(...),
    owner: str = Form(...),
    code_url: str = Form(""),
    video_url: str = Form(""),
    description: str = Form(""),
    tags: str = Form(""),
    version: str = Form("v1.0"),
    is_public: bool = Form(False),
    code_file: UploadFile | None = File(None),
    video_file: UploadFile | None = File(None),
) -> dict:
    project_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    saved_code = save_upload(project_id, code_file, "code")
    saved_video = save_upload(project_id, video_file, "video")
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO projects
            (id, title, summary, category, owner, code_url, video_url, code_file,
             video_file, is_public, description, tags, version, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, title.strip(), summary.strip(), category, owner.strip(), code_url.strip(), video_url.strip(), saved_code, saved_video, int(is_public), description.strip(), tags.strip(), version.strip() or "v1.0", "published" if is_public else "draft", now, now),
        )
    return get_project(project_id)


@app.put("/api/projects/{project_id}")
def update_project(
    project_id: str,
    title: str = Form(...),
    summary: str = Form(...),
    category: str = Form(...),
    owner: str = Form(...),
    code_url: str = Form(""),
    video_url: str = Form(""),
    description: str = Form(""),
    tags: str = Form(""),
    version: str = Form("v1.0"),
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        updated = connection.execute(
            "UPDATE projects SET title=?, summary=?, category=?, owner=?, code_url=?, video_url=?, description=?, tags=?, version=?, updated_at=? WHERE id=?",
            (title.strip(), summary.strip(), category, owner.strip(), code_url.strip(), video_url.strip(), description.strip(), tags.strip(), version.strip() or "v1.0", now, project_id),
        ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="项目不存在")
    return get_project(project_id)


@app.post("/api/projects/{project_id}/status")
def update_status(project_id: str, status: str = Form(...)) -> dict:
    if status not in {"draft", "pending_review", "published", "archived"}:
        raise HTTPException(status_code=400, detail="无效的项目状态")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        updated = connection.execute(
            "UPDATE projects SET status=?, is_public=?, updated_at=? WHERE id=?",
            (status, int(status == "published"), now, project_id),
        ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="项目不存在")
    return get_project(project_id)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    with connect() as connection:
        row = connection.execute("SELECT code_file, video_file FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        connection.execute("DELETE FROM projects WHERE id=?", (project_id,))
    for stored_path in (row["code_file"], row["video_file"]):
        if stored_path:
            file_path = UPLOAD_DIR / Path(stored_path).name
            if file_path.is_file():
                file_path.unlink()


def save_upload(project_id: str, upload: UploadFile | None, kind: str) -> str | None:
    if upload is None or not upload.filename:
        return None
    suffix = Path(upload.filename).suffix.lower()
    safe_name = f"{project_id}_{kind}{suffix}"
    target = UPLOAD_DIR / safe_name
    with target.open("wb") as output:
        while chunk := upload.file.read(1024 * 1024):
            output.write(chunk)
    return f"/uploads/{safe_name}"


# Keep API routes above this mount. It serves the HTML, CSS, and JavaScript
# files that make up the local Atlas frontend.
app.mount("/", StaticFiles(directory=ROOT, html=True), name="frontend_assets")
