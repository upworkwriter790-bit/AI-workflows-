from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 - populate Base.metadata
from app.core.auth import create_access_token, hash_password
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.internal_user import InternalUser


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    """Full API harness: in-memory SQLite shared across requests (StaticPool),
    test Settings, an ADMIN bearer token, and Celery `.delay()` calls for
    email/WhatsApp dispatch rewired to run synchronously against the same
    test database instead of needing a real broker.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    settings = Settings(
        STORAGE_LOCAL_DIR=str(tmp_path / "storage"),
        SUPPORT_EMAIL="support@test.com",
        COMPANY_LEGAL_NAME="Test Co Pvt Ltd",
        APP_BASE_URL="http://test.local",
        JWT_SECRET="test-jwt-secret",
    )

    def _get_db_override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings_override():
        return settings

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_settings] = _get_settings_override

    seed_db = TestSessionLocal()
    admin = InternalUser(
        email="admin@test.com", display_name="Admin", password_hash=hash_password("x"), role="ADMIN",
    )
    manager = InternalUser(
        email="manager@test.com", display_name="Manager", password_hash=hash_password("x"),
        role="DELIVERY_MANAGER",
    )
    viewer = InternalUser(
        email="viewer@test.com", display_name="Viewer", password_hash=hash_password("x"),
        role="DELIVERY_VIEWER",
    )
    seed_db.add_all([admin, manager, viewer])
    seed_db.commit()
    admin_token = create_access_token(admin, settings)
    manager_token = create_access_token(manager, settings)
    viewer_token = create_access_token(viewer, settings)
    seed_db.close()

    from app.tasks import delivery_tasks
    from app.workflows.delivery_workflow import dispatch_email_attempt, dispatch_whatsapp_attempt
    from app.models.delivery_attempt import DeliveryAttempt

    def _fake_send_email(attempt_id, *, attach_pdf, include_download_link):
        db = TestSessionLocal()
        try:
            attempt = db.query(DeliveryAttempt).filter_by(id=attempt_id).one()
            outcome = dispatch_email_attempt(
                db, settings, attempt, attach_pdf=attach_pdf, include_download_link=include_download_link
            )
            while outcome.should_retry:
                outcome = dispatch_email_attempt(
                    db, settings, attempt, attach_pdf=attach_pdf, include_download_link=include_download_link
                )
        finally:
            db.close()

    def _fake_send_whatsapp(attempt_id, *, include_download_link):
        db = TestSessionLocal()
        try:
            attempt = db.query(DeliveryAttempt).filter_by(id=attempt_id).one()
            outcome = dispatch_whatsapp_attempt(db, settings, attempt, include_download_link=include_download_link)
            while outcome.should_retry:
                outcome = dispatch_whatsapp_attempt(db, settings, attempt, include_download_link=include_download_link)
        finally:
            db.close()

    monkeypatch.setattr(delivery_tasks.send_email_attempt_task, "delay", _fake_send_email)
    monkeypatch.setattr(delivery_tasks.send_whatsapp_attempt_task, "delay", _fake_send_whatsapp)

    client = TestClient(app)

    class Harness:
        pass

    h = Harness()
    h.client = client
    h.SessionLocal = TestSessionLocal
    h.settings = settings
    h.admin_headers = {"Authorization": f"Bearer {admin_token}"}
    h.manager_headers = {"Authorization": f"Bearer {manager_token}"}
    h.viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    yield h

    app.dependency_overrides.clear()
