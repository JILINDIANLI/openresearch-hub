from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.database import get_db
from .schemas import PublicStatistics
from .service import public_statistics


router = APIRouter(prefix="/api/statistics", tags=["Public Statistics"])


@router.get("", response_model=PublicStatistics, summary="Public platform statistics")
def get_public_statistics(db: Session = Depends(get_db)):
    return public_statistics(db)

