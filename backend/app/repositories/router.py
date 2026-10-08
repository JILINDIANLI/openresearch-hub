from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.cache import repository_cache_delete, repository_cache_get, repository_cache_set
from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Repository, Resource, User
from ..services.gitea_service import GiteaError, gitea_service
from ..services.visibility import require_viewable_resource
from .schemas import RepositoryBranch, RepositoryCommit, RepositoryCreate, RepositoryFile, RepositoryFileContent, RepositoryRead

router = APIRouter(prefix="/api/resources", tags=["Repositories"])


def resource_or_404(db: Session, resource_id: int) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return resource


def visible_repository(resource: Resource, user: User | None) -> Repository:
    require_viewable_resource(resource, user)
    repository = resource.repository
    if repository is None:
        raise HTTPException(status_code=404, detail="该资源尚未关联代码仓库")
    if repository.visibility == "PRIVATE" and (user is None or resource.author_id != user.id):
        raise HTTPException(status_code=404, detail="代码仓库不存在")
    return repository


def sync_record(db: Session, repository: Repository) -> Repository:
    data = gitea_service.get(repository.owner, repository.name)
    for key, value in data.items():
        if key not in {"provider", "owner", "name", "full_name"} and hasattr(repository, key):
            setattr(repository, key, value)
    repository_cache_set(repository.owner, repository.name, data)
    db.commit()
    db.refresh(repository)
    return repository


@router.post("/{resource_id}/repository", response_model=RepositoryRead, status_code=201)
def create_repository(resource_id: int, payload: RepositoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = resource_or_404(db, resource_id)
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以创建代码仓库")
    if resource.repository is not None:
        raise HTTPException(status_code=409, detail="该资源已经关联代码仓库")
    try:
        data = gitea_service.create(payload.model_dump())
        repository = Repository(resource_id=resource.id, **data)
        db.add(repository)
        db.commit()
        db.refresh(repository)
        repository_cache_set(repository.owner, repository.name, data)
        return repository
    except GiteaError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="该代码仓库已被关联或名称重复") from exc


@router.get("/{resource_id}/repository", response_model=RepositoryRead)
def get_repository(resource_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    resource = resource_or_404(db, resource_id)
    repository = visible_repository(resource, current_user)
    cached = repository_cache_get(repository.owner, repository.name)
    if cached:
        for key, value in cached.items():
            if key not in {"provider", "owner", "name", "full_name"} and hasattr(repository, key):
                setattr(repository, key, value)
    else:
        try:
            repository = sync_record(db, repository)
        except GiteaError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return repository


@router.delete("/{resource_id}/repository", status_code=204)
def delete_repository(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = resource_or_404(db, resource_id)
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有资源作者可以解除代码仓库关联")
    repository = resource.repository
    if repository is None:
        raise HTTPException(status_code=404, detail="该资源尚未关联代码仓库")
    try:
        gitea_service.delete(repository.owner, repository.name)
    except GiteaError as exc:
        if exc.status_code not in {404}:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    repository_cache_delete(repository.owner, repository.name)
    db.delete(repository)
    db.commit()


@router.post("/{resource_id}/repository/sync", response_model=RepositoryRead)
def sync_repository(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = resource_or_404(db, resource_id)
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有资源作者可以同步代码仓库")
    if resource.repository is None:
        raise HTTPException(status_code=404, detail="该资源尚未关联代码仓库")
    try:
        return sync_record(db, resource.repository)
    except GiteaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def repo_for_child(resource_id: int, db: Session, current_user: User | None):
    resource = resource_or_404(db, resource_id)
    return visible_repository(resource, current_user)


@router.get("/{resource_id}/repository/commits", response_model=list[RepositoryCommit])
def repository_commits(resource_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    repository = repo_for_child(resource_id, db, current_user)
    try:
        return gitea_service.commits(repository.owner, repository.name)
    except GiteaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{resource_id}/repository/branches", response_model=list[RepositoryBranch])
def repository_branches(resource_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    repository = repo_for_child(resource_id, db, current_user)
    try:
        return gitea_service.branches(repository.owner, repository.name)
    except GiteaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{resource_id}/repository/tree", response_model=list[RepositoryFile])
def repository_tree(resource_id: int, path: str = Query(default=""), ref: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    repository = repo_for_child(resource_id, db, current_user)
    try:
        return gitea_service.contents(repository.owner, repository.name, path, ref or repository.default_branch)
    except GiteaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{resource_id}/repository/file", response_model=RepositoryFileContent)
def repository_file(resource_id: int, path: str = Query(min_length=1), ref: str | None = None, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    repository = repo_for_child(resource_id, db, current_user)
    try:
        return gitea_service.file(repository.owner, repository.name, path, ref or repository.default_branch)
    except GiteaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
