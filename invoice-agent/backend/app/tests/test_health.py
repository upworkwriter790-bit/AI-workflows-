from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["email_provider"] == "mock"
    assert body["whatsapp_provider"] == "mock"
