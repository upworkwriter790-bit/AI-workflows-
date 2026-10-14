from __future__ import annotations

import uuid
from typing import Any

from app.services.operations.base import OperationsAdapter


class MockOperationsAdapter(OperationsAdapter):
    def __init__(self) -> None:
        self.notifications: list[dict[str, Any]] = []

    def notify_product_access_required(self, payload: dict[str, Any]) -> str:
        reference = f"MOCK-OPS-{uuid.uuid4().hex[:10]}"
        self.notifications.append({"reference": reference, "payload": payload})
        return reference
