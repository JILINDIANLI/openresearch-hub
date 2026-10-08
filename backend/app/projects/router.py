from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database.database import get_db
from ..core.security import get_current_user, get_optional_user
from ..database.models import Project, Resource, User
from ..services.visibility import public_resource_conditions, require_viewable_resource
from ..resources.router import serialize_resource
from .schemas import ProjectCreate

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    visibility = public_resource_conditions()
    query = select(Project).join(Project.resource).options(selectinload(Project.resource).selectinload(Resource.author))
    if current_user is not None:
        query = query.where(or_(and_(*visibility), Resource.author_id == current_user.id))
    else:
        query = query.where(*visibility)
    projects = db.scalars(query.order_by(Project.id.desc())).all()
    return [serialize_resource(project.resource) | {"project": {"leader": project.leader, "members": project.members.split(", ") if project.members else [], "status": project.status, "github_url": project.github_url, "paper_url": project.paper_url, "demo_url": project.demo_url}} for project in projects]


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    project = db.scalar(select(Project).options(selectinload(Project.resource).selectinload(Resource.author)).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    require_viewable_resource(project.resource, current_user)
    return serialize_resource(project.resource) | {"project": {"leader": project.leader, "members": project.members.split(", ") if project.members else [], "status": project.status, "github_url": project.github_url, "paper_url": project.paper_url, "demo_url": project.demo_url}}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = db.get(Resource, payload.resource_id)
    if resource is None or resource.resource_type != "project":
        raise HTTPException(status_code=404, detail="项目资源不存在")
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有项目资源作者可以创建项目详情")
    if db.scalar(select(Project).where(Project.resource_id == payload.resource_id)):
        raise HTTPException(status_code=409, detail="项目详情已存在")
    project = Project(resource_id=payload.resource_id, leader=payload.leader, members=", ".join(payload.members), status=payload.status, github_url=payload.github_url, paper_url=payload.paper_url, demo_url=payload.demo_url)
    db.add(project)
    db.commit()
    db.refresh(project)
    return get_project(project.id, db, current_user)
