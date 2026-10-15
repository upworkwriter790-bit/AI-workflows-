"""Mode B1 — Quick Create. Exact-match deterministic lookups only;
the mock AI provider echoes those candidates back without ever
inventing a value.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.customer import Customer
from app.models.generated_invoice import GeneratedInvoice
from app.models.product_catalog_item import ProductCatalogItem


def _seed_catalog(db, **overrides):
    item = ProductCatalogItem(
        internal_reference="ANNUAL-PLAN", display_description="Annual Premium Plan",
        aliases_json=["annual plan", "premium yearly"], product_type="SERVICE",
        hsn_or_sac_code="9983", unit="Year", unit_price=Decimal("2999.00"), gst_rate=Decimal("18.00"),
        active=True,
    )
    for k, v in overrides.items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    return item


def _seed_customer(db, **overrides):
    customer = Customer(
        display_name="Jane Buyer", email="jane@example.com", phone="+919876543210",
        state_name="Maharashtra", state_code="27",
        billing_address_json={
            "line1": "1 MG Road", "city": "Mumbai", "state": "Maharashtra",
            "state_code": "27", "postal_code": "400001", "country": "India",
        },
        source="MANUAL",
    )
    for k, v in overrides.items():
        setattr(customer, k, v)
    db.add(customer)
    db.commit()
    return customer


def test_exact_email_and_alias_match_is_ready_for_draft(harness):
    db = harness.SessionLocal()
    try:
        _seed_catalog(db)
        _seed_customer(db)
    finally:
        db.close()

    resp = harness.client.post(
        "/api/v1/quick-create/resolve",
        json={
            "customer_email": "jane@example.com", "amount_paid": 2999.00,
            "payment_reference": "TXN-1001", "product_text": "annual plan",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "READY_FOR_DRAFT"
    assert body["customer"]["email"] == "jane@example.com"
    assert body["product"]["hsn_or_sac_code"] == "9983"


def test_ambiguous_product_asks_one_question_and_creates_no_draft(harness):
    db = harness.SessionLocal()
    try:
        _seed_catalog(db)
        _seed_catalog(
            db, internal_reference="MONTHLY-PLAN", display_description="Monthly Plan",
            aliases_json=["monthly plan"],
        )
        _seed_customer(db)
    finally:
        db.close()

    resp = harness.client.post(
        "/api/v1/quick-create/draft",
        json={
            "customer_email": "jane@example.com", "amount_paid": 2999.00,
            "payment_reference": "TXN-1002", "product_text": "plan",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["outcome"] == "NEEDS_ONE_QUESTION"
    assert detail["clarification"] is not None

    db = harness.SessionLocal()
    try:
        assert db.query(GeneratedInvoice).count() == 0
    finally:
        db.close()


def test_no_product_match_asks_what_was_purchased(harness):
    """No catalog candidate at all for the free text given — rather than
    a long form, the system asks the one question that would resolve it.
    """
    db = harness.SessionLocal()
    try:
        _seed_customer(db)
    finally:
        db.close()

    resp = harness.client.post(
        "/api/v1/quick-create/resolve",
        json={
            "customer_email": "jane@example.com", "amount_paid": 500.00,
            "payment_reference": "TXN-1003", "product_text": "something nobody sells",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "NEEDS_ONE_QUESTION"
    assert body["clarification"]["field_needed"] == "product_or_service"


def test_unknown_customer_and_unknown_product_needs_detailed_form(harness):
    resp = harness.client.post(
        "/api/v1/quick-create/resolve",
        json={
            "customer_email": "nobody@example.com", "amount_paid": 500.00,
            "payment_reference": "TXN-1004",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] in {"NEEDS_ONE_QUESTION", "NEEDS_DETAILED_FORM"}
    assert body["customer"] is None


def test_quick_create_draft_matches_normal_draft_review_workflow(harness):
    db = harness.SessionLocal()
    try:
        _seed_catalog(db)
        _seed_customer(db)
    finally:
        db.close()

    resp = harness.client.post(
        "/api/v1/quick-create/draft",
        json={
            "customer_email": "jane@example.com", "amount_paid": 2999.00,
            "payment_reference": "TXN-1005", "product_text": "annual plan",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 201
    invoice_id = resp.json()["invoice_id"]
    assert resp.json()["status"] == "PENDING_HUMAN_REVIEW"

    detail = harness.client.get(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}", headers=harness.editor_headers
    )
    assert detail.status_code == 200
    assert detail.json()["is_editable"] is True


def test_ai_never_picks_a_candidate_outside_what_backend_found(harness, monkeypatch):
    """Even if a (hypothetical) misbehaving AI provider returns an id
    that wasn't in the candidate list, the workflow must ignore it.
    """
    from app.workflows import quick_create_workflow as qcw

    db = harness.SessionLocal()
    try:
        _seed_catalog(db)
        customer = _seed_customer(db)
        customer_id = customer.id
    finally:
        db.close()

    class _RogueProvider:
        name = "rogue"

        def generate_prefill(self, *, system_prompt, context):
            return {
                "outcome": "READY_FOR_DRAFT",
                "customer_match": {
                    "customer_id": "not-a-real-id", "confidence": 0.99, "match_basis": "USER_INPUT",
                },
                "product_match": {
                    "catalog_item_id": "also-not-real", "confidence": 0.99, "match_basis": "USER_SELECTION",
                },
                "missing_critical_fields": [],
                "single_clarification_question": None,
                "reviewer_summary": "rogue",
                "warnings": [],
            }

        def generate_edit_proposal(self, *, system_prompt, context):
            raise NotImplementedError

    monkeypatch.setattr(qcw, "get_ai_provider", lambda settings: _RogueProvider())

    resp = harness.client.post(
        "/api/v1/quick-create/resolve",
        json={
            "customer_email": "jane@example.com", "amount_paid": 2999.00,
            "payment_reference": "TXN-1006", "product_text": "annual plan",
        },
        headers=harness.editor_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    # The rogue ids aren't in the candidate lists the backend found, so
    # both get discarded entirely rather than trusted.
    assert body["customer"] is None
    assert body["product"] is None
    assert customer_id  # the real candidate did exist deterministically
