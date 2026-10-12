from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 - populate Base.metadata
from app.core.config import Settings, get_settings
from app.core.security import compute_signature
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.invoice import Invoice
from app.models.order import Order
from app.tasks.order_tasks import process_paid_order_task
from app.workflows.order_workflow import process_paid_order

SECRET = "test-webhook-secret"


def _build_payload(event_id: str = "evt-1", order_id: str = "ORD-100") -> dict:
    return {
        "event_id": event_id,
        "event_type": "order.paid",
        "occurred_at": "2026-10-13T10:00:00+05:30",
        "order_id": order_id,
        "customer_id": f"CUS-{order_id}",
        "payment_status": "paid",
        "payment_reference": f"PAY-{order_id}",
        "currency": "INR",
        "customer": {
            "name": "Buyer Pvt Ltd",
            "email": "buyer@example.com",
            "billing_address": {
                "line1": "1 Test St",
                "city": "Mumbai",
                "state": "Maharashtra",
                "state_code": "27",
                "postal_code": "400001",
                "country": "India",
            },
        },
        "items": [
            {
                "product_id": "PROD-1",
                "name": "Widget",
                "product_type": "GOODS",
                "hsn_or_sac_code": "8471",
                "quantity": 1,
                "unit_price": 1000.00,
                "gst_rate": 18.00,
            }
        ],
        "pricing": {
            "tax_inclusive": False,
            "subtotal": 1000.00,
            "tax_total": 180.00,
            "grand_total": 1180.00,
        },
    }


def _sign(body: bytes) -> dict[str, str]:
    ts = str(time.time())
    sig = compute_signature(SECRET, ts, body)
    return {"X-Signature": sig, "X-Timestamp": ts, "Content-Type": "application/json"}


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    settings = Settings(
        COMPANY_LEGAL_NAME="Test Co Pvt Ltd",
        COMPANY_REGISTERED_ADDRESS="123 Test St, Mumbai",
        SELLER_GSTIN="27AAAAA0000A1Z5",
        SELLER_STATE_NAME="Maharashtra",
        SELLER_STATE_CODE="27",
        SUPPORT_EMAIL="support@test.com",
        CRM_WEBHOOK_HMAC_SECRET=SECRET,
        STORAGE_LOCAL_DIR=str(tmp_path / "storage"),
    )

    def _get_db_override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings_override():
        return settings

    def _fake_delay(order_id: str):
        db = TestSessionLocal()
        try:
            process_paid_order(db, order_id, settings)
        finally:
            db.close()

    monkeypatch.setattr(process_paid_order_task, "delay", _fake_delay)
    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_settings] = _get_settings_override

    client = TestClient(app)
    yield client, TestSessionLocal

    app.dependency_overrides.clear()


def test_valid_webhook_creates_exactly_one_invoice(harness):
    client, SessionLocal = harness
    payload = _build_payload()
    body = json.dumps(payload).encode()

    resp = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=_sign(body))
    assert resp.status_code == 202

    db = SessionLocal()
    try:
        orders = db.query(Order).all()
        invoices = db.query(Invoice).all()
        assert len(orders) == 1
        assert len(invoices) == 1
        assert invoices[0].invoice_status == "INVOICE_PDF_GENERATED"
    finally:
        db.close()


def test_repeated_event_id_returns_409_and_creates_no_duplicate(harness):
    client, SessionLocal = harness
    payload = _build_payload(event_id="evt-dup", order_id="ORD-101")
    body = json.dumps(payload).encode()

    first = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=_sign(body))
    second = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=_sign(body))

    assert first.status_code == 202
    assert second.status_code == 409

    db = SessionLocal()
    try:
        assert db.query(Order).count() == 1
        assert db.query(Invoice).count() == 1
    finally:
        db.close()


def test_same_order_id_different_event_id_still_returns_409(harness):
    client, SessionLocal = harness
    first_payload = _build_payload(event_id="evt-a", order_id="ORD-102")
    second_payload = _build_payload(event_id="evt-b", order_id="ORD-102")

    body1 = json.dumps(first_payload).encode()
    body2 = json.dumps(second_payload).encode()

    first = client.post("/api/v1/webhooks/crm/order-paid", content=body1, headers=_sign(body1))
    second = client.post("/api/v1/webhooks/crm/order-paid", content=body2, headers=_sign(body2))

    assert first.status_code == 202
    assert second.status_code == 409

    db = SessionLocal()
    try:
        assert db.query(Order).filter_by(crm_order_id="ORD-102").count() == 1
    finally:
        db.close()


def test_invalid_signature_returns_401(harness):
    client, _ = harness
    payload = _build_payload(event_id="evt-bad-sig", order_id="ORD-103")
    body = json.dumps(payload).encode()

    headers = _sign(body)
    headers["X-Signature"] = "0" * 64  # wrong signature

    resp = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=headers)
    assert resp.status_code == 401


def test_missing_signature_headers_returns_401(harness):
    client, _ = harness
    payload = _build_payload(event_id="evt-no-sig", order_id="ORD-104")
    body = json.dumps(payload).encode()

    resp = client.post(
        "/api/v1/webhooks/crm/order-paid", content=body, headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 401


def test_invalid_schema_returns_400(harness):
    client, _ = harness
    payload = _build_payload(event_id="evt-bad-schema", order_id="ORD-105")
    del payload["customer"]["email"]  # required field
    body = json.dumps(payload).encode()

    resp = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=_sign(body))
    assert resp.status_code == 400


def test_tax_mismatch_webhook_routes_to_manual_review(harness):
    client, SessionLocal = harness
    payload = _build_payload(event_id="evt-mismatch", order_id="ORD-106")
    payload["pricing"]["grand_total"] = 50000.00  # wildly wrong vs. computed GST
    body = json.dumps(payload).encode()

    resp = client.post("/api/v1/webhooks/crm/order-paid", content=body, headers=_sign(body))
    assert resp.status_code == 202

    db = SessionLocal()
    try:
        invoice = db.query(Invoice).one()
        assert invoice.invoice_status == "MANUAL_REVIEW_REQUIRED"
    finally:
        db.close()
