"""Product-access adapter interface. Per spec §15: only called after an
explicit APPROVE_AND_ENABLE_ACCESS action by a human/Operations system —
the LLM is never granted permission to call this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProductAccessAdapter(ABC):
    @abstractmethod
    def enable_access(self, customer_id: str, product_ids: list[str]) -> dict:
        """Returns {'status': 'ACTIVATED'|'FAILED', 'details': {...}}."""
        ...
