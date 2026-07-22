import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test gets its own scratch data/output dirs and a fake API key,
    so tests never touch a developer's real ~/data or make network calls
    unless a test explicitly mocks/allows it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("LINKEDIN_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LINKEDIN_AGENT_OUTPUT_DIR", str(tmp_path / "outputs"))
    # config module reads env vars at import time, so reload it under the
    # patched environment for every test.
    import importlib
    from linkedin_agent import config
    importlib.reload(config)
    yield
    importlib.reload(config)
