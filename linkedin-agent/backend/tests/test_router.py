import pytest

from linkedin_agent import router
from linkedin_agent.client import AgentClient


class FakeClient:
    """Stands in for AgentClient without making any network calls.
    `responses` is a list consumed in order across successive .call()s,
    so a test can script router-classification then agent-execution."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def call(self, system_prompt, user_message, use_web_search=False,
              max_tokens=4096, max_search_uses=8, model=None):
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        text, sources = self._responses.pop(0)
        return text, sources, None


def test_classify_parses_router_json():
    client = FakeClient([
        ('{"agent": "jobs", "params": {"target_role": "Backend Intern", "geography": "remote"}, "reasoning": "user wants job listings"}', []),
    ])
    result = router.classify(client, "find me remote backend intern roles")
    assert result["agent"] == "jobs"
    assert result["params"]["target_role"] == "Backend Intern"


def test_classify_rejects_unknown_agent():
    client = FakeClient([
        ('{"agent": "not_a_real_agent", "params": {}, "reasoning": "bad"}', []),
    ])
    with pytest.raises(ValueError):
        router.classify(client, "do something weird")


def test_route_and_run_reports_missing_required_fields():
    client = FakeClient([
        ('{"agent": "resume", "params": {"company": "Stripe", "role": "Backend Intern"}, "reasoning": "tailor a resume"}', []),
    ])
    result = router.route_and_run(client, "tailor my resume for the Stripe backend intern role")
    assert result["status"] == "needs_input"
    assert result["agent"] == "resume"
    assert "master_resume_text" in result["missing"]
    assert "location" in result["missing"]
    assert "job_description" in result["missing"]


def test_route_and_run_executes_when_all_required_fields_present(monkeypatch):
    client = FakeClient([
        ('{"agent": "profile", "params": {"target_role": "Backend Intern"}, "reasoning": "profile audit request"}', []),
        ("### LinkedIn Optimization Report\n...\nHANDOFF: none -- no cross-agent gaps identified this cycle.", []),
    ])
    result = router.route_and_run(
        client, "review my linkedin profile",
        overrides={"profile_text": "Current headline: Student."},
    )
    assert result["status"] == "completed"
    assert result["agent"] == "profile"
    assert "LinkedIn Optimization Report" in result["result"]["report"]


def test_execute_agent_logs_to_execution_log():
    from linkedin_agent import execution_log
    client = FakeClient([
        ("### LinkedIn Optimization Report\nHANDOFF: none -- no cross-agent gaps identified this cycle.", []),
    ])
    router.execute_agent(client, "profile", {"profile_text": "x", "target_role": "Backend Intern"})
    recent = execution_log.recent(limit=5)
    assert recent[0]["agent"] == "profile"
    assert recent[0]["status"] == "success"
