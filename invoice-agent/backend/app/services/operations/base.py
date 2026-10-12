"""Operations notification adapter interface (Slack/Teams/email/CRM-task).
Per spec §15: triggered only after ERP sync succeeds; the response
(approve/hold/reject access) is a separate controlled action, never taken
by the LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OperationsAdapter(ABC):
    @abstractmethod
    def notify_product_access_required(self, payload: dict[str, Any]) -> str:
        """Sends the PRODUCT_ACCESS_REQUEST-style payload. Returns a
        provider-side reference (message ts, task id, etc.).
        """
        ...
