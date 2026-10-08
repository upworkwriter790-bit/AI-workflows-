"""Lightweight enrichment + email verification (the QC gauntlet, Pillar 3).

MVP uses offline heuristics (no paid data provider). The interface is where a
real enrichment/verification API (Clearbit, Pyrsonalize, etc.) would plug in.
"""
from __future__ import annotations

import re
from typing import Dict

from app.models import Lead, VerificationStatus

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ROLE_LOCALPARTS = {"info", "sales", "contact", "support", "admin", "hello", "team", "office"}

# crude ccTLD -> region map for region inference
_CCTLD_REGION = {
    ".in": "IN", ".sg": "SG", ".ae": "AE", ".uk": "GB", ".au": "AU",
    ".de": "DE", ".fr": "FR", ".ca": "CA", ".us": "US",
}
# phone country code -> region
_PHONE_REGION = {"+91": "IN", "+65": "SG", "+971": "AE", "+44": "GB", "+1": "US", "+61": "AU"}


def verify_email(email: str) -> VerificationStatus:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return VerificationStatus.bounce_risk
    local = email.split("@", 1)[0]
    if local in _ROLE_LOCALPARTS:
        return VerificationStatus.catch_all_risk
    return VerificationStatus.verified


def enrich_lead(lead: Lead) -> Dict:
    """Fill firmographic gaps heuristically. Never overwrite provided values."""
    enr = dict(lead.enriched_data or {})

    # Region inference
    if not enr.get("region"):
        region = None
        if lead.phone:
            for code, reg in _PHONE_REGION.items():
                if lead.phone.replace(" ", "").startswith(code):
                    region = reg
                    break
        if not region:
            host = ""
            if lead.email and "@" in lead.email:
                host = lead.email.split("@", 1)[1].lower()
            elif lead.website:
                host = lead.website.lower()
            for tld, reg in _CCTLD_REGION.items():
                if host.endswith(tld):
                    region = reg
                    break
        if region:
            enr["region"] = region

    # Industry / size are left as provided; a real provider would fill these.
    enr.setdefault("company_size", enr.get("company_size"))
    enr.setdefault("industry", enr.get("industry"))
    return enr
