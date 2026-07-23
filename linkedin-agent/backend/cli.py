#!/usr/bin/env python3
"""
LinkedIn Agent CLI -- copilot-only, per PRD.

Every command drafts/researches; nothing here ever posts, connects, sends,
or applies on LinkedIn automatically. You read the output, you click.

Quickstart:
    export ANTHROPIC_API_KEY=sk-ant-...
    python cli.py profile --file my_profile.txt --role "SDE Internship, backend"
    python cli.py content --companies "Stripe, Notion, Ramp"
    python cli.py jobs --role "Backend SDE Intern" --geo remote --level "student, no experience"
    python cli.py resume --file resume.txt --company Stripe --role "Backend Intern" \\
        --location Remote --jd-file stripe_jd.txt
    python cli.py outreach --company Stripe --person "Jane Doe, Eng Manager" --role "Backend Intern"
    python cli.py status
    python cli.py track --id "<pipeline-id>" --stage Interview
    python cli.py export --format csv
"""
import argparse
import sys

from linkedin_agent import config, pipeline, orchestrator, handoff, state
from linkedin_agent.client import AgentClient
from linkedin_agent.agents import profile_agent, content_agent, job_agent, resume_agent, outreach_agent


def _read(path_or_text_flag_value, inline_flag_value):
    if path_or_text_flag_value:
        with open(path_or_text_flag_value, "r") as f:
            return f.read()
    if inline_flag_value:
        return inline_flag_value
    return None


def cmd_profile(args):
    client = AgentClient()
    profile_text = _read(args.file, args.text)
    if not profile_text:
        sys.exit("Provide --file or --text with the profile content.")
    ref = _read(args.ref_file, args.ref_text)
    result = profile_agent.run(client, profile_text, args.role, reference_profiles=ref)
    print(result["report"])
    print(f"\n[saved to {result['path']}]")


def cmd_content(args):
    client = AgentClient()
    perf = _read(args.perf_file, args.perf_text)
    result = content_agent.run(client, target_companies=args.companies, prior_post_performance=perf)
    print(result["report"])
    print(f"\n[saved to {result['path']}]")


def cmd_log_post(args):
    performance = {
        "likes": args.likes, "comments": args.comments, "shares": args.shares,
        "profile_views_after": args.profile_views, "connection_requests_after": args.connections,
    }
    content_agent.log_post_performance(args.idea, performance)
    print(f"Logged performance for post: {args.idea!r}")


def cmd_jobs(args):
    client = AgentClient()
    result = job_agent.run(client, target_role=args.role, geography=args.geo,
                             experience_level=args.level, target_companies=args.companies,
                             active_only=args.active_only)
    print(result["report"])
    print(f"\n[saved to {result['path']}]")
    if result["warnings"]:
        print("\n[!] Guardrail warnings were attached above -- review before trusting any listing.")


def cmd_resume(args):
    client = AgentClient()
    master_resume = _read(args.file, args.text)
    jd = _read(args.jd_file, args.jd_text)
    if not master_resume or not jd:
        sys.exit("Provide --file/--text for the resume AND --jd-file/--jd-text for the job description.")
    result = resume_agent.run(
        client, master_resume_text=master_resume, company=args.company, role=args.role,
        location=args.location, job_description=jd, channel=args.channel,
        used_referral=args.referral, log_to_pipeline=not args.no_log,
    )
    print(result["report"])
    print(f"\n[saved to {result['path']}]")
    if result["pipeline_entry"]:
        print(f"[logged to pipeline: id={result['pipeline_entry']['id']}]")


def cmd_outreach(args):
    client = AgentClient()
    resume_summary = _read(args.resume_summary_file, args.resume_summary_text)
    result = outreach_agent.run(
        client, company=args.company, target_person=args.person, role=args.role,
        resume_summary=resume_summary, relationship_warmth=args.warmth,
        referral_available=args.referral_available,
    )
    print(result["report"])
    print(f"\n[saved to {result['path']}]")


def cmd_outreach_status(args):
    ok = outreach_agent.update_status(args.company, args.person, args.status)
    print("Updated." if ok else "No matching outreach entry found.")


def cmd_track(args):
    old, entry = pipeline.update_stage(args.id, args.stage, note=args.note)
    print(f"{entry['company']} / {entry['role']}: {old} -> {entry['stage']}")


def cmd_add_application(args):
    entry = pipeline.add_application(
        company=args.company, role=args.role, location=args.location,
        channel=args.channel, resume_version=args.resume_version or "manual",
        jd_snapshot=args.jd_snapshot or "", used_referral=args.referral, source="manual",
    )
    print(f"Added to pipeline: id={entry['id']}")


def cmd_status(args):
    print(orchestrator.status_report())


def cmd_resolve_handoff(args):
    handoff.resolve_handoff(args.index)
    print(f"Marked handoff #{args.index} resolved.")


def cmd_export(args):
    import csv
    items = pipeline.load()
    if not items:
        print("Pipeline is empty -- nothing to export.")
        return
    out_path = f"{config.OUTPUT_DIR}/pipeline_export.csv"
    import os
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    fields = ["id", "company", "role", "location", "channel", "used_referral",
              "stage", "applied_date", "last_update", "fit_score", "source"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for it in items:
            writer.writerow(it)
    print(f"Exported {len(items)} pipeline entries to {out_path}")


def cmd_orchestrate(args):
    from linkedin_agent import router
    client = AgentClient()
    result = router.route_and_run(client, args.task)
    if result["status"] == "needs_input":
        print(f"[router] chose agent={result['agent']!r} but is missing: {result['missing']}")
        print(f"Reasoning: {result['reasoning']}")
        print("Re-run the matching subcommand directly with those fields filled in.")
        return
    print(f"[router] chose agent={result['agent']!r} -- {result['reasoning']}")
    print(result["result"]["report"])


def build_parser():
    p = argparse.ArgumentParser(prog="linkedin-agent", description="Copilot for LinkedIn profile, content, job search, resumes, and outreach.")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("profile", help="Run the Profile Optimization Agent")
    sp.add_argument("--file", help="Path to a text file with your current profile content")
    sp.add_argument("--text", help="Inline profile content")
    sp.add_argument("--role", required=True, help="Target role/context, e.g. 'final-year CS student targeting SDE internships'")
    sp.add_argument("--ref-file", help="Path to reference/benchmark profiles (optional)")
    sp.add_argument("--ref-text", help="Inline reference profiles (optional)")
    sp.set_defaults(func=cmd_profile)

    sp = sub.add_parser("content", help="Run the Network Building & Content Strategy Agent")
    sp.add_argument("--companies", help="Target companies/recruiter types, comma-separated")
    sp.add_argument("--perf-file", help="Path to prior post performance notes (for feedback loop cycles)")
    sp.add_argument("--perf-text", help="Inline prior post performance notes")
    sp.set_defaults(func=cmd_content)

    sp = sub.add_parser("log-post", help="Log real performance numbers for a post you actually published")
    sp.add_argument("--idea", required=True)
    sp.add_argument("--likes", type=int, default=0)
    sp.add_argument("--comments", type=int, default=0)
    sp.add_argument("--shares", type=int, default=0)
    sp.add_argument("--profile-views", type=int, default=0)
    sp.add_argument("--connections", type=int, default=0)
    sp.set_defaults(func=cmd_log_post)

    sp = sub.add_parser("jobs", help="Run the Job Discovery & Market Intelligence Agent")
    sp.add_argument("--role", help="Target role (defaults to profile.json's target_role)")
    sp.add_argument("--geo", default="remote", help="local | national | international | remote | all")
    sp.add_argument("--level", default="not specified", help="Experience level / eligibility constraints")
    sp.add_argument("--companies", help="Prioritized target companies, comma-separated")
    sp.add_argument("--active-only", action="store_true", help="Skip early-signal scan")
    sp.set_defaults(func=cmd_jobs)

    sp = sub.add_parser("resume", help="Run the Resume Tailoring Agent for one job listing")
    sp.add_argument("--file", help="Path to your master resume text")
    sp.add_argument("--text", help="Inline master resume text")
    sp.add_argument("--company", required=True)
    sp.add_argument("--role", required=True)
    sp.add_argument("--location", required=True)
    sp.add_argument("--jd-file", help="Path to the job description text")
    sp.add_argument("--jd-text", help="Inline job description text")
    sp.add_argument("--channel", default="cold", choices=["cold", "referral"])
    sp.add_argument("--referral", action="store_true")
    sp.add_argument("--no-log", action="store_true", help="Don't add this to the pipeline tracker")
    sp.set_defaults(func=cmd_resume)

    sp = sub.add_parser("outreach", help="Run the Cold Outreach & Recruiter Engagement Agent")
    sp.add_argument("--company", required=True)
    sp.add_argument("--person", required=True, help="Name, title, e.g. 'Jane Doe, Engineering Manager'")
    sp.add_argument("--role", required=True)
    sp.add_argument("--resume-summary-file")
    sp.add_argument("--resume-summary-text")
    sp.add_argument("--warmth", default="cold", choices=["cold", "warmed-up", "referral-available"])
    sp.add_argument("--referral-available", action="store_true")
    sp.set_defaults(func=cmd_outreach)

    sp = sub.add_parser("outreach-status", help="Update the status of a logged outreach attempt")
    sp.add_argument("--company", required=True)
    sp.add_argument("--person", required=True)
    sp.add_argument("--status", required=True, choices=["sent", "responded_positive", "responded_negative", "no_response", "closed"])
    sp.set_defaults(func=cmd_outreach_status)

    sp = sub.add_parser("track", help="Update an existing pipeline entry's stage")
    sp.add_argument("--id", required=True, help="Pipeline entry id (see `status`)")
    sp.add_argument("--stage", required=True, choices=list(pipeline.VALID_STAGES))
    sp.add_argument("--note")
    sp.set_defaults(func=cmd_track)

    sp = sub.add_parser("add-application", help="Manually log an application not created via the resume agent")
    sp.add_argument("--company", required=True)
    sp.add_argument("--role", required=True)
    sp.add_argument("--location", required=True)
    sp.add_argument("--channel", default="cold", choices=["cold", "referral"])
    sp.add_argument("--referral", action="store_true")
    sp.add_argument("--resume-version")
    sp.add_argument("--jd-snapshot")
    sp.set_defaults(func=cmd_add_application)

    sp = sub.add_parser("status", help="Unified cross-agent status: profile, pipeline, outreach, open handoffs")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("resolve-handoff", help="Mark a cross-agent handoff note as resolved")
    sp.add_argument("--index", type=int, required=True)
    sp.set_defaults(func=cmd_resolve_handoff)

    sp = sub.add_parser("export", help="Export the pipeline tracker to CSV")
    sp.add_argument("--format", default="csv", choices=["csv"])
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("orchestrate", help="Describe what you want in free text; the router picks the right agent")
    sp.add_argument("task", help="Free-text task description, e.g. 'find me remote backend intern roles at Stripe'")
    sp.set_defaults(func=cmd_orchestrate)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as e:
        sys.exit(f"[error] {e}")


if __name__ == "__main__":
    main()
