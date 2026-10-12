from __future__ import annotations

import uuid
from typing import Any

from app.services.erp.base import ERPAdapter


class MockERPAdapter(ERPAdapter):
    def __init__(self) -> None:
        self._by_external_reference: dict[str, dict[str, Any]] = {}
        self._by_erp_id: dict[str, dict[str, Any]] = {}

    def create_invoice_draft(
        self, invoice_payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        external_reference = invoice_payload.get("external_reference", idempotency_key)
        existing = self._by_external_reference.get(external_reference)
        if existing is not None:
            return existing

        erp_invoice_id = f"MOCK-ERP-{uuid.uuid4().hex[:10].upper()}"
        record = {
            "erp_invoice_id": erp_invoice_id,
            "status": "DRAFT",
            "raw_response": {"echo": invoice_payload},
        }
        self._by_external_reference[external_reference] = record
        self._by_erp_id[erp_invoice_id] = record
        return record

    def get_invoice_by_external_reference(self, external_reference: str) -> dict[str, Any] | None:
        return self._by_external_reference.get(external_reference)

    def update_invoice_status(self, erp_invoice_id: str, status: str) -> None:
        if erp_invoice_id not in self._by_erp_id:
            raise LookupError(f"mock ERP has no invoice {erp_invoice_id}")
        self._by_erp_id[erp_invoice_id]["status"] = status

    def attach_invoice_document(self, erp_invoice_id: str, pdf_storage_key: str) -> None:
        if erp_invoice_id not in self._by_erp_id:
            raise LookupError(f"mock ERP has no invoice {erp_invoice_id}")
        self._by_erp_id[erp_invoice_id]["pdf_storage_key"] = pdf_storage_key

    def get_sync_result(self, job_or_invoice_id: str) -> dict[str, Any]:
        record = self._by_erp_id.get(job_or_invoice_id)
        if record is None:
            raise LookupError(f"mock ERP has no invoice {job_or_invoice_id}")
        return record
