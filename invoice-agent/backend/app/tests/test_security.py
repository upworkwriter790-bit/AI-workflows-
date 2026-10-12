from __future__ import annotations

import time

from app.core.security import verify_signature


def test_valid_signature_accepted():
    from app.core.security import compute_signature

    secret = "topsecret"
    ts = str(time.time())
    body = b'{"event_id": "evt_1"}'
    sig = compute_signature(secret, ts, body)

    ok, reason = verify_signature(secret, ts, body, sig)
    assert ok is True
    assert reason is None


def test_tampered_body_rejected():
    secret = "topsecret"
    ts = str(time.time())
    body = b'{"event_id": "evt_1"}'
    sig = compute_signature_for_test(secret, ts, body)

    ok, reason = verify_signature(secret, ts, b'{"event_id": "evt_2"}', sig)
    assert ok is False
    assert reason == "signature_mismatch"


def test_stale_timestamp_rejected():
    secret = "topsecret"
    ts = str(time.time() - 10_000)
    body = b"{}"
    sig = compute_signature_for_test(secret, ts, body)

    ok, reason = verify_signature(secret, ts, body, sig)
    assert ok is False
    assert reason == "timestamp_outside_allowed_skew"


def compute_signature_for_test(secret: str, ts: str, body: bytes) -> str:
    from app.core.security import compute_signature

    return compute_signature(secret, ts, body)
