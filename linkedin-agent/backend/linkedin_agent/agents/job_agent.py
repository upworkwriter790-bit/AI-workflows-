from .. import prompts, state, handoff, guardrails
from ..client import AgentClient

AGENT_NAME = "job_agent"


def run(client: AgentClient, target_role: str = None, geography: str = "remote",
        experience_level: str = "not specified", target_companies: str = None,
        active_only: bool = False) -> dict:
    profile_state = state.load("profile.json", {})
    role = target_role or profile_state.get("target_role")
    if not role:
        raise RuntimeError(
            "No target role given and none found in profile.json. "
            "Run the Profile agent first, or pass a role explicitly."
        )

    user_message = f"""SCOPE:
Target role(s): {role}
Geography scope: {geography}
Experience level / eligibility constraints: {experience_level}
Target companies (if any, prioritize these): {target_companies or 'none specified'}
Active openings only (skip early-signal scan): {active_only}

PROFILE STRENGTHS/KEYWORDS (for fit-scoring):
{profile_state.get('audit_report_md', 'No profile audit on file -- fit-score generically for this role.')}
"""

    text, sources, _ = client.call(prompts.JOB_DISCOVERY_AGENT_SYSTEM, user_message,
                                     use_web_search=True, max_search_uses=15)

    warnings = guardrails.check_job_report(text, had_sources=bool(sources))
    text_with_warnings = text + guardrails.format_warnings(warnings)

    note = handoff.extract_handoff(text)
    handoff.log_handoff(AGENT_NAME, note)

    path = state.save_markdown_report(AGENT_NAME, text_with_warnings)

    jobs_cache = state.load("jobs_cache.json", {"runs": []})
    jobs_cache["runs"].append({
        "date": state.now_iso(),
        "role": role,
        "geography": geography,
        "report_path": path,
        "num_sources": len(sources),
        "warnings": warnings,
    })
    state.save("jobs_cache.json", jobs_cache)

    return {"report": text_with_warnings, "sources": sources, "path": path,
            "handoff": note, "warnings": warnings}
