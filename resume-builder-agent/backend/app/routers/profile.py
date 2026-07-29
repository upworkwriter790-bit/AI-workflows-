from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ChangePasswordRequest, ProfileUpdateRequest, UserOut
from app.security import get_current_user, hash_password, verify_password
from fastapi import HTTPException, status

router = APIRouter(prefix="/profile", tags=["profile"])


def _to_user_out(user: User) -> UserOut:
    return UserOut.model_validate(
        {**user.__dict__, "has_password": user.password_hash is not None}
    )


@router.get("", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return _to_user_out(current_user)


@router.put("", response_model=UserOut)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _to_user_out(current_user)


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.password_hash is not None:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.password_hash
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)
    return _to_user_out(current_user)
