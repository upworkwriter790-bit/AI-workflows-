import secrets

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import set_auth_cookies

router = APIRouter(prefix="/auth", tags=["oauth"])
settings = get_settings()

STATE_COOKIE = "rb_oauth_state"


def _find_or_create_user(
    db: Session,
    *,
    provider_field: str,
    provider_id: str,
    email: str,
    first_name: str,
    last_name: str,
) -> User:
    user = db.query(User).filter(getattr(User, provider_field) == provider_id).first()
    if user is not None:
        return user

    # Link to an existing email/password account with the same email.
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is not None:
        setattr(user, provider_field, provider_id)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=email.lower(),
        password_hash=None,
        first_name=first_name,
        last_name=last_name,
        **{provider_field: provider_id},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _finish_login(db: Session, user: User) -> RedirectResponse:
    redirect = RedirectResponse(url=f"{settings.frontend_url}/dashboard")
    set_auth_cookies(redirect, user.id)
    redirect.delete_cookie(STATE_COOKIE, path="/")
    return redirect


# ── Google ──────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login")
def google_login():
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")

    state = secrets.token_urlsafe(24)
    redirect_uri = f"{settings.backend_url}/auth/google/callback"
    params = httpx.QueryParams(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    redirect = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")
    redirect.set_cookie(STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600, path="/")
    return redirect


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    rb_oauth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not rb_oauth_state or state != rb_oauth_state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")

    redirect_uri = f"{settings.backend_url}/auth/google/callback"
    with httpx.Client(timeout=10) as client:
        token_res = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        user_res = client.get(
            GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        user_res.raise_for_status()
        profile = user_res.json()

    user = _find_or_create_user(
        db,
        provider_field="google_id",
        provider_id=profile["sub"],
        email=profile.get("email", ""),
        first_name=profile.get("given_name", ""),
        last_name=profile.get("family_name", ""),
    )
    return _finish_login(db, user)


# ── GitHub ──────────────────────────────────────────────────────────────

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/github/login")
def github_login():
    if not settings.github_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GitHub sign-in is not configured")

    state = secrets.token_urlsafe(24)
    redirect_uri = f"{settings.backend_url}/auth/github/callback"
    params = httpx.QueryParams(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
    )
    redirect = RedirectResponse(url=f"{GITHUB_AUTH_URL}?{params}")
    redirect.set_cookie(STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600, path="/")
    return redirect


@router.get("/github/callback")
def github_callback(
    code: str,
    state: str,
    rb_oauth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not rb_oauth_state or state != rb_oauth_state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")

    redirect_uri = f"{settings.backend_url}/auth/github/callback"
    with httpx.Client(timeout=10, headers={"Accept": "application/json"}) as client:
        token_res = client.post(
            GITHUB_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        token_res.raise_for_status()
        token_json = token_res.json()
        if "access_token" not in token_json:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub authorization failed")
        access_token = token_json["access_token"]

        auth_header = {"Authorization": f"Bearer {access_token}"}
        user_res = client.get(GITHUB_USER_URL, headers=auth_header)
        user_res.raise_for_status()
        profile = user_res.json()

        email = profile.get("email")
        if not email:
            emails_res = client.get(GITHUB_EMAILS_URL, headers=auth_header)
            emails_res.raise_for_status()
            primary = next(
                (e for e in emails_res.json() if e.get("primary") and e.get("verified")), None
            )
            email = primary["email"] if primary else f"{profile['id']}+{profile['login']}@users.noreply.github.com"

    full_name = (profile.get("name") or profile.get("login") or "").strip()
    first_name, _, last_name = full_name.partition(" ")

    user = _find_or_create_user(
        db,
        provider_field="github_id",
        provider_id=str(profile["id"]),
        email=email,
        first_name=first_name or profile.get("login", ""),
        last_name=last_name,
    )
    return _finish_login(db, user)
