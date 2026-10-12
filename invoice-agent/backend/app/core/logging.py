"""Structured JSON logging with redaction of secrets/PII before anything hits
a log sink. Every log line is a JSON object; never interpolate raw payloads.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

_REDACT_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "gstin",
    "email",
    "phone",
    "pdf_bytes",
    "raw_document",
    "hmac_secret",
    "token",
}

_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        value = _GSTIN_RE.sub("[REDACTED_GSTIN]", value)
        value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
        return value
    return value


def _redact_processor(_logger: Any, _name: str, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(sensitive in lowered for sensitive in _REDACT_KEYS):
            event_dict[key] = "[REDACTED]"
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


def configure_logging(environment: str = "development") -> None:
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if environment == "production" else logging.DEBUG,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
