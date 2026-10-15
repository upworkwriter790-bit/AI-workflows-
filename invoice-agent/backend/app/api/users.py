"""ADMIN-only internal-user management — lets an admin create the
INVOICE_EDITOR/INVOICE_APPROVER/DELIVERY_MANAGER/DELIVERY_VIEWER users
a real rollout needs, from the UI, instead of a DB script.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.auth import ROLES, InternalUser, hash_password, require_role
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    display_name: str
    password: str = Field(min_length=8)
    roles: list[str] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def roles_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown role(s): {sorted(unknown)}")
        return v


def _serialize(user: InternalUser) -> dict:
    return {
        "id": user.id, "email": user.email, "display_name": user.display_name,
        "roles": sorted(user.role_set), "is_active": user.is_active,
    }


@router.get("")
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN"))],
) -> dict:
    return {"users": [_serialize(u) for u in db.query(InternalUser).order_by(InternalUser.email).all()]}


@router.post("", status_code=201)
def create_user(
    payload: CreateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN"))],
) -> dict:
    email = payload.email.strip().lower()
    if db.query(InternalUser).filter_by(email=email).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="a user with this email already exists")

    user = InternalUser(
        email=email, display_name=payload.display_name,
        password_hash=hash_password(payload.password), role=",".join(payload.roles),
    )
    db.add(user)
    db.commit()
    return _serialize(user)
