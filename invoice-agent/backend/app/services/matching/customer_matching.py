"""Deterministic candidate retrieval for customers — exact match only
(spec §5). No fuzzy-name matching: a fuzzy match is never auto-selected
anyway, so there is no value in a fuzzy library here, only risk.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.customer import Customer


def find_candidate_customers(db: Session, *, email: str | None, phone: str | None) -> list[dict]:
    candidates: list[Customer] = []
    seen_ids: set[str] = set()

    if email:
        for c in db.query(Customer).filter(Customer.email == email.strip().lower()).all():
            if c.id not in seen_ids:
                candidates.append(c)
                seen_ids.add(c.id)
    if phone:
        for c in db.query(Customer).filter(Customer.phone == phone).all():
            if c.id not in seen_ids:
                candidates.append(c)
                seen_ids.add(c.id)

    results = []
    for c in candidates:
        basis = "EXACT_EMAIL" if email and c.email == email.strip().lower() else "EXACT_PHONE"
        results.append(
            {
                "id": c.id,
                "match_basis": basis,
                "display_name": c.display_name,
                "email": c.email,
                "phone": c.phone,
            }
        )
    return results
