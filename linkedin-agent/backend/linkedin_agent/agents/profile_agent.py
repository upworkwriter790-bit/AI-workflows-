from .. import prompts, state, handoff
from ..client import AgentClient

AGENT_NAME = "profile_agent"


def run(client: AgentClient, profile_text: str, target_role: str,
        reference_profiles: str = None) -> dict:
    user_message = f"""TARGET ROLE/CONTEXT: {target_role}

CURRENT LINKEDIN PROFILE CONTENT:
{profile_text}
"""
    if reference_profiles:
        user_message += f"\nREFERENCE/BENCHMARK PROFILES SUPPLIED BY USER:\n{reference_profiles}\n"
    else:
        user_message += "\nNo reference profiles supplied -- benchmark against general best-practice patterns for this role/industry and say so explicitly.\n"

    text, sources, _ = client.call(prompts.PROFILE_AGENT_SYSTEM, user_message, use_web_search=False)

    note = handoff.extract_handoff(text)
    handoff.log_handoff(AGENT_NAME, note)

    path = state.save_markdown_report(AGENT_NAME, text)

    # persist for downstream agents (Content, Job Discovery use target_role +
    # keyword context; Resume agent uses this as the "profile strengths" input)
    profile_state = state.load("profile.json", {})
    profile_state.update({
        "target_role": target_role,
        "raw_profile_text": profile_text,
        "audit_report_md": text,
        "handoff_note": note,
        "updated_at": state.now_iso(),
    })
    state.save("profile.json", profile_state)

    return {"report": text, "sources": sources, "path": path, "handoff": note}
