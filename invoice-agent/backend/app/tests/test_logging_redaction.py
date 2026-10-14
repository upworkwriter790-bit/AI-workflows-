from __future__ import annotations

from app.core.logging import _redact_processor


def test_redacts_known_sensitive_keys():
    event = {"api_key": "sk-live-abc123", "note": "fine"}
    result = _redact_processor(None, "info", event)
    assert result["api_key"] == "[REDACTED]"
    assert result["note"] == "fine"


def test_redacts_phone_pattern_in_free_text():
    event = {"message": "notified +919876543210 via whatsapp"}
    result = _redact_processor(None, "info", event)
    assert "+919876543210" not in result["message"]
    assert "[REDACTED_PHONE]" in result["message"]


def test_redacts_email_pattern_in_free_text():
    event = {"message": "sent to buyer@example.com"}
    result = _redact_processor(None, "info", event)
    assert "buyer@example.com" not in result["message"]
    assert "[REDACTED_EMAIL]" in result["message"]
