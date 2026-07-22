"""
Central orchestrator / intent router.

`orchestrator.py` deliberately does NOT auto-chain agents end-to-end (see
its module docstring) -- but the product still needs a single front door: a
user should be able to type "help me find backend intern roles at Stripe"
into one box and have the system figure out which of the five specialist
agents handles that, instead of memorizing five CLI subcommands / five API
routes.

This module is that front door. It does two things, in order:

  1. classify() -- one small, cheap LLM call (config.ROUTER_MODEL) that
     reads the user's free-text request and returns which agent should
     handle it plus whatever parameters it can confidently extract from
     the text itself. It never invents values for fields it can't find --
     matching the guardrails philosophy used everywhere else in this repo,
     it reports them as `missing` instead.
  2. route_and_run() -- validates that every REQUIRED field for the chosen
     agent is present (from extraction + any explicit overrides the caller
     supplied), and only then dispatches to that agent's run(). If required
     fields are still missing, it returns a `needs_input` result instead of
     guessing or fabricating -- the caller (API/frontend) is expected to
     prompt the user for exactly those fields and re-submit.

This is the piece referenced by the PRD as "the orchestrator routes/
delegates tasks to the correct agents."
"""
import json
import logging
import re
import time

from . import state, config, execution_log
from .client import AgentClient
from .agents import profile_agent, content_agent, job_agent, resume_agent, outreach_agent

logger = logging.getLogger("linkedin_agent.router")

# Required vs optional parameters per agent -- used both to validate
# extraction results and to tell the frontend what to render as a form.
AGENT_SPECS = {
    "profile": {
        "module": profile_agent,
        "description": "Audits/optimizes a LinkedIn profile against a target role.",
        "required": ["profile_text", "target_role"],
        "optional": ["reference_profiles"],
    },
    "content": {
        "module": content_agent,
        "description": "Builds a content + networking/recruiter-targeting strategy. Requires a profile audit to already be on file.",
        "required": [],
        "optional": ["target_companies", "prior_post_performance"],
    },
    "jobs": {
        "module": job_agent,
        "description": "Searches for live job openings and early hiring signals.",
        "required": [],
        "optional": ["target_role", "geography", "experience_level", "target_companies", "active_only"],
    },
    "resume": {
        "module": resume_agent,
        "description": "Tailors a resume/application to one specific job listing and logs it to the pipeline tracker.",
        "required": ["master_resume_text", "company", "role", "location", "job_description"],
        "optional": ["channel", "used_referral", "log_to_pipeline"],
    },
    "outreach": {
        "module": outreach_agent,
        "description": "Drafts cold/warm outreach messages to a specific named recruiter/hiring manager.",
        "required": ["company", "target_person", "role"],
        "optional": ["resume_summary", "relationship_warmth", "referral_available"],
    },
    "status": {
        "module": None,
        "description": "Shows the unified cross-agent status view (profile, pipeline, outreach, open handoffs). Takes no parameters.",
        "required": [],
        "optional": [],
    },
}

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

ROUTER_SYSTEM_PROMPT = """You are the routing layer in front of five specialist LinkedIn career-copilot agents. You do not do any of the agents' actual work yourself -- you only decide which ONE agent should handle a user's request and extract whatever parameters you can find explicitly stated in their message.

The agents:
- profile: audits/optimizes a LinkedIn profile. Needs profile_text (the actual current profile content) and target_role.
- content: builds a content/networking strategy. Optional target_companies, prior_post_performance.
- jobs: searches for live job openings + early signals. Optional target_role, geography, experience_level, target_companies, active_only.
- resume: tailors a resume to one job listing, logs it to the pipeline. Needs master_resume_text, company, role, location, job_description.
- outreach: drafts outreach messages to a specific named person. Needs company, target_person, role.
- status: shows the cross-agent status dashboard. No parameters.

Respond with STRICT JSON only, no prose, no markdown fences, in exactly this shape:
{"agent": "<one of profile|content|jobs|resume|outreach|status>", "params": {<only fields you found explicitly and confidently in the user's message>}, "reasoning": "<one sentence>"}

Rules:
- NEVER invent or guess a value for a parameter the user did not actually provide (no fabricated company names, resume text, job descriptions, etc.) -- omit the key entirely if it's not present in the message.
- If the request is ambiguous between two agents, pick the one whose required fields are best supported by the message.
- boolean-looking fields (active_only, used_referral, referral_available) should be true/false only if explicitly implied.
"""


def classify(client: AgentClient, task_text: str) -> dict:
    text, _, _ = client.call(
        ROUTER_SYSTEM_PROMPT, task_text,
        use_web_search=False, max_tokens=512, model=config.ROUTER_MODEL,
    )
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError(f"Router did not return parseable JSON: {text!r}")
    parsed = json.loads(match.group(0))
    agent = parsed.get("agent")
    if agent not in AGENT_SPECS:
        raise ValueError(f"Router chose an unknown agent: {agent!r}")
    parsed.setdefault("params", {})
    return parsed


def route_and_run(client: AgentClient, task_text: str, overrides: dict = None) -> dict:
    """
    Full orchestration entrypoint: classify the free-text task, merge in any
    explicit overrides the caller already knows (e.g. from a form the user
    filled in), and either execute the matched agent or report exactly what
    input is still missing.
    """
    overrides = overrides or {}
    classification = classify(client, task_text)
    agent_name = classification["agent"]
    spec = AGENT_SPECS[agent_name]

    params = {**classification.get("params", {}), **overrides}
    missing = [f for f in spec["required"] if not params.get(f)]

    logger.info("router.route agent=%s missing=%s", agent_name, missing)

    if missing:
        return {
            "status": "needs_input",
            "agent": agent_name,
            "description": spec["description"],
            "extracted_params": params,
            "missing": missing,
            "reasoning": classification.get("reasoning", ""),
        }

    result = execute_agent(client, agent_name, params, source="orchestrator")
    return {
        "status": "completed",
        "agent": agent_name,
        "reasoning": classification.get("reasoning", ""),
        "result": result,
    }


def execute_agent(client: AgentClient, agent_name: str, params: dict, source: str = "direct") -> dict:
    """Direct dispatch by agent name + kwargs -- used both by route_and_run()
    and by the API's per-agent endpoints so there is exactly one code path
    that actually invokes agent modules. Every call is recorded to the
    execution log so the frontend can show a live run history."""
    if agent_name not in AGENT_SPECS:
        raise ValueError(f"Unknown agent: {agent_name!r}")

    entry = execution_log.start(agent_name, source, input_summary=json.dumps(params, default=str))
    started = time.monotonic()
    try:
        if agent_name == "status":
            from . import orchestrator
            result = {"report": orchestrator.status_report(), "sources": [], "path": None, "handoff": None}
        else:
            spec = AGENT_SPECS[agent_name]
            allowed = set(spec["required"]) | set(spec["optional"])
            call_kwargs = {k: v for k, v in params.items() if k in allowed}
            result = spec["module"].run(client, **call_kwargs)
    except Exception as e:
        execution_log.finish(entry["id"], ok=False, error=str(e), started_monotonic=started)
        raise
    execution_log.finish(entry["id"], ok=True, started_monotonic=started)
    return result
