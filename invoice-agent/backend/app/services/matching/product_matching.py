"""Deterministic candidate retrieval for the product/tax catalog —
exact internal_reference match, or an exact (case-insensitive)
substring match against the item's display description or one of its
aliases (spec §5). No fuzzy library, no LLM guess at a HSN/SAC or GST
rate: whatever the AI ultimately picks must be one of these rows.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.product_catalog_item import ProductCatalogItem


def find_candidate_products(db: Session, *, item_reference: str | None, free_text: str | None) -> list[dict]:
    query = db.query(ProductCatalogItem).filter_by(active=True)

    if item_reference:
        exact = query.filter(ProductCatalogItem.internal_reference == item_reference).all()
        if exact:
            return [_to_candidate(item, "PRODUCT_ID") for item in exact]

    if not free_text:
        return []

    needle = free_text.strip().lower()
    if not needle:
        return []

    candidates = []
    for item in query.all():
        haystacks = [item.display_description.lower(), *[a.lower() for a in (item.aliases_json or [])]]
        if any(needle in h or h in needle for h in haystacks):
            basis = "EXACT_ALIAS" if any(needle == h for h in haystacks) else "DESCRIPTION_MATCH"
            candidates.append(_to_candidate(item, basis))
    return candidates


def _to_candidate(item: ProductCatalogItem, basis: str) -> dict:
    return {
        "id": item.id,
        "internal_reference": item.internal_reference,
        "match_basis": basis,
        "display_description": item.display_description,
        "hsn_or_sac_code": item.hsn_or_sac_code,
        "unit": item.unit,
        "unit_price": str(item.unit_price),
        "gst_rate": str(item.gst_rate),
        "product_type": item.product_type,
    }
