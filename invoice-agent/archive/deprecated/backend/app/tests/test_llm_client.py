from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.document_review.llm_client import (
    ExtractionError,
    _extract_json_object,
    get_llm_provider,
    load_system_prompt,
)


def test_load_system_prompt_substitutes_company_name():
    prompt = load_system_prompt("Acme Pvt Ltd")
    assert "Acme Pvt Ltd" in prompt
    assert "{company_legal_name}" not in prompt


def test_load_system_prompt_flags_missing_company_name():
    prompt = load_system_prompt(None)
    assert "NOT CONFIGURED" in prompt


def test_get_llm_provider_raises_without_api_key():
    settings = Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=None)
    with pytest.raises(RuntimeError):
        get_llm_provider(settings)


def test_get_llm_provider_raises_on_unknown_provider():
    settings = Settings(LLM_PROVIDER="not-a-real-provider")
    with pytest.raises(ValueError):
        get_llm_provider(settings)


def test_get_llm_provider_selects_anthropic_when_key_present():
    settings = Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-test")
    provider = get_llm_provider(settings)
    assert provider.name == "anthropic"


def test_extract_json_object_rejects_non_json():
    with pytest.raises(ExtractionError):
        _extract_json_object("sorry, I can't help with that")


def test_extract_json_object_parses_embedded_json():
    text = 'Here you go:\n{"a": 1, "b": [1, 2]}\nthanks'
    parsed = _extract_json_object(text)
    assert parsed == {"a": 1, "b": [1, 2]}
