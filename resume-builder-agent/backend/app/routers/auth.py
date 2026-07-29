from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, SignUpRequest, UserOut
from app.security import (
    ACCESS_COOKIE,
    clear_auth_cookies,
    create_access_token,
    decode_token,
    get_current_user,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from fastapi import Cookie

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut.model_validate(
        {**user.__dict__, "has_password": user.password_hash is not None}
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        gender=payload.gender,
        address_type=payload.address_type,
        address=payload.address,
        country_code=payload.country_code,
        phone=payload.phone,
        country=payload.country,
        state=payload.state,
        city=payload.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    set_auth_cookies(response, user.id)
    return _to_user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or user.password_hash is None or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    set_auth_cookies(response, user.id)
    return _to_user_out(user)


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh", response_model=UserOut)
def refresh(
    response: Response,
    rb_refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not rb_refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_token(rb_refresh_token, "refresh")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user.id),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return _to_user_out(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return _to_user_out(current_user)
