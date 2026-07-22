import datetime

from linkedin_agent import pipeline, state


def test_add_and_track_application():
    entry = pipeline.add_application(
        company="Stripe", role="Backend Intern", location="Remote",
        channel="cold", resume_version="v1", jd_snapshot="build payments infra",
    )
    assert entry["stage"] == "Applied"

    old_stage, updated = pipeline.update_stage(entry["id"], "Interview", note="phone screen")
    assert old_stage == "Applied"
    assert updated["stage"] == "Interview"
    assert updated["history"][-1]["note"] == "phone screen"


def test_ghosted_derivation_from_staleness():
    entry = pipeline.add_application(
        company="Notion", role="SWE Intern", location="Remote",
        channel="cold", resume_version="v1", jd_snapshot="",
    )
    items = pipeline.load()
    for it in items:
        if it["id"] == entry["id"]:
            it["last_update"] = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat(timespec="seconds")
    pipeline.save(items)

    reloaded = pipeline.load()
    stale_entry = next(i for i in reloaded if i["id"] == entry["id"])
    assert pipeline.is_stale(stale_entry)
    assert "GHOSTED" in pipeline.display_stage(stale_entry)

    stats = pipeline.summary_stats(reloaded)
    assert stats["Ghosted"] == 1
    assert stats["Applied"] == 0  # moved out of Applied bucket once ghosted


def test_diagnostics_referral_vs_cold_ghost_rate():
    referral = pipeline.add_application(
        company="A", role="R1", location="Remote", channel="referral",
        resume_version="v1", jd_snapshot="",
    )
    cold = pipeline.add_application(
        company="B", role="R2", location="Remote", channel="cold",
        resume_version="v1", jd_snapshot="",
    )
    items = pipeline.load()
    old_date = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat(timespec="seconds")
    for it in items:
        if it["id"] == cold["id"]:
            it["last_update"] = old_date
    pipeline.save(items)

    diag = pipeline.diagnostics(pipeline.load())
    assert diag["referral_count"] == 1
    assert diag["cold_count"] == 1
    assert diag["referral_ghost_rate_pct"] == 0.0
    assert diag["cold_ghost_rate_pct"] == 100.0
