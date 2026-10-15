"""Self-serve login. Previously users were seeded directly with no
login endpoint — added here so the (also new) UI has something to call.
Still minimal: no refresh tokens, no password reset, no sessions table.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import (
    InternalUser,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user = db.query(InternalUser).filter_by(email=payload.email.strip().lower(), is_active=True).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")

    token = create_access_token(user, settings)
    return {
        "access_token": token,
        "user_id": user.id,
        "display_name": user.display_name,
        "role": user.role,
    }


@router.get("/me")
def me(user: Annotated[InternalUser, Depends(get_current_user)]) -> dict:
    # Convenience endpoint the frontend uses to validate a stored token
    # and discover the current user's own roles without decoding the JWT
    # client-side.
    return {"user_id": user.id, "display_name": user.display_name, "email": user.email, "role": user.role}
