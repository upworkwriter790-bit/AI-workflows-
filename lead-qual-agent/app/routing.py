"""Lead routing / owner assignment.

Strategies: round_robin, territory (region), segment (SMB/MM/Enterprise).
Falls back to None (-> manual routing) when rules are ambiguous.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models import Client, Lead, Rep


def _segment_of(lead: Lead) -> str:
    size = (lead.enriched_data or {}).get("company_size")
    if not isinstance(size, int):
        return "unknown"
    if size < 100:
        return "SMB"
    if size < 1000:
        return "MM"
    return "Enterprise"


def assign_owner(client: Client, lead: Lead) -> Optional[str]:
    reps = [r for r in client.reps if r.active]
    if not reps:
        return None

    strategy = client.routing_strategy
    region = ((lead.enriched_data or {}).get("region", "") or "").upper()
    segment = _segment_of(lead)

    if strategy == "territory" and region:
        matches = [r for r in reps if region in [x.upper() for x in r.regions]]
        if matches:
            return _round_robin(client.id, matches)
        return None  # ambiguous -> manual

    if strategy == "segment" and segment != "unknown":
        matches = [r for r in reps if segment in r.segments]
        if matches:
            return _round_robin(client.id, matches)
        return None

    # default: round robin across all active reps
    return _round_robin(client.id, reps)


def _round_robin(client_id: str, reps: list[Rep]) -> str:
    idx = db.next_round_robin_index(client_id, len(reps))
    return reps[idx].id
