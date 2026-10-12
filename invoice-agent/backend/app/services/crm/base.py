"""CRM adapter interface. A concrete adapter for a real CRM implements this
exact surface; the workflow layer (Phase 2+) only ever talks to this
interface, never to a specific CRM's SDK directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CRMAdapter(ABC):
    @abstractmethod
    def verify_order_paid(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_order(self, order_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_customer(self, customer_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def update_invoice_status(self, order_id: str, status: str, details: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def attach_invoice_pdf(self, order_id: str, secure_pdf_url: str) -> None:
        ...

    @abstractmethod
    def create_internal_crm_note(self, order_id: str, note: str) -> None:
        ...

    @abstractmethod
    def create_operations_task(
        self, customer_id: str, order_id: str, invoice_id: str, product_ids: list[str]
    ) -> str:
        """Returns a CRM task/reference ID."""
        ...

    @abstractmethod
    def update_product_access_status(
        self, customer_id: str, product_ids: list[str], status: str
    ) -> None:
        ...
