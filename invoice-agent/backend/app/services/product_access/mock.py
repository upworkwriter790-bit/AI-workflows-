from __future__ import annotations

from app.services.product_access.base import ProductAccessAdapter


class MockProductAccessAdapter(ProductAccessAdapter):
    def __init__(self) -> None:
        self.activations: list[dict] = []

    def enable_access(self, customer_id: str, product_ids: list[str]) -> dict:
        record = {"customer_id": customer_id, "product_ids": product_ids, "status": "ACTIVATED"}
        self.activations.append(record)
        return {"status": "ACTIVATED", "details": record}
