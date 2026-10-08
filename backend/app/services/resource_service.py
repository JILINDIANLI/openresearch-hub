from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database.models import (
    Algorithm,
    Dataset,
    Demo,
    Model,
    Paper,
    Project,
    Resource,
    Tag,
    Tutorial,
    User,
)
from ..resources.schemas import ResourceCreate


class ResourceService:
    """Business operations for resources, including one-transaction publishing."""

    @staticmethod
    def get(db: Session, resource_id: int) -> Resource | None:
        return db.get(Resource, resource_id)

    @staticmethod
    def delete(db: Session, resource_id: int) -> bool:
        resource = db.get(Resource, resource_id)
        if resource is None:
            return False
        db.delete(resource)
        db.commit()
        return True

    @staticmethod
    def tags(db: Session, names: list[str]) -> list[Tag]:
        result: list[Tag] = []
        seen: set[str] = set()
        for raw_name in names:
            name = raw_name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            tag = db.scalar(select(Tag).where(func.lower(Tag.name) == name.lower()))
            if tag is None:
                tag = Tag(name=name, description=f"OpenResearch research tag: {name}")
                db.add(tag)
                db.flush()
            result.append(tag)
        return result

    @staticmethod
    def _detail_values(payload: ResourceCreate, resource_type: str) -> dict:
        typed = getattr(payload, resource_type, None)
        if typed is not None:
            return typed.model_dump(exclude_none=True)
        legacy = payload.details.get(resource_type)
        if isinstance(legacy, dict):
            return dict(legacy)
        return {}

    @staticmethod
    def _add_extension(db: Session, resource: Resource, resource_type: str, values: dict) -> None:
        if resource_type == "model":
            db.add(Model(resource_id=resource.id, framework=values.get("framework", ""), task=values.get("task", ""), parameters=values.get("parameters", ""), model_url=values.get("model_url")))
        elif resource_type == "dataset":
            download_url = values.get("download_url") or values.get("dataset_url")
            db.add(Dataset(resource_id=resource.id, name=values.get("name", resource.title), size=values.get("size", ""), format=values.get("format", ""), task=values.get("task", ""), download_count=int(values.get("download_count", 0) or 0), dataset_url=download_url, download_url=download_url))
        elif resource_type == "algorithm":
            db.add(Algorithm(resource_id=resource.id, category=values.get("category", ""), difficulty=values.get("difficulty", ""), paper_url=values.get("paper_url"), code_url=values.get("code_url")))
        elif resource_type == "project":
            members = values.get("members", [])
            if isinstance(members, list):
                members = ", ".join(str(item).strip() for item in members if str(item).strip())
            db.add(Project(resource_id=resource.id, leader=values.get("leader", ""), members=str(members or ""), status=values.get("status", "published"), github_url=values.get("github_url"), paper_url=values.get("paper_url"), demo_url=values.get("demo_url")))
        elif resource_type == "paper":
            authors = values.get("authors", [])
            if isinstance(authors, list):
                authors = ", ".join(str(item).strip() for item in authors if str(item).strip())
            db.add(Paper(resource_id=resource.id, title=values.get("title", resource.title), authors=str(authors or ""), journal=values.get("journal"), year=values.get("year"), doi=values.get("doi"), pdf_url=values.get("pdf_url"), abstract=values.get("abstract", "")))
        elif resource_type == "demo":
            db.add(Demo(resource_id=resource.id, video_url=values.get("video_url"), project_url=values.get("project_url"), duration=values.get("duration", "")))
        elif resource_type == "tutorial":
            db.add(Tutorial(resource_id=resource.id, difficulty=values.get("difficulty", ""), duration=values.get("duration", ""), content_url=values.get("content_url")))

    @staticmethod
    def update_extension(resource: Resource, details: dict) -> None:
        """Keep the typed extension row synchronized with edit-mode details."""
        values = details.get(resource.resource_type)
        if not isinstance(values, dict):
            return
        extension = getattr(resource, resource.resource_type, None)
        if extension is None:
            return
        for key, value in values.items():
            if key in {"id", "resource_id"}:
                continue
            if resource.resource_type == "dataset" and key == "download_url":
                extension.download_url = value
                extension.dataset_url = value
                continue
            if resource.resource_type in {"project", "paper"} and key in {"members", "authors"} and isinstance(value, list):
                value = ", ".join(str(item).strip() for item in value if str(item).strip())
            if hasattr(extension, key):
                setattr(extension, key, value)

    @classmethod
    def create(cls, db: Session, payload: ResourceCreate, author: User) -> Resource:
        resource_type = payload.resource_type.lower()
        values = cls._detail_values(payload, resource_type)
        details = dict(payload.details)
        if values:
            details[resource_type] = values
        resource = Resource(
            title=payload.title.strip(),
            resource_type=resource_type,
            description=payload.description.strip(),
            author_id=author.id,
            license=payload.license,
            visibility=payload.visibility,
            review_status="PENDING",
            research_field=payload.research_field,
            thumbnail_url=payload.thumbnail_url,
            repository_url=payload.repository_url,
            homepage_url=payload.homepage_url,
            details_json=json.dumps(details, ensure_ascii=False),
            tags=cls.tags(db, payload.tags),
        )
        try:
            db.add(resource)
            db.flush()
            cls._add_extension(db, resource, resource_type, values)
            db.commit()
            db.refresh(resource)
            return resource
        except Exception:
            db.rollback()
            raise
