from __future__ import annotations

from app.core.logging import _redact_processor


def test_redacts_known_sensitive_keys():
    event = {"api_key": "sk-live-abc123", "note": "fine"}
    result = _redact_processor(None, "info", event)
    assert result["api_key"] == "[REDACTED]"
    assert result["note"] == "fine"


def test_redacts_gstin_pattern_in_free_text():
    event = {"message": "invoice from 27AAAPL1234C1Z5 received"}
    result = _redact_processor(None, "info", event)
    assert "27AAAPL1234C1Z5" not in result["message"]
    assert "[REDACTED_GSTIN]" in result["message"]


def test_redacts_email_pattern_in_free_text():
    event = {"message": "sent to buyer@example.com"}
    result = _redact_processor(None, "info", event)
    assert "buyer@example.com" not in result["message"]
    assert "[REDACTED_EMAIL]" in result["message"]
