"""
Cross-agent handoff ledger.

Per the PRD's acceptance criteria: "Given any subagent detects a gap
belonging to another agent, when it completes its report, then the handoff
note names the specific agent and the specific gap."

Each subagent prompt ends its output with a line starting "HANDOFF:" (we
instruct this explicitly in prompts.py). We extract that line, log it here,
and both the CLI (`status`) and the API (`GET /api/handoffs`) surface open
handoffs in one place.
"""
import re
from . import state

HANDOFF_FILE = "handoff_log.json"
HANDOFF_PATTERN = re.compile(r"HANDOFF:\s*(.+)", re.IGNORECASE)


def extract_handoff(agent_output: str) -> str:
    match = HANDOFF_PATTERN.search(agent_output)
    if match:
        return match.group(1).strip()
    return "(no HANDOFF: line found -- agent output may not have followed format)"


def log_handoff(from_agent: str, note: str) -> dict:
    log = state.load(HANDOFF_FILE, [])
    entry = {
        "from_agent": from_agent,
        "note": note,
        "created_at": state.now_iso(),
        "resolved": False,
    }
    log.append(entry)
    state.save(HANDOFF_FILE, log)
    return entry


def open_handoffs() -> list:
    return [h for h in state.load(HANDOFF_FILE, []) if not h.get("resolved")]


def resolve_handoff(index: int) -> None:
    log = state.load(HANDOFF_FILE, [])
    if 0 <= index < len(log):
        log[index]["resolved"] = True
        log[index]["resolved_at"] = state.now_iso()
        state.save(HANDOFF_FILE, log)
