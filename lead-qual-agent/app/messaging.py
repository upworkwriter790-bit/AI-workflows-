"""Outbound messaging. MVP logs/prints; swap for SMTP/Gmail/Twilio in prod."""
from __future__ import annotations

from app import db
from app.models import Channel, ConversationMessage, Lead, MessageRole


def send_message(lead: Lead, channel: Channel, content: str) -> ConversationMessage:
    # Real integration point: email (SMTP/Gmail API) or WhatsApp (Twilio/Meta).
    print(f"[send:{channel.value}] -> {lead.email or lead.phone}\n{content}\n{'-' * 40}")
    msg = ConversationMessage(
        lead_id=lead.id,
        role=MessageRole.agent,
        channel=channel,
        content=content,
    )
    db.save_message(msg)
    return msg
