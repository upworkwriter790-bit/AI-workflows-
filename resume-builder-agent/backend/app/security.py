import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_COOKIE = "rb_access_token"
REFRESH_COOKIE = "rb_refresh_token"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id), timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id), timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


def decode_token(token: str, expected_type: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject") from exc


def get_current_user(
    rb_access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not rb_access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_token(rb_access_token, "access")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def set_auth_cookies(response: Response, user_id: uuid.UUID) -> None:
    is_https = settings.backend_url.startswith("https")
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id),
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(user_id),
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
