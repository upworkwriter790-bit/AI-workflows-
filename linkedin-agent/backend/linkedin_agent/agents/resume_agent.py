from .. import prompts, state, handoff, guardrails, pipeline
from ..client import AgentClient

AGENT_NAME = "resume_agent"


def run(client: AgentClient, master_resume_text: str, company: str, role: str,
        location: str, job_description: str, channel: str = "cold",
        used_referral: bool = False, log_to_pipeline: bool = True) -> dict:
    profile_state = state.load("profile.json", {})

    user_message = f"""COMPANY: {company}
ROLE: {role}
LOCATION: {location}
CHANNEL: {channel} (used_referral={used_referral})

JOB DESCRIPTION:
{job_description}

MASTER RESUME (do not fabricate anything not present here):
{master_resume_text}

PROFILE STRENGTHS/KEYWORDS FROM PROFILE AGENT (for consistency):
{profile_state.get('audit_report_md', 'none on file')}
"""

    text, sources, _ = client.call(prompts.RESUME_AGENT_SYSTEM, user_message, use_web_search=False)

    warnings = guardrails.check_resume_tailoring(text)
    text_with_warnings = text + guardrails.format_warnings(warnings)

    note = handoff.extract_handoff(text)
    handoff.log_handoff(AGENT_NAME, note)

    path = state.save_markdown_report(AGENT_NAME, text_with_warnings)

    entry = None
    if log_to_pipeline:
        entry = pipeline.add_application(
            company=company, role=role, location=location, channel=channel,
            resume_version=path, jd_snapshot=job_description[:2000],
            source="resume_agent", used_referral=used_referral,
        )

    return {"report": text_with_warnings, "sources": sources, "path": path,
            "handoff": note, "warnings": warnings, "pipeline_entry": entry}
