"""ERP adapter interface. Lets the organization swap ERPs later without
touching the invoice workflow. Per spec §13: search-before-create, draft
status first, save ERP's own ID, never silently overwrite a posted invoice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ERPAdapter(ABC):
    @abstractmethod
    def create_invoice_draft(
        self, invoice_payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        """Returns {'erp_invoice_id': str, 'status': str, 'raw_response': dict}."""
        ...

    @abstractmethod
    def get_invoice_by_external_reference(self, external_reference: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def update_invoice_status(self, erp_invoice_id: str, status: str) -> None:
        ...

    @abstractmethod
    def attach_invoice_document(self, erp_invoice_id: str, pdf_storage_key: str) -> None:
        ...

    @abstractmethod
    def get_sync_result(self, job_or_invoice_id: str) -> dict[str, Any]:
        ...
