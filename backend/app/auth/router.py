from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    ACCESS_COOKIE_NAME,
    bearer_scheme,
    create_access_token,
    get_current_user,
    get_request_access_token,
    revoke_access_token,
)
from ..database.database import get_db
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from .service import authenticate_user, register_user, user_to_dict

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


@router.post("/bootstrap-admin", status_code=201)
def bootstrap_admin(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if settings.app_env != "production" or os.getenv("ALLOW_ADMIN_BOOTSTRAP", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    from sqlalchemy import func, select
    from ..database.models import User
    if int(db.scalar(select(func.count(User.id))) or 0) != 0:
        raise HTTPException(status_code=409, detail="Initial administrator has already been created")
    supplied = request.headers.get("x-admin-bootstrap-key", "")
    expected = os.getenv("ADMIN_BOOTSTRAP_KEY", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Bootstrap key is invalid")
    try:
        user = register_user(db, payload)
        user.role = "ADMIN"
        db.commit()
        db.refresh(user)
        os.environ["ALLOW_ADMIN_BOOTSTRAP"] = "false"
        return user_to_dict(user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if settings.app_env == "production" and os.getenv("ALLOW_PUBLIC_REGISTRATION", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Registration is currently disabled")
    if settings.app_env == "production":
        from sqlalchemy import func, select
        from ..database.models import User
        if int(db.scalar(select(func.count(User.id)).where(User.role == "ADMIN", User.is_active.is_(True))) or 0) == 0:
            raise HTTPException(status_code=403, detail="Administrator setup is required before public registration")
    try:
        user = register_user(db, payload)
        db.commit()
        db.refresh(user)
        return user_to_dict(user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在") from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.identifier, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名/邮箱或密码错误", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(user.id, user.role, user.token_version)
    set_session_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 60 * settings.access_token_expire_minutes,
        "user": user_to_dict(user),
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    _: object = Depends(get_current_user),
):
    token = get_request_access_token(request, credentials)
    if token is not None:
        revoke_access_token(token)
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
def me(current_user=Depends(get_current_user)):
    return user_to_dict(current_user)
