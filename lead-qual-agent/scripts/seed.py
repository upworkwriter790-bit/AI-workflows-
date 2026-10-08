"""Seed a demo client (Acme Logistics), ICP, BANT config, reps and RAG docs.

Run from the project root:  python scripts/seed.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, rag  # noqa: E402
from app.models import BANTConfig, Client, ICPConfig, Rep  # noqa: E402

CLIENT_ID = "client_001"


def seed() -> None:
    db.init_db()

    client = Client(
        id=CLIENT_ID,
        name="Acme Logistics",
        industry="Logistics",
        timezone="Asia/Kolkata",
        crm_provider="mock",
        routing_strategy="territory",
        require_human_approval=False,
        default_calendar_link="https://calendly.com/acme-logistics/intro",
        reps=[
            Rep(id="rep_in", name="Priya Nair", email="priya@acme.in", regions=["IN"], segments=["SMB", "MM"], calendar_link="https://calendly.com/priya-acme/intro"),
            Rep(id="rep_sg", name="Wei Tan", email="wei@acme.sg", regions=["SG", "AE"], segments=["MM", "Enterprise"], calendar_link="https://calendly.com/wei-acme/intro"),
        ],
    )
    db.save_client(client)

    db.save_icp(ICPConfig(
        client_id=CLIENT_ID,
        target_industries=["Logistics", "Supply Chain", "E-commerce"],
        exclude_industries=["Retail B2C"],
        company_size_min=20,
        company_size_max=1000,
        target_regions=["IN", "SG", "AE"],
        target_titles=["Head", "Director", "VP", "Founder", "CEO", "Chief"],
        ideal_use_cases=["route optimization", "fleet management", "cost reduction", "delivery"],
    ))

    db.save_bant(BANTConfig(
        client_id=CLIENT_ID,
        weights={"budget": 0.15, "authority": 0.25, "need": 0.35, "timeline": 0.25},
        score_thresholds={"hot_min": 0.60, "warm_min": 0.35},
        rules={"auto_disqualify_if_need_0": True, "require_authority_ge_1": True},
    ))

    docs = [
        {"doc_type": "icp", "doc_id": "icp_main", "text": (
            "Ideal Customer Profile for Acme Logistics. We sell real-time delivery route "
            "optimization and fleet management software. Best-fit customers are logistics, "
            "supply chain and e-commerce companies with 20-1000 employees in India, Singapore "
            "and the UAE. Decision makers are Heads/Directors/VPs of Operations, Supply Chain, "
            "or Founders. Common pains: delivery delays, high fuel costs, manual route planning, "
            "lack of real-time visibility. Typical qualified budget is $20k+ per year."
        )},
        {"doc_type": "playbook", "doc_id": "objections", "text": (
            "Objection handling. Price: emphasize ROI from reduced fuel and failed deliveries; "
            "typical customers recover cost within 2 quarters. Timing: offer a 2-week pilot on "
            "one route cluster. Integration: we support CSV import and REST APIs for existing TMS."
        )},
        {"doc_type": "playbook", "doc_id": "discovery", "text": (
            "Discovery questions: What % of deliveries are late or failed today? How are routes "
            "planned now (manual vs tool)? What is the cost of a failed delivery? When do you need "
            "this live? Who owns this decision and who controls budget?"
        )},
        {"doc_type": "case_study", "doc_id": "cs_fleet", "text": (
            "Case study: A 150-vehicle regional carrier cut failed deliveries 15% to 4% and fuel "
            "spend 12% within one quarter after adopting Acme real-time routing before peak season."
        )},
    ]
    n = rag.index_documents(CLIENT_ID, docs)
    print(f"Seeded client '{CLIENT_ID}' (Acme Logistics) with ICP, BANT config, 2 reps.")
    print(f"RAG chunks indexed: {n} (0 means Ollama/Chroma not available - agent still runs).")


if __name__ == "__main__":
    seed()
