"""Multi-provider LLM client for Use Case 2 document extraction.

Every provider implements the same `extract()` contract and is handed the
exact same system prompt + JSON schema (see app/prompts/ and
app/schemas/invoice_extraction_schema.py) — so switching LLM_PROVIDER never
changes extraction behavior beyond the underlying model's own accuracy.

Hard boundary enforced by design, not just prompt wording: this module only
ever returns a parsed dict to the caller. It never executes a tool, never
touches the database, and never has credentials for CRM/ERP/email. The
decision engine (app/services/document_review/decision_engine.py, built in
Phase 4) is what turns this dict + backend validation results into
ACCEPT/HOLD_FOR_REVIEW/REJECT — the LLM's `suggested_recommendation` field is
read as a recommendation only, never applied directly.
"""

from __future__ import annotations

import base64
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.schemas.invoice_extraction_schema import INVOICE_EXTRACTION_JSON_SCHEMA, SCHEMA_VERSION

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "invoice_document_review_system.txt"


def load_system_prompt(company_legal_name: str | None) -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    name = company_legal_name or "[COMPANY LEGAL NAME NOT CONFIGURED]"
    return raw.format(company_legal_name=name)


class ExtractionError(RuntimeError):
    """Raised when a provider returns something that isn't valid JSON
    matching the expected shape. Callers must treat this as HOLD_FOR_REVIEW
    material, never as grounds to invent a value.
    """


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        system_prompt: str,
    ) -> dict[str, Any]:
        """Returns a dict matching INVOICE_EXTRACTION_JSON_SCHEMA."""
        ...


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ExtractionError(f"model returned non-JSON output: {text[:200]!r}")
    return json.loads(text[start : end + 1])


_SCHEMA_INSTRUCTION = (
    "\n\nReturn exactly one JSON object matching this JSON Schema and nothing "
    "else (no markdown fences, no prose before or after):\n"
    + json.dumps(INVOICE_EXTRACTION_JSON_SCHEMA)
)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or "claude-opus-4-8"

    def extract(self, *, document_bytes: bytes, mime_type: str, system_prompt: str) -> dict[str, Any]:
        b64 = base64.b64encode(document_bytes).decode("ascii")
        content: list[dict[str, Any]] = []
        if mime_type == "application/pdf":
            content.append(
                {"type": "document", "source": {"type": "base64", "media_type": mime_type, "data": b64}}
            )
        else:
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}}
            )
        content.append({"type": "text", "text": "Extract this document into the required JSON schema now."})

        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt + _SCHEMA_INSTRUCTION,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _extract_json_object(text)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str | None) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model or "gpt-5"

    def extract(self, *, document_bytes: bytes, mime_type: str, system_prompt: str) -> dict[str, Any]:
        b64 = base64.b64encode(document_bytes).decode("ascii")
        if mime_type == "application/pdf":
            file_part: dict[str, Any] = {
                "type": "input_file",
                "filename": "document.pdf",
                "file_data": f"data:{mime_type};base64,{b64}",
            }
        else:
            file_part = {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"}

        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt + _SCHEMA_INSTRUCTION},
                {
                    "role": "user",
                    "content": [
                        file_part,
                        {"type": "input_text", "text": "Extract this document into the required JSON schema now."},
                    ],
                },
            ],
        )
        return _extract_json_object(response.output_text)


class OpenRouterProvider(LLMProvider):
    """OpenAI-compatible chat API. Model/vision support for raw PDFs varies
    by the specific model routed to — for best results pick a model known to
    accept PDF or image input (check openrouter.ai/models) and, for scanned
    documents, prefer passing pre-rasterized page images over raw PDF bytes.
    """

    name = "openrouter"

    def __init__(self, api_key: str, model: str | None) -> None:
        import httpx

        self._api_key = api_key
        self._model = model or "anthropic/claude-opus-4.8"
        self._client = httpx.Client(base_url="https://openrouter.ai/api/v1", timeout=120)

    def extract(self, *, document_bytes: bytes, mime_type: str, system_prompt: str) -> dict[str, Any]:
        b64 = base64.b64encode(document_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        content_part = (
            {"type": "image_url", "image_url": {"url": data_url}}
            if mime_type != "application/pdf"
            else {"type": "file", "file": {"filename": "document.pdf", "file_data": data_url}}
        )
        resp = self._client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt + _SCHEMA_INSTRUCTION},
                    {
                        "role": "user",
                        "content": [
                            content_part,
                            {"type": "text", "text": "Extract this document into the required JSON schema now."},
                        ],
                    },
                ],
            },
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _extract_json_object(text)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str | None) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._model_obj = genai.GenerativeModel(model or "gemini-2.5-pro")

    def extract(self, *, document_bytes: bytes, mime_type: str, system_prompt: str) -> dict[str, Any]:
        response = self._model_obj.generate_content(
            [
                system_prompt + _SCHEMA_INSTRUCTION,
                {"mime_type": mime_type, "data": document_bytes},
                "Extract this document into the required JSON schema now.",
            ]
        )
        return _extract_json_object(response.text)


class SarvamProvider(LLMProvider):
    """Sarvam's multimodal/document-input support should be re-verified
    against current Sarvam API docs before production use — this adapter
    sends the document as a base64 data URL on a chat-completion-style
    endpoint, matching Sarvam's OpenAI-compatible chat API shape at the time
    this was written. If their current API lacks direct document/image
    input, route documents through the OCR pipeline (see
    app/services/document_review/ocr_fallback.py, Phase 4) to get plain text
    first, then send that text instead of raw bytes.
    """

    name = "sarvam"

    def __init__(self, api_key: str, model: str | None) -> None:
        import httpx

        self._api_key = api_key
        self._model = model or "sarvam-m"
        self._client = httpx.Client(base_url="https://api.sarvam.ai/v1", timeout=120)

    def extract(self, *, document_bytes: bytes, mime_type: str, system_prompt: str) -> dict[str, Any]:
        b64 = base64.b64encode(document_bytes).decode("ascii")
        resp = self._client.post(
            "/chat/completions",
            headers={"api-subscription-key": self._api_key},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt + _SCHEMA_INSTRUCTION},
                    {
                        "role": "user",
                        "content": (
                            "Extract the attached document into the required JSON "
                            f"schema now. document_base64 ({mime_type}): {b64}"
                        ),
                    },
                ],
            },
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _extract_json_object(text)


def get_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(settings.anthropic_api_key, settings.llm_model)
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
        return OpenAIProvider(settings.openai_api_key, settings.llm_model)
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set")
        return OpenRouterProvider(settings.openrouter_api_key, settings.llm_model)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set")
        return GeminiProvider(settings.gemini_api_key, settings.llm_model)
    if provider == "sarvam":
        if not settings.sarvam_api_key:
            raise RuntimeError("LLM_PROVIDER=sarvam but SARVAM_API_KEY is not set")
        return SarvamProvider(settings.sarvam_api_key, settings.llm_model)
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}")


__all__ = [
    "SCHEMA_VERSION",
    "ExtractionError",
    "LLMProvider",
    "get_llm_provider",
    "load_system_prompt",
]
