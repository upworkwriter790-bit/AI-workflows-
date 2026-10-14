from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["email_provider"] == "mock"
    assert body["whatsapp_provider"] == "mock"
    assert "generated_invoices_ready" in body


def test_health_flags_missing_seller_config(client):
    resp = client.get("/health")
    body = resp.json()
    # .env.example ships with no seller identity filled in, so in a clean
    # dev checkout this must be False, not silently True.
    assert body["generated_invoices_ready"] is False
    assert "company_legal_name" in body["missing_seller_config"]
