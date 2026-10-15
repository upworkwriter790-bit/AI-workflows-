"""Provider interface for the two AI assistants (draft prefill, draft
edit proposal). Both assistants are read-only with respect to the
database and delivery/approval tooling — see app/services/ai/factory.py
and the prompt files under app/prompts/ for what they are and are not
allowed to do.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    name: str

    @abstractmethod
    def generate_edit_proposal(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Returns a dict matching AIEditProposalOutput's shape (raw,
        not yet validated — the caller validates it)."""

    @abstractmethod
    def generate_prefill(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Returns a dict matching AIPrefillOutput's shape (raw, not yet
        validated — the caller validates it)."""
