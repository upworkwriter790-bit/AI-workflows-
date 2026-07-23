from .. import prompts, state, handoff, guardrails
from ..client import AgentClient

AGENT_NAME = "outreach_agent"


def run(client: AgentClient, company: str, target_person: str, role: str,
        resume_summary: str = None, relationship_warmth: str = "cold",
        referral_available: bool = False) -> dict:
    user_message = f"""COMPANY: {company}
TARGET PERSON: {target_person}
ROLE: {role}
KNOWN RELATIONSHIP WARMTH (user-reported): {relationship_warmth}
REFERRAL PATH AVAILABLE: {referral_available}
"""
    if resume_summary:
        user_message += f"\nTAILORED RESUME/APPLICATION SUMMARY FOR THIS ROLE:\n{resume_summary}\n"

    user_message += "\nUse web search to research the target person/company before drafting anything."

    text, sources, _ = client.call(prompts.OUTREACH_AGENT_SYSTEM, user_message,
                                     use_web_search=True, max_search_uses=6)

    warnings = guardrails.check_outreach_message(text)
    text_with_warnings = text + guardrails.format_warnings(warnings)

    note = handoff.extract_handoff(text)
    handoff.log_handoff(AGENT_NAME, note)

    path = state.save_markdown_report(AGENT_NAME, text_with_warnings)

    outreach_log = state.load("outreach_log.json", [])
    outreach_log.append({
        "company": company,
        "target_person": target_person,
        "role": role,
        "date": state.now_iso(),
        "report_path": path,
        "status": "drafted",  # drafted -> sent -> responded -> closed (user updates manually)
    })
    state.save("outreach_log.json", outreach_log)

    return {"report": text_with_warnings, "sources": sources, "path": path,
            "handoff": note, "warnings": warnings}


def update_status(company: str, target_person: str, new_status: str) -> bool:
    """new_status: sent | responded_positive | responded_negative | no_response | closed"""
    outreach_log = state.load("outreach_log.json", [])
    updated = False
    for entry in outreach_log:
        if entry["company"] == company and entry["target_person"] == target_person:
            entry["status"] = new_status
            entry["status_updated_at"] = state.now_iso()
            updated = True
    if updated:
        state.save("outreach_log.json", outreach_log)
    return updated
