"""HMAC webhook signature verification + replay protection.

Used by the CRM paid-order webhook (see api/webhooks.py, Phase 2). Kept here,
dependency-free, so it is easy to unit test in isolation.
"""

from __future__ import annotations

import hashlib
import hmac
import time

DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + raw_body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    timestamp: str,
    raw_body: bytes,
    provided_signature: str,
    *,
    now: float | None = None,
    max_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> tuple[bool, str | None]:
    """Returns (is_valid, error_reason). error_reason is None on success."""
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return False, "invalid_timestamp"

    now = now if now is not None else time.time()
    if abs(now - ts) > max_skew_seconds:
        return False, "timestamp_outside_allowed_skew"

    expected = compute_signature(secret, timestamp, raw_body)
    if not hmac.compare_digest(expected, provided_signature):
        return False, "signature_mismatch"

    return True, None
