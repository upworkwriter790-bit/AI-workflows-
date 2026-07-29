from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, oauth, profile, resumes

settings = get_settings()

app = FastAPI(title="Resume Builder Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(profile.router)
app.include_router(resumes.router)


@app.on_event("startup")
def on_startup() -> None:
    # Creates tables if they don't exist yet. For schema changes in
    # production, switch to Alembic migrations (see backend/README.md).
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
