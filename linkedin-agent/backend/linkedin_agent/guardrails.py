"""
Automated output validation checks.

The PRD names fabrication (invented listings, salaries, metrics presented
as fact) as the single rollback trigger for the whole product. An LLM call
alone can't guarantee zero hallucination, so this module runs cheap,
deterministic checks AFTER generation and surfaces warnings instead of
silently trusting the text. This is a heuristic safety net, not a proof --
treat warnings as "needs human review," not "definitely fabricated."
"""
import re

SALARY_PATTERN = re.compile(r"\$\s?\d{2,3}(?:,\d{3})?(?:\s?-\s?\$?\d{2,3}(?:,\d{3})?)?k?", re.IGNORECASE)
NOT_DISCLOSED_MARKERS = ("not disclosed", "not listed", "undisclosed", "n/a")


def check_job_report(report_text: str, had_sources: bool) -> list:
    warnings = []
    if not had_sources:
        warnings.append(
            "No web sources were returned with this report. Job Discovery "
            "output should always be grounded in live search results -- "
            "treat every listing here as UNVERIFIED until you confirm it "
            "yourself."
        )
    salary_hits = SALARY_PATTERN.findall(report_text)
    if salary_hits and not any(m in report_text.lower() for m in NOT_DISCLOSED_MARKERS):
        warnings.append(
            f"Found {len(salary_hits)} salary-like figure(s) in the report "
            "with no 'not disclosed' language anywhere. Verify each salary "
            "against the actual listing or Glassdoor/Levels.fyi -- do not "
            "assume the agent read a real number for every one of them."
        )
    if "early signal" not in report_text.lower() and "confirmed" not in report_text.lower():
        warnings.append(
            "Report doesn't clearly label listings as 'confirmed' vs 'early "
            "signal' as required. Ask the agent to re-run with explicit "
            "labeling before trusting deadline-sensitive listings."
        )
    return warnings


def check_resume_tailoring(report_text: str) -> list:
    warnings = []
    lowered = report_text.lower()
    if "gap" not in lowered and "flagged" not in lowered:
        warnings.append(
            "No explicit gap-flagging language detected. Confirm the agent "
            "actually checked hard requirements (years of experience, "
            "specific tools) against your real resume rather than smoothing "
            "over a mismatch."
        )
    return warnings


def check_outreach_message(report_text: str) -> list:
    warnings = []
    lowered = report_text.lower()
    banned_openers = ["i hope this finds you well", "i came across your profile and was impressed",
                       "i'd love to pick your brain"]
    for phrase in banned_openers:
        if phrase in lowered:
            warnings.append(f"Draft contains a banned generic opener: \"{phrase}\". Ask for a rewrite.")
    if "referral" in lowered and "first message" not in lowered:
        # weak heuristic: flag for human review rather than block
        warnings.append(
            "Message may be asking for a referral in the first outreach touch. "
            "Re-check that the first-contact ask is low-friction (e.g. a short "
            "chat), not a direct referral request."
        )
    return warnings


def format_warnings(warnings: list) -> str:
    if not warnings:
        return ""
    lines = ["\n---\n**Automated guardrail warnings (review before acting):**"]
    for w in warnings:
        lines.append(f"- {w}")
    return "\n".join(lines) + "\n"
