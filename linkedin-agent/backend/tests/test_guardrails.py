from linkedin_agent import guardrails


def test_job_report_flags_missing_sources():
    warnings = guardrails.check_job_report("### Job Opportunities Report\nnothing found", had_sources=False)
    assert any("No web sources" in w for w in warnings)


def test_job_report_flags_unlabeled_salary():
    text = "Company X pays $120,000 - $150,000 for this role. confirmed opening."
    warnings = guardrails.check_job_report(text, had_sources=True)
    assert any("salary-like figure" in w for w in warnings)


def test_job_report_passes_when_disclosed_and_labeled():
    text = "Salary: not disclosed. This is a confirmed opening at Acme."
    warnings = guardrails.check_job_report(text, had_sources=True)
    assert warnings == []


def test_outreach_flags_banned_opener():
    text = "I hope this finds you well, I wanted to reach out about the role."
    warnings = guardrails.check_outreach_message(text)
    assert any("banned generic opener" in w for w in warnings)


def test_resume_flags_missing_gap_language():
    warnings = guardrails.check_resume_tailoring("Everything matches perfectly, no issues at all.")
    assert any("gap-flagging" in w for w in warnings)
