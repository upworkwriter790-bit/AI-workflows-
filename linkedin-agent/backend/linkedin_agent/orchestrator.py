"""
The orchestrator does NOT auto-chain agent calls end-to-end in one shot --
that would violate the PRD's locked V1 decision that every LinkedIn action
(posting, connecting, applying) requires explicit human execution between
steps. Instead, it provides the cross-cutting views that make the pipeline
feel like ONE product instead of five disconnected scripts:
  - a unified status report across profile / content / jobs / pipeline / outreach
  - open cross-agent handoffs surfaced in one place
  - pipeline diagnostics (referral vs cold, rejection clustering, staleness)

See router.py for the piece that actually does routing/delegation of a
free-text user request to the correct subagent(s).
"""
from . import state, pipeline, handoff


def status_report() -> str:
    lines = ["# LinkedIn Agent -- Status\n"]

    profile_state = state.load("profile.json", {})
    lines.append("## Profile")
    if profile_state:
        lines.append(f"- Target role: {profile_state.get('target_role')}")
        lines.append(f"- Last audited: {profile_state.get('updated_at')}")
    else:
        lines.append("- No profile audit on file yet. Run the Profile agent first.")

    lines.append("\n## Pipeline")
    items = pipeline.load()
    stats = pipeline.summary_stats(items)
    lines.append(
        f"- Applied {stats['Applied']} | Screened {stats['Screened']} | "
        f"Assessment {stats['Assessment']} | Interview {stats['Interview']} | "
        f"Offer {stats['Offer']} | Rejected {stats['Rejected']} | "
        f"Ghosted (>21d silent) {stats['Ghosted']}"
    )
    if items:
        lines.append("\n| Company | Role | Channel | Stage | Applied | Last Update |")
        lines.append("|---|---|---|---|---|---|")
        for it in items:
            lines.append(
                f"| {it['company']} | {it['role']} | {it['channel']} | "
                f"{pipeline.display_stage(it)} | {it['applied_date'][:10]} | "
                f"{it['last_update'][:10]} |"
            )
        diag = pipeline.diagnostics(items)
        lines.append("\n### Diagnostics")
        lines.append(f"- Referral applications: {diag['referral_count']} "
                      f"(ghost rate: {diag['referral_ghost_rate_pct']}%)")
        lines.append(f"- Cold applications: {diag['cold_count']} "
                      f"(ghost rate: {diag['cold_ghost_rate_pct']}%)")
        if diag["rejection_clusters"]:
            lines.append(f"- Rejection clustering by prior stage: {diag['rejection_clusters']}")
        if diag["referral_ghost_rate_pct"] is not None and diag["cold_ghost_rate_pct"] is not None:
            if diag["cold_ghost_rate_pct"] > diag["referral_ghost_rate_pct"] + 15:
                lines.append(
                    "- **Signal:** cold applications are ghosting noticeably more than "
                    "referred ones -- prioritize the Network/Outreach agents before "
                    "applying cold to the next batch of roles."
                )

    lines.append("\n## Outreach")
    outreach_log = state.load("outreach_log.json", [])
    if outreach_log:
        lines.append("| Company | Person | Role | Status | Date |")
        lines.append("|---|---|---|---|---|")
        for o in outreach_log:
            lines.append(f"| {o['company']} | {o['target_person']} | {o['role']} | "
                          f"{o['status']} | {o['date'][:10]} |")
    else:
        lines.append("- No outreach drafted yet.")

    lines.append("\n## Open Cross-Agent Handoffs")
    open_h = handoff.open_handoffs()
    if open_h:
        for i, h in enumerate(state.load(handoff.HANDOFF_FILE, [])):
            if not h.get("resolved"):
                lines.append(f"- [{i}] ({h['from_agent']}) {h['note']}")
    else:
        lines.append("- None open.")

    return "\n".join(lines)


def status_dict() -> dict:
    """
    Structured (JSON-friendly) version of status_report(), for the API/frontend.
    Keeps status_report() around unchanged for the CLI's `status` command.
    """
    profile_state = state.load("profile.json", {})
    items = pipeline.load()
    stats = pipeline.summary_stats(items)
    diag = pipeline.diagnostics(items) if items else None
    outreach_log = state.load("outreach_log.json", [])
    handoff_log = state.load(handoff.HANDOFF_FILE, [])

    pipeline_items = [
        {**it, "display_stage": pipeline.display_stage(it), "is_stale": pipeline.is_stale(it)}
        for it in items
    ]

    return {
        "profile": profile_state or None,
        "pipeline": {
            "stats": stats,
            "items": pipeline_items,
            "diagnostics": diag,
        },
        "outreach": outreach_log,
        "handoffs": [
            {**h, "index": i} for i, h in enumerate(handoff_log)
        ],
    }
