"""
Application pipeline tracker (Subagent 4's core data structure).

Stages: Applied -> Screened -> Assessment -> Interview -> Offer / Rejected
Ghosted is not a stage the user sets -- it's DERIVED whenever `last_update`
is older than config.STALE_DAYS and the entry isn't already closed
(Offer/Rejected). This directly implements PRD acceptance criterion #5:
"Given a logged application with no status update for 3+ weeks ... it is
shown as 'stale/ghosted', not 'pending'."
"""
import datetime
from . import state, config

FILE = "pipeline.json"
CLOSED_STAGES = {"Offer", "Rejected"}
VALID_STAGES = {"Applied", "Screened", "Assessment", "Interview", "Offer", "Rejected"}


def load() -> list:
    return state.load(FILE, [])


def save(items: list) -> None:
    state.save(FILE, items)


def add_application(company, role, location, channel, resume_version,
                     jd_snapshot, applied_date=None, fit_score=None,
                     source="manual", used_referral=False) -> dict:
    items = load()
    entry_id = f"{company}::{role}::{state.now_iso()}"
    entry = {
        "id": entry_id,
        "company": company,
        "role": role,
        "location": location,
        "applied_date": applied_date or state.now_iso(),
        "channel": channel,               # "cold" | "referral"
        "used_referral": used_referral,
        "resume_version": resume_version,
        "stage": "Applied",
        "last_update": state.now_iso(),
        "jd_snapshot": jd_snapshot,
        "fit_score": fit_score,
        "source": source,                  # "job_discovery" | "outreach" | "manual"
        "history": [{"stage": "Applied", "date": state.now_iso()}],
    }
    items.append(entry)
    save(items)
    return entry


def update_stage(entry_id: str, new_stage: str, note: str = None) -> tuple:
    if new_stage not in VALID_STAGES:
        raise ValueError(f"'{new_stage}' is not a valid stage. Use one of {sorted(VALID_STAGES)}")
    items = load()
    for it in items:
        if it["id"] == entry_id:
            old_stage = it["stage"]
            it["stage"] = new_stage
            it["last_update"] = state.now_iso()
            it.setdefault("history", []).append(
                {"stage": new_stage, "date": state.now_iso(), "note": note}
            )
            save(items)
            return old_stage, it
    raise ValueError(f"No pipeline entry with id {entry_id}")


def is_stale(entry: dict) -> bool:
    if entry["stage"] in CLOSED_STAGES:
        return False
    last = datetime.datetime.fromisoformat(entry["last_update"])
    return (datetime.datetime.now() - last).days >= config.STALE_DAYS


def display_stage(entry: dict) -> str:
    return f"{entry['stage']} (STALE/GHOSTED)" if is_stale(entry) else entry["stage"]


def summary_stats(items: list = None) -> dict:
    items = items if items is not None else load()
    stats = {"Applied": 0, "Screened": 0, "Assessment": 0, "Interview": 0,
              "Offer": 0, "Rejected": 0, "Ghosted": 0}
    for it in items:
        if is_stale(it):
            stats["Ghosted"] += 1
        else:
            stats[it["stage"]] = stats.get(it["stage"], 0) + 1
    return stats


def diagnostics(items: list = None) -> dict:
    """
    Turns raw pipeline history into the diagnostic signals Subagent 4 is
    supposed to reason over: referral vs cold conversion, and where in the
    funnel rejections cluster.
    """
    items = items if items is not None else load()
    referral = [i for i in items if i.get("channel") == "referral"]
    cold = [i for i in items if i.get("channel") == "cold"]

    def ghost_rate(group):
        if not group:
            return None
        ghosted = sum(1 for i in group if is_stale(i))
        return round(ghosted / len(group) * 100, 1)

    def rejection_stage_counts(group):
        counts = {}
        for i in group:
            if i["stage"] == "Rejected":
                # last non-rejected stage before rejection, if tracked
                hist = i.get("history", [])
                prior = hist[-2]["stage"] if len(hist) >= 2 else "Applied"
                counts[prior] = counts.get(prior, 0) + 1
        return counts

    return {
        "referral_count": len(referral),
        "cold_count": len(cold),
        "referral_ghost_rate_pct": ghost_rate(referral),
        "cold_ghost_rate_pct": ghost_rate(cold),
        "rejection_clusters": rejection_stage_counts(items),
    }
