"""Minimal JWT-based internal-user authentication + role-based
authorization. Five roles: ADMIN, DELIVERY_MANAGER, DELIVERY_VIEWER
(Method A / delivery operations) and INVOICE_EDITOR, INVOICE_APPROVER
(Method B draft editing and approval). A user may hold more than one —
see InternalUser.has_role(). No external auth provider, no session
store — this is deliberately small.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.internal_user import InternalUser

ROLES = ("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER", "INVOICE_EDITOR", "INVOICE_APPROVER")
JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=12)

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))


def create_access_token(user: InternalUser, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> InternalUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    claims = decode_access_token(credentials.credentials, settings)
    user = db.query(InternalUser).filter_by(id=claims["sub"], is_active=True).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")
    return user


def require_role(*allowed_roles: str):
    """ADMIN always passes — it is the superset role (§12). Everyone
    else needs at least one of `allowed_roles` in their own role set.
    """

    def _dependency(user: Annotated[InternalUser, Depends(get_current_user)]) -> InternalUser:
        if user.has_role("ADMIN") or user.has_role(*allowed_roles):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"role(s) {user.role!r} not permitted to perform this action",
        )

    return _dependency
