"""Draft-versioning + AI edit-proposal safety tests — the hard rules:
AI never writes to the database, never approves, never sends, and a
human must explicitly apply/approve everything.
"""

from __future__ import annotations

from app.models.delivery_attempt import DeliveryAttempt
from app.models.generated_invoice import GeneratedInvoice
from app.models.invoice_draft_version import InvoiceDraftVersion
from app.models.invoice_edit_proposal import InvoiceEditProposal


def _base_payload(**overrides):
    payload = {
        "idempotency_key": "ai-key-1",
        "external_reference": "ORD-AI-100",
        "recipient": {
            "name": "Buyer Pvt Ltd",
            "email": "buyer@example.com",
            "phone": "+919876543210",
            "billing_address": {
                "line1": "1 Test St", "city": "Mumbai", "state": "Maharashtra",
                "state_code": "27", "postal_code": "400001", "country": "India",
            },
        },
        "payment_or_order_details": {
            "payment_reference": "PAY-AI-100", "payment_date": "2026-10-14", "currency": "INR",
            "tax_inclusive": False, "subtotal": 1000.00, "discount_total": 0,
            "tax_total": 180.00, "grand_total": 1180.00, "payment_status": "PAID",
        },
        "items": [
            {
                "description": "Pro Plan", "product_type": "SERVICE", "hsn_or_sac_code": "9983",
                "quantity": 1, "unit": "Nos", "unit_price": 1000.00, "gst_rate": 18.00,
            }
        ],
        "delivery": {"requested_channels": ["email"]},
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _post(client, headers, payload):
    return client.post("/api/v1/generated-invoice-deliveries", json=payload, headers=headers)


def test_draft_saved_with_no_delivery_attempt_initially(harness):
    resp = _post(harness.client, harness.editor_headers, _base_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING_HUMAN_REVIEW"
    assert body["delivery_id"] is None

    db = harness.SessionLocal()
    try:
        assert db.query(DeliveryAttempt).count() == 0
        versions = db.query(InvoiceDraftVersion).filter_by(generated_invoice_id=body["invoice_id"]).all()
        assert len(versions) == 1
        assert versions[0].creation_reason == "INITIAL_GENERATION"
    finally:
        db.close()


def test_unauthorized_role_cannot_approve(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-unauth"))
    invoice_id = draft.json()["invoice_id"]

    # An editor (not an approver/admin) cannot approve.
    resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=harness.editor_headers
    )
    assert resp.status_code == 403

    # Nor can a plain viewer.
    resp2 = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=harness.viewer_headers
    )
    assert resp2.status_code == 403


def test_unauthorized_role_cannot_edit_draft(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-unauth-edit"))
    invoice_id = draft.json()["invoice_id"]

    resp = harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}",
        json=_base_payload(idempotency_key="ai-unauth-edit"),
        headers=harness.approver_headers,
    )
    assert resp.status_code == 403


def test_manual_edit_creates_new_immutable_version_and_prior_is_frozen(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-version"))
    invoice_id = draft.json()["invoice_id"]

    updated_payload = _base_payload(idempotency_key="ai-version")
    updated_payload["items"][0]["quantity"] = 2
    updated_payload["payment_or_order_details"]["subtotal"] = 2000.00
    updated_payload["payment_or_order_details"]["tax_total"] = 360.00
    updated_payload["payment_or_order_details"]["grand_total"] = 2360.00

    edit = harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}", json=updated_payload, headers=harness.editor_headers
    )
    assert edit.status_code == 200
    assert edit.json()["current_version_number"] == 2

    versions = harness.client.get(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/versions", headers=harness.editor_headers
    ).json()["versions"]
    assert len(versions) == 2
    assert versions[0]["is_current"] is False
    assert versions[1]["is_current"] is True

    v1 = harness.client.get(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/versions/1", headers=harness.editor_headers
    ).json()
    # Version 1's own snapshot is untouched by the version-2 edit.
    assert float(v1["invoice_data_snapshot"]["items"][0]["quantity"]) == 1


def test_ai_proposal_does_not_change_draft_until_applied(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-proposal-1"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "change the description"},
        headers=harness.editor_headers,
    )
    assert proposal_resp.status_code == 201
    proposal_id = proposal_resp.json()["proposal_id"]

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one()
        assert gi.current_version_number == 1  # unchanged — nothing applied yet
    finally:
        db.close()

    proposal = harness.client.get(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals/{proposal_id}",
        headers=harness.editor_headers,
    ).json()
    assert proposal["status"] in {"GENERATED", "INVALID", "FAILED"}


def test_ai_proposal_touching_protected_field_is_rejected(harness, monkeypatch):
    from app.workflows import generated_invoice_workflow as giw

    class _BadProvider:
        name = "bad"

        def generate_edit_proposal(self, *, system_prompt, context):
            return {
                "proposal_status": "PROPOSAL_READY",
                "base_draft_version_number": context["base_draft_version_number"],
                "instruction_summary": "attempt to change invoice number",
                "requires_clarification": False,
                "clarification_question": None,
                "requires_recalculation": False,
                "requires_tax_validation": False,
                "proposed_changes": [
                    {
                        "path": "invoice_number", "operation": "replace", "current_value": None,
                        "proposed_value": "HACKED/0001", "reason": "test", "change_type": "OTHER",
                    }
                ],
                "warnings": [],
                "reviewer_summary": "malicious proposal",
            }

        def generate_prefill(self, *, system_prompt, context):
            raise NotImplementedError

    monkeypatch.setattr(giw, "get_ai_provider", lambda settings: _BadProvider())

    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-protected"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "change the invoice number"},
        headers=harness.editor_headers,
    )
    assert proposal_resp.status_code == 201
    assert proposal_resp.json()["status"] == "INVALID"

    # Confirm an INVALID proposal can never be applied.
    apply_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals/{proposal_resp.json()['proposal_id']}/apply",
        headers=harness.editor_headers,
    )
    assert apply_resp.status_code == 409


def test_stale_ai_proposal_cannot_be_applied(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-stale"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "make the notes more formal"},
        headers=harness.editor_headers,
    )
    proposal_id = proposal_resp.json()["proposal_id"]

    # Someone else edits the draft in the meantime, advancing its version.
    harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}",
        json=_base_payload(idempotency_key="ai-stale", notes="edited out from under the proposal"),
        headers=harness.editor_headers,
    )

    apply_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals/{proposal_id}/apply",
        headers=harness.editor_headers,
    )
    assert apply_resp.status_code == 409


def test_applying_valid_proposal_creates_new_version_and_does_not_send(harness, monkeypatch):
    from app.workflows import generated_invoice_workflow as giw

    class _WordingProvider:
        name = "wording"

        def generate_edit_proposal(self, *, system_prompt, context):
            return {
                "proposal_status": "PROPOSAL_READY",
                "base_draft_version_number": context["base_draft_version_number"],
                "instruction_summary": "reword notes",
                "requires_clarification": False,
                "clarification_question": None,
                "requires_recalculation": False,
                "requires_tax_validation": False,
                "proposed_changes": [
                    {
                        "path": "notes", "operation": "replace", "current_value": None,
                        "proposed_value": "Thank you for your business.", "reason": "more formal wording",
                        "change_type": "WORDING",
                    }
                ],
                "warnings": [],
                "reviewer_summary": "Reworded the notes field only.",
            }

        def generate_prefill(self, *, system_prompt, context):
            raise NotImplementedError

    monkeypatch.setattr(giw, "get_ai_provider", lambda settings: _WordingProvider())

    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-apply-ok"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "make the notes more formal"},
        headers=harness.editor_headers,
    )
    proposal_id = proposal_resp.json()["proposal_id"]
    assert proposal_resp.json()["status"] == "GENERATED"

    apply_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals/{proposal_id}/apply",
        headers=harness.editor_headers,
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["current_version_number"] == 2
    assert apply_resp.json()["status"] == "PENDING_HUMAN_REVIEW"
    assert apply_resp.json()["delivery_id"] is None  # never sent by an AI-applied edit

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one()
        assert gi.notes == "Thank you for your business."
        proposal = db.query(InvoiceEditProposal).filter_by(id=proposal_id).one()
        assert proposal.status == "APPLIED"
        assert db.query(DeliveryAttempt).count() == 0
    finally:
        db.close()


def test_finalized_invoice_cannot_be_edited_or_reapproved(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-finalized"))
    invoice_id = draft.json()["invoice_id"]
    approve = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=harness.approver_headers
    )
    assert approve.status_code == 200

    edit_resp = harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}",
        json=_base_payload(idempotency_key="ai-finalized"),
        headers=harness.editor_headers,
    )
    assert edit_resp.status_code == 409

    reapprove = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=harness.approver_headers
    )
    assert reapprove.status_code == 409


def test_rejected_invoice_cannot_be_approved_or_delivered(harness):
    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-rejected"))
    invoice_id = draft.json()["invoice_id"]

    reject = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/reject",
        json={"reason": "customer requested cancellation of the order"},
        headers=harness.approver_headers,
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "REJECTED"

    approve = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=harness.approver_headers
    )
    assert approve.status_code == 409

    db = harness.SessionLocal()
    try:
        assert db.query(DeliveryAttempt).count() == 0
    finally:
        db.close()


def test_ai_provider_interface_has_no_delivery_or_approval_methods():
    from app.services.ai.base import AIProvider

    dangerous_names = {
        "approve", "reject", "send", "send_email", "send_whatsapp", "finalize",
        "delete", "create_delivery", "reserve_invoice_number",
    }
    exposed = {name for name in dir(AIProvider) if not name.startswith("_")}
    assert exposed & dangerous_names == set()
    assert exposed == {"generate_edit_proposal", "generate_prefill"}


def test_malformed_ai_output_is_marked_failed_not_silently_trusted(harness, monkeypatch):
    from app.workflows import generated_invoice_workflow as giw

    class _BrokenProvider:
        name = "broken"

        def generate_edit_proposal(self, *, system_prompt, context):
            return {"not": "a valid schema"}

        def generate_prefill(self, *, system_prompt, context):
            raise NotImplementedError

    monkeypatch.setattr(giw, "get_ai_provider", lambda settings: _BrokenProvider())

    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-malformed"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "do anything"},
        headers=harness.editor_headers,
    )
    assert proposal_resp.status_code == 201
    assert proposal_resp.json()["status"] == "FAILED"


def test_ai_edit_disabled_without_api_key_returns_503(harness, monkeypatch):
    harness.settings.ai_api_key = None

    draft = _post(harness.client, harness.editor_headers, _base_payload(idempotency_key="ai-disabled"))
    invoice_id = draft.json()["invoice_id"]

    proposal_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/ai-edit-proposals",
        json={"instruction": "anything"},
        headers=harness.editor_headers,
    )
    assert proposal_resp.status_code == 503
