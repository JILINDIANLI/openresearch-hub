from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from redis.exceptions import RedisError

from .cache import redis_client
from .config import settings


ALGORITHM = "HS256"
ACCESS_COOKIE_NAME = "openresearch_session"
password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash new passwords with Argon2id."""
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$argon2"):
        try:
            return password_hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    try:
        _, iterations, expected = stored_hash.split("$", 2)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"openresearch-v1", int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str = "USER", token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role.upper(),
            "tv": token_version,
            "jti": uuid.uuid4().hex,
            "exp": expires,
            "iat": now,
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def get_request_access_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is not None:
        return credentials.credentials
    return request.cookies.get(ACCESS_COOKIE_NAME)


def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        if not payload.get("jti"):
            raise JWTError("Token identifier is missing")
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _is_revoked(jti: str) -> bool:
    try:
        return bool(redis_client().get(f"openresearch:auth:revoked:{jti}"))
    except RedisError as exc:
        if settings.app_env == "production":
            raise HTTPException(status_code=503, detail="登录凭证检查暂不可用") from exc
        return False


def revoke_access_token(token: str) -> None:
    payload = _decode_token(token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    lifetime = max(1, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    try:
        redis_client().setex(f"openresearch:auth:revoked:{payload['jti']}", lifetime, "1")
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="注销暂不可用，请稍后重试") from exc


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    from ..database.database import SessionLocal
    from ..database.models import User

    token = get_request_access_token(request, credentials)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(token)
    if _is_revoked(str(payload["jti"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证已注销",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload.get("sub"))
        token_version = int(payload.get("tv", -1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="登录凭证无效", headers={"WWW-Authenticate": "Bearer"}) from exc
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active or user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在、已停用或登录凭证已失效",
                headers={"WWW-Authenticate": "Bearer"},
            )
        db.expunge(user)
        return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if get_request_access_token(request, credentials) is None:
        return None
    try:
        return get_current_user(request, credentials)
    except HTTPException:
        return None


def require_admin(current_user=Depends(get_current_user)):
    if (current_user.role or "USER").upper() != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理员权限不足")
    return current_user
