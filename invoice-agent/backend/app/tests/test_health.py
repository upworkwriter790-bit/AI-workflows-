from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "live_invoicing_ready" in body


def test_health_flags_missing_company_config(client):
    resp = client.get("/health")
    body = resp.json()
    # .env.example ships with no company identity filled in, so in a clean
    # dev checkout this must be False, not silently True.
    assert body["live_invoicing_ready"] is False
    assert "company_legal_name" in body["missing_company_config"]
