"""In-memory mock CRM adapter. Used whenever CRM_PROVIDER=mock (the default).
Never calls a network. Lets the rest of the system be built and tested
before real CRM credentials exist, and gives Phase 2+ a safe target for the
full workflow's integration tests.
"""

from __future__ import annotations

from typing import Any

from app.services.crm.base import CRMAdapter


class MockCRMAdapter(CRMAdapter):
    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._customers: dict[str, dict[str, Any]] = {}
        self._invoice_status_updates: list[dict[str, Any]] = []
        self._notes: list[dict[str, Any]] = []
        self._operations_tasks: list[dict[str, Any]] = []
        self._access_updates: list[dict[str, Any]] = []
        self._task_counter = 0

    def seed_order(self, order_id: str, payload: dict[str, Any]) -> None:
        self._orders[order_id] = payload

    def seed_customer(self, customer_id: str, payload: dict[str, Any]) -> None:
        self._customers[customer_id] = payload

    def verify_order_paid(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        return bool(order) and order.get("payment_status") == "paid"

    def get_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self._orders:
            raise LookupError(f"mock CRM has no order {order_id}")
        return self._orders[order_id]

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        if customer_id not in self._customers:
            raise LookupError(f"mock CRM has no customer {customer_id}")
        return self._customers[customer_id]

    def update_invoice_status(self, order_id: str, status: str, details: dict[str, Any]) -> None:
        self._invoice_status_updates.append({"order_id": order_id, "status": status, **details})

    def attach_invoice_pdf(self, order_id: str, secure_pdf_url: str) -> None:
        self._invoice_status_updates.append({"order_id": order_id, "pdf_url": secure_pdf_url})

    def create_internal_crm_note(self, order_id: str, note: str) -> None:
        self._notes.append({"order_id": order_id, "note": note})

    def create_operations_task(
        self, customer_id: str, order_id: str, invoice_id: str, product_ids: list[str]
    ) -> str:
        self._task_counter += 1
        task_id = f"MOCK-OPS-TASK-{self._task_counter}"
        self._operations_tasks.append(
            {
                "task_id": task_id,
                "customer_id": customer_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "product_ids": product_ids,
            }
        )
        return task_id

    def update_product_access_status(
        self, customer_id: str, product_ids: list[str], status: str
    ) -> None:
        self._access_updates.append(
            {"customer_id": customer_id, "product_ids": product_ids, "status": status}
        )
