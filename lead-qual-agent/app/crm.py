"""Mock CRM connector: upsert to a per-client CSV with dedup.

Swap this module for a HubSpot/Pipedrive/Salesforce client in production; the
graph only depends on upsert_lead() and find_duplicate().
"""
from __future__ import annotations

import csv
import os
from typing import Optional

from app import config, db
from app.models import Lead, QualificationResult

_FIELDS = [
    "lead_id", "name", "email", "company", "title", "phone", "website",
    "source", "source_tool", "verification_status", "region", "industry", "company_size",
    "status", "owner_id", "label", "total_score", "fit_score", "intent_score",
    "next_step", "created_at", "updated_at",
]


def _csv_path(client_id: str) -> str:
    os.makedirs(config.CRM_DIR, exist_ok=True)
    return os.path.join(config.CRM_DIR, f"{client_id}.csv")


def _domain(email: str) -> str:
    return email.split("@", 1)[1].lower() if email and "@" in email else ""


def find_duplicate(lead: Lead) -> Optional[Lead]:
    """Dedup by exact email, else by (company domain + same name)."""
    if lead.email:
        for existing in db.find_leads_by_email(lead.client_id, lead.email):
            if existing.id != lead.id:
                return existing
    dom = _domain(lead.email)
    if dom:
        for existing in db.list_leads(lead.client_id):
            if existing.id == lead.id:
                continue
            if _domain(existing.email) == dom and existing.name.strip().lower() == lead.name.strip().lower() and lead.name:
                return existing
    return None


def upsert_lead(lead: Lead, qual: Optional[QualificationResult]) -> None:
    enr = lead.enriched_data or {}
    row = {
        "lead_id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "title": lead.title,
        "phone": lead.phone or "",
        "website": lead.website or "",
        "source": lead.source.value,
        "source_tool": lead.source_tool or "",
        "verification_status": lead.verification_status.value if lead.verification_status else "",
        "region": enr.get("region", ""),
        "industry": enr.get("industry", ""),
        "company_size": enr.get("company_size", ""),
        "status": lead.status.value,
        "owner_id": lead.owner_id or "",
        "label": qual.label.value if qual else "",
        "total_score": qual.total_score if qual else "",
        "fit_score": qual.fit_score if qual else "",
        "intent_score": qual.intent_score if qual else "",
        "next_step": qual.next_step.value if qual else "",
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }

    path = _csv_path(lead.client_id)
    rows = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["lead_id"]] = r
    rows[lead.id] = row  # upsert by lead_id

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        w.writeheader()
        for r in rows.values():
            w.writerow({k: r.get(k, "") for k in _FIELDS})
