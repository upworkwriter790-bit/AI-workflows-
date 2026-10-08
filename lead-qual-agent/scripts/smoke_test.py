"""End-to-end smoke test (no server, no Ollama needed in stub mode).

Run from the project root:  python scripts/smoke_test.py
Seeds the demo client if needed, ingests 3 varied leads, processes each
through the LangGraph workflow, and prints the qualification + draft.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, graph  # noqa: E402
from app.models import Channel, ConversationMessage, Lead, MessageRole  # noqa: E402
from scripts.seed import CLIENT_ID, seed  # noqa: E402

LEADS = [
    # Hot: quantified need, timeline, authority, budget in range
    {
        "name": "Rahul Sharma", "email": "rahul@acme.in", "company": "Acme Logistics",
        "title": "Operations Head", "phone": "+91-9800000000", "website": "https://acme.in",
        "message": ("We are losing ~15% of deliveries due to poor routing. Our current tool is basic and "
                    "doesn't optimize in real time. We need a solution before our peak season in Q1. I own "
                    "this initiative but need CFO sign-off for spend above $30k."),
        "enriched_data": {"company_size": 150, "industry": "Logistics", "region": "IN", "budget_range": "$20k-$50k"},
    },
    # Warm: real-ish pain, vague budget/timeline
    {
        "name": "Meera Iyer", "email": "meera@shipfast.sg", "company": "ShipFast",
        "title": "Logistics Manager", "message": ("We struggle with manual route planning and want to improve "
                    "efficiency. Not sure about budget yet, exploring options for next year maybe."),
        "enriched_data": {"company_size": 80, "industry": "Supply Chain", "region": "SG"},
    },
    # Cold: no need, wrong fit
    {
        "name": "John Doe", "email": "info@retailco.com", "company": "RetailCo",
        "title": "Intern", "message": "Just curious what you do, nice to have maybe someday.",
        "enriched_data": {"company_size": 5, "industry": "Retail B2C", "region": "US"},
    },
]


def main() -> None:
    db.init_db()
    if not db.get_client(CLIENT_ID):
        seed()

    for payload in LEADS:
        lead = Lead(
            client_id=CLIENT_ID, source=Channel.web_form,
            name=payload["name"], email=payload["email"], company=payload["company"],
            title=payload["title"], phone=payload.get("phone"), website=payload.get("website"),
            initial_message=payload["message"], enriched_data=payload.get("enriched_data", {}),
            source_tool="smoke_test",
        )
        db.save_lead(lead)
        db.save_message(ConversationMessage(lead_id=lead.id, role=MessageRole.lead, channel=Channel.web_form, content=lead.initial_message))

        graph.process_lead(lead.id)

        out = db.get_lead(lead.id)
        q = db.latest_qualification(lead.id)
        print("\n" + "=" * 70)
        print(f"{out.name} ({out.company}) -> {q.label.value}  total={q.total_score} "
              f"fit={q.fit_score} intent={q.intent_score}")
        print(f"  BANT: {q.bant_scores()}  next_step={q.next_step.value}  owner={out.owner_id}")
        print(f"  verify={out.verification_status.value if out.verification_status else None}  status={out.status.value}")
        print(f"  reasoning: {q.reasoning}")
        print(f"  draft:\n    " + (out.draft_response or "").replace("\n", "\n    "))

    print("\n" + "=" * 70)
    print("Dashboard:")
    from app.main import dashboard
    import json
    print(json.dumps(dashboard(CLIENT_ID), indent=2))


if __name__ == "__main__":
    main()
