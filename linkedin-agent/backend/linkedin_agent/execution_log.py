"""
In-memory + persisted log of API-triggered agent executions, so the
frontend can show a live "agent execution" view (what ran, when, how long,
success/failure) instead of just the final markdown report.

Kept separate from handoff_log.json / jobs_cache.json etc. because this is
about *invocation telemetry*, not agent-produced domain data.
"""
import itertools
import logging
import threading
import time

from . import state

logger = logging.getLogger("linkedin_agent.execution")

FILE = "execution_log.json"
_lock = threading.Lock()
_counter = itertools.count(1)

MAX_ENTRIES = 200


def start(agent_name: str, source: str, input_summary: str) -> dict:
    entry = {
        "id": next(_counter),
        "agent": agent_name,
        "source": source,           # "orchestrator" | "direct"
        "input_summary": input_summary[:300],
        "status": "running",
        "started_at": state.now_iso(),
        "finished_at": None,
        "duration_s": None,
        "error": None,
    }
    with _lock:
        log = state.load(FILE, [])
        log.append(entry)
        log = log[-MAX_ENTRIES:]
        state.save(FILE, log)
    logger.info("execution.start id=%s agent=%s source=%s", entry["id"], agent_name, source)
    return entry


def finish(entry_id: int, ok: bool, error: str = None, started_monotonic: float = None) -> None:
    with _lock:
        log = state.load(FILE, [])
        for e in log:
            if e["id"] == entry_id:
                e["status"] = "success" if ok else "error"
                e["finished_at"] = state.now_iso()
                e["error"] = error
                if started_monotonic is not None:
                    e["duration_s"] = round(time.monotonic() - started_monotonic, 2)
                break
        state.save(FILE, log)
    logger.info("execution.finish id=%s ok=%s error=%s", entry_id, ok, error)


def recent(limit: int = 50) -> list:
    log = state.load(FILE, [])
    return list(reversed(log))[:limit]
