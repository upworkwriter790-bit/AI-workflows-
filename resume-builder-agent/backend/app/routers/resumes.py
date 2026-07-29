import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Resume, User
from app.schemas import ResumeCreate, ResumeOut, ResumeUpdate
from app.security import get_current_user

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_owned_resume(db: Session, resume_id: uuid.UUID, user: User) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.updated_at.desc())
        .all()
    )


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def create_resume(
    payload: ResumeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = Resume(user_id=current_user.id, **payload.model_dump())
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_resume(db, resume_id, current_user)


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_owned_resume(db, resume_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(resume, field, value)
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_owned_resume(db, resume_id, current_user)
    db.delete(resume)
    db.commit()


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF or Word documents are accepted"
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large (max 10 MB)")

    user_dir = Path(settings.upload_dir) / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    resume_id = uuid.uuid4()
    extension = Path(file.filename or "").suffix or ".pdf"
    stored_path = user_dir / f"{resume_id}{extension}"
    stored_path.write_bytes(contents)

    resume = Resume(
        id=resume_id,
        user_id=current_user.id,
        title=Path(file.filename or "Uploaded Resume").stem,
        template_id="uploaded",
        source="upload",
        uploaded_file_path=str(stored_path),
        data={},
        styles={},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume
