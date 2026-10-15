"""Real Anthropic-backed AI provider. Uses forced tool-use (tool_choice)
rather than free-form text so the model's only possible output is a
single call to a tool whose input_schema is the exact JSON contract
(AIEditProposalOutput / AIPrefillOutput) — this is the "strict
structured output" the spec calls for; there is no free-text parsing of
a financial record anywhere in this path.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from app.services.ai.base import AIProvider

_EDIT_PROPOSAL_TOOL_NAME = "submit_edit_proposal"
_PREFILL_TOOL_NAME = "submit_prefill_result"


class AnthropicAIProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def generate_edit_proposal(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        from app.schemas.ai_edit_proposal import AIEditProposalOutput

        return self._call_with_tool(
            system_prompt=system_prompt,
            user_content=json.dumps(context),
            tool_name=_EDIT_PROPOSAL_TOOL_NAME,
            schema=AIEditProposalOutput.model_json_schema(),
        )

    def generate_prefill(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        from app.schemas.ai_prefill_output import AIPrefillOutput

        return self._call_with_tool(
            system_prompt=system_prompt,
            user_content=json.dumps(context),
            tool_name=_PREFILL_TOOL_NAME,
            schema=AIPrefillOutput.model_json_schema(),
        )

    def _call_with_tool(
        self, *, system_prompt: str, user_content: str, tool_name: str, schema: dict
    ) -> dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system_prompt,
            tools=[{"name": tool_name, "description": "Submit the structured result.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_content}],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        raise RuntimeError("model did not return a tool_use block")
