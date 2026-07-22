import pytest
from fastapi.testclient import TestClient

from linkedin_agent.client import AgentClient


@pytest.fixture
def fake_llm(monkeypatch):
    """Patches AgentClient.call at the class level so every API request in
    a test hits this canned response instead of the real Anthropic API --
    verifies the full HTTP -> router/agent -> response path without needing
    a live API key or network access."""
    script = {"responses": []}

    def fake_call(self, system_prompt, user_message, use_web_search=False,
                  max_tokens=4096, max_search_uses=8, model=None):
        text, sources = script["responses"].pop(0)
        return text, sources, None

    monkeypatch.setattr(AgentClient, "call", fake_call)
    return script


@pytest.fixture
def client():
    # Imported here (after conftest's isolated_state fixture has patched
    # env vars) so the app picks up the test data/output directories.
    from app.main import app
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["api_key_configured"] is True


def test_list_agents(client):
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"profile", "content", "jobs", "resume", "outreach", "status"}


def test_profile_endpoint_reaches_agent_and_returns_report(client, fake_llm):
    fake_llm["responses"].append((
        "### LinkedIn Optimization Report\n**Overall Profile Health Score:** 6/10\n"
        "HANDOFF: content_agent should build a content plan because the profile lacks a posting strategy.",
        [],
    ))
    resp = client.post("/api/agents/profile", json={
        "profile_text": "Headline: Student at State University.",
        "target_role": "Backend SDE Internship",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "LinkedIn Optimization Report" in body["report"]
    assert body["handoff"].startswith("content_agent should build a content plan")

    # Handoff should now be visible via the status/handoffs endpoints.
    handoffs = client.get("/api/handoffs").json()
    assert len(handoffs) == 1
    assert handoffs[0]["from_agent"] == "profile_agent"


def test_content_endpoint_requires_profile_first(client, fake_llm):
    resp = client.post("/api/agents/content", json={"target_companies": "Stripe"})
    assert resp.status_code == 400
    assert "profile" in resp.json()["detail"].lower()


def test_orchestrate_reports_needs_input_without_fabricating(client, fake_llm):
    fake_llm["responses"].append((
        '{"agent": "outreach", "params": {"company": "Stripe"}, "reasoning": "outreach request"}',
        [],
    ))
    resp = client.post("/api/orchestrate", json={"task": "help me message someone at Stripe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_input"
    assert body["agent"] == "outreach"
    assert "target_person" in body["missing"]
    assert "role" in body["missing"]


def test_orchestrate_executes_full_agent_when_fields_present(client, fake_llm):
    fake_llm["responses"].extend([
        ('{"agent": "outreach", "params": {"company": "Stripe", "target_person": "Jane Doe, EM"}, "reasoning": "outreach"}', []),
        ("### Outreach Plan -- Stripe / Jane Doe\nHANDOFF: none -- no cross-agent gaps identified this cycle.", []),
    ])
    resp = client.post("/api/orchestrate", json={
        "task": "draft outreach to Jane Doe at Stripe for the backend intern role",
        "overrides": {"role": "Backend Intern"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "Outreach Plan" in body["result"]["report"]


def test_pipeline_add_and_track_roundtrip(client):
    add_resp = client.post("/api/pipeline/add", json={
        "company": "Ramp", "role": "Backend Intern", "location": "NYC",
    })
    assert add_resp.status_code == 200
    entry_id = add_resp.json()["id"]

    track_resp = client.post("/api/pipeline/track", json={"id": entry_id, "stage": "Interview"})
    assert track_resp.status_code == 200
    assert track_resp.json()["entry"]["stage"] == "Interview"

    listing = client.get("/api/pipeline").json()
    assert listing["stats"]["Interview"] == 1


def test_missing_api_key_returns_400(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import importlib
    from linkedin_agent import config
    importlib.reload(config)
    resp = client.post("/api/agents/profile", json={"profile_text": "x", "target_role": "y"})
    assert resp.status_code == 400
    importlib.reload(config)
