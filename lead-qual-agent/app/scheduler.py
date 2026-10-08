"""Meeting scheduling. MVP returns a configured calendar link and records a
Meeting row; swap for Calendly/Google Calendar API in production.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models import Client, Lead, Meeting, Rep


def _rep(client: Client, rep_id: Optional[str]) -> Optional[Rep]:
    return next((r for r in client.reps if r.id == rep_id), None)


def propose_meeting(client: Client, lead: Lead) -> Meeting:
    rep = _rep(client, lead.owner_id)
    link = (rep.calendar_link if rep and rep.calendar_link else None) or client.default_calendar_link or "https://calendly.com/your-team/intro"
    meeting = Meeting(
        lead_id=lead.id,
        client_id=lead.client_id,
        owner_id=lead.owner_id,
        calendar_link=link,
        status="proposed",
    )
    db.save_meeting(meeting)
    return meeting


def book_meeting(lead: Lead, scheduled_for: str) -> Optional[Meeting]:
    meeting = db.get_meeting_for_lead(lead.id)
    if not meeting:
        return None
    meeting.status = "booked"
    meeting.scheduled_for = scheduled_for
    db.save_meeting(meeting)
    return meeting
