import importlib

import pytest


def _reload_config():
    from linkedin_agent import config
    importlib.reload(config)
    return config


def test_defaults_to_anthropic_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    config = _reload_config()
    assert config.LLM_PROVIDER == "anthropic"
    assert config.DEFAULT_MODEL == "claude-sonnet-5"


def test_openrouter_provider_picks_openrouter_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    config = _reload_config()
    try:
        assert config.LLM_PROVIDER == "openrouter"
        assert config.DEFAULT_MODEL == "anthropic/claude-3.5-sonnet"
        config.require_api_key()  # should not raise -- key is set
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        _reload_config()


def test_openai_provider_without_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = _reload_config()
    try:
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            config.require_api_key()
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        _reload_config()


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    config = _reload_config()
    try:
        with pytest.raises(RuntimeError, match="not recognized"):
            config.require_api_key()
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        _reload_config()


def test_explicit_model_override_wins_over_provider_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LINKEDIN_AGENT_MODEL", "openai/gpt-4o")
    config = _reload_config()
    try:
        assert config.DEFAULT_MODEL == "openai/gpt-4o"
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LINKEDIN_AGENT_MODEL", raising=False)
        _reload_config()
