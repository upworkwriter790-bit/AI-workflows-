from .. import prompts, state, handoff
from ..client import AgentClient

AGENT_NAME = "content_agent"


def run(client: AgentClient, target_companies: str = None,
        prior_post_performance: str = None) -> dict:
    profile_state = state.load("profile.json", {})
    if not profile_state.get("audit_report_md"):
        raise RuntimeError(
            "No profile audit found. Run the Profile agent first -- "
            "the Content Agent needs the Profile Agent's handoff to build pillars."
        )

    content_log = state.load("content_log.json", {"pillars": [], "posts": [], "history": []})

    user_message = f"""HANDOFF FROM PROFILE AGENT:
Target role: {profile_state.get('target_role')}
Audit report:
{profile_state.get('audit_report_md')}
"""
    if target_companies:
        user_message += f"\nTARGET COMPANIES/RECRUITER TYPES: {target_companies}\n"
    if prior_post_performance:
        user_message += f"\nPRIOR POST PERFORMANCE DATA (this is a repeat cycle -- use the feedback loop step):\n{prior_post_performance}\n"
    elif content_log["posts"]:
        user_message += f"\nPRIOR CYCLE HISTORY ON FILE:\n{content_log['history'][-3:]}\n"
    else:
        user_message += "\nThis is the first content cycle -- no prior performance data yet.\n"

    text, sources, _ = client.call(prompts.CONTENT_AGENT_SYSTEM, user_message, use_web_search=True)

    note = handoff.extract_handoff(text)
    handoff.log_handoff(AGENT_NAME, note)

    path = state.save_markdown_report(AGENT_NAME, text)

    content_log["history"].append({
        "date": state.now_iso(),
        "report_path": path,
        "had_prior_performance_data": bool(prior_post_performance),
    })
    state.save("content_log.json", content_log)

    return {"report": text, "sources": sources, "path": path, "handoff": note}


def log_post_performance(post_idea: str, performance: dict) -> None:
    """Call this after the user has actually posted and has real numbers,
    so the next content_agent.run() cycle can use the feedback loop."""
    content_log = state.load("content_log.json", {"pillars": [], "posts": [], "history": []})
    content_log["posts"].append({
        "idea": post_idea,
        "performance": performance,
        "logged_at": state.now_iso(),
    })
    state.save("content_log.json", content_log)
