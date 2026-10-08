from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database.database import get_db
from ..database.models import Tag, User
from .schemas import TagCreate

router = APIRouter(prefix="/api/tags", tags=["Tags"])


@router.get("")
def list_tags(db: Session = Depends(get_db)):
    return [{"id": tag.id, "name": tag.name, "description": tag.description} for tag in db.scalars(select(Tag).order_by(Tag.name)).all()]


@router.post("", status_code=201)
def create_tag(payload: TagCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    name = payload.name.strip()
    if db.scalar(select(Tag).where(Tag.name == name)):
        raise HTTPException(status_code=409, detail="标签已存在")
    tag = Tag(name=name, description=payload.description)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "description": tag.description}
