"""FastAPI surface for the Lead Response & Qualification Agent."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import config, db, graph, rag
from app.models import (
    AuditEntry,
    Channel,
    ConversationMessage,
    Label,
    Lead,
    LeadStatus,
    MessageRole,
)

app = FastAPI(title="Lead Response & Qualification Agent", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# --------------------------------------------------------------------------- #
# Request / response schemas
# --------------------------------------------------------------------------- #
class IngestRequest(BaseModel):
    source: Channel = Channel.web_form
    client_id: str
    lead: Dict[str, Any]
    source_tool: Optional[str] = None
    received_at: Optional[str] = None
    auto_process: bool = True


class ApproveRequest(BaseModel):
    approve: bool = True
    message: Optional[str] = None       # edited draft, if any
    actor: str = "user"


class OverrideRequest(BaseModel):
    label: Optional[Label] = None
    total_score: Optional[int] = None
    reason: str = ""
    actor: str = "user"


class RagIndexRequest(BaseModel):
    docs: List[Dict[str, str]]          # [{doc_type, doc_id, text}]


# --------------------------------------------------------------------------- #
# Ingestion normalization
# --------------------------------------------------------------------------- #
def _normalize(source: Channel, payload: Dict[str, Any], client_id: str, source_tool: Optional[str]) -> Lead:
    """Map structured/unstructured channel payloads into a Lead."""
    if source == Channel.email:
        name = payload.get("from_name") or payload.get("name") or ""
        email = payload.get("from_email") or payload.get("email") or ""
        message = payload.get("body") or payload.get("message") or ""
        subject = payload.get("subject")
        if subject:
            message = f"[{subject}] {message}"
        lead = Lead(client_id=client_id, source=source, name=name, email=email, initial_message=message)
    elif source == Channel.whatsapp:
        lead = Lead(
            client_id=client_id, source=source,
            name=payload.get("profile_name") or payload.get("name") or "",
            phone=payload.get("from_number") or payload.get("phone"),
            email=payload.get("email", ""),
            initial_message=payload.get("text") or payload.get("message") or "",
        )
    else:  # web_form / linkedin: structured
        lead = Lead(
            client_id=client_id, source=source,
            name=payload.get("name", ""),
            email=payload.get("email", ""),
            company=payload.get("company", ""),
            title=payload.get("title", ""),
            phone=payload.get("phone"),
            website=payload.get("website"),
            initial_message=payload.get("message", ""),
            utm_source=payload.get("utm_source"),
            utm_campaign=payload.get("utm_campaign"),
        )
    lead.source_tool = source_tool
    if payload.get("enriched_data"):
        lead.enriched_data = dict(payload["enriched_data"])
    # Allow structured firmographics inline on the lead payload too.
    for key in ("company_size", "industry", "region", "budget_range"):
        if key in payload and key not in lead.enriched_data:
            lead.enriched_data[key] = payload[key]
    return lead


def _lead_summary(lead: Lead, qual=None) -> Dict[str, Any]:
    return {
        "lead_id": lead.id,
        "status": lead.status.value,
        "owner_id": lead.owner_id,
        "verification_status": lead.verification_status.value if lead.verification_status else None,
        "label": qual.label.value if qual else None,
        "total_score": qual.total_score if qual else None,
        "next_step": qual.next_step.value if qual else None,
        "draft_response": lead.draft_response,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "llm_mode": config.llm_mode(), "rag_enabled": config.RAG_ENABLED}


@app.post("/leads/ingest")
def ingest(req: IngestRequest) -> Dict[str, Any]:
    if not db.get_client(req.client_id):
        raise HTTPException(404, f"unknown client_id {req.client_id}; seed it first")
    lead = _normalize(req.source, req.lead, req.client_id, req.source_tool)
    db.save_lead(lead)
    db.save_message(
        ConversationMessage(lead_id=lead.id, role=MessageRole.lead, channel=req.source, content=lead.initial_message)
    )
    db.add_audit(AuditEntry(lead_id=lead.id, client_id=lead.client_id, actor="system", action="ingest", detail={"source": req.source.value}))

    if not req.auto_process:
        return {"lead_id": lead.id, "status": lead.status.value, "processed": False}

    final = graph.process_lead(lead.id)
    out_lead = db.get_lead(lead.id)
    qual = db.latest_qualification(lead.id)
    return {
        "processed": True,
        "duplicate_of": final.get("duplicate_of"),
        "errors": final.get("errors", []),
        **_lead_summary(out_lead, qual),
    }


@app.post("/leads/{lead_id}/process")
def process(lead_id: str) -> Dict[str, Any]:
    if not db.get_lead(lead_id):
        raise HTTPException(404, "lead not found")
    final = graph.process_lead(lead_id)
    lead = db.get_lead(lead_id)
    qual = db.latest_qualification(lead_id)
    return {"errors": final.get("errors", []), **_lead_summary(lead, qual)}


@app.post("/leads/{lead_id}/approve")
def approve(lead_id: str, req: ApproveRequest) -> Dict[str, Any]:
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")
    if lead.status != LeadStatus.pending_approval:
        raise HTTPException(409, f"lead is not pending approval (status={lead.status.value})")

    if not req.approve:
        lead.status = LeadStatus.disqualified
        db.save_lead(lead)
        db.add_audit(AuditEntry(lead_id=lead_id, client_id=lead.client_id, actor=f"user:{req.actor}", action="approval_rejected"))
        return _lead_summary(db.get_lead(lead_id), db.latest_qualification(lead_id))

    graph.deliver(lead_id, override_message=req.message, actor=f"user:{req.actor}")
    return _lead_summary(db.get_lead(lead_id), db.latest_qualification(lead_id))


@app.get("/leads/{lead_id}")
def get_lead(lead_id: str) -> Dict[str, Any]:
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")
    qual = db.latest_qualification(lead_id)
    return {
        "lead": lead.model_dump(),
        "qualification": qual.model_dump() if qual else None,
        "conversation": [m.model_dump() for m in db.list_messages(lead_id)],
        "meeting": (db.get_meeting_for_lead(lead_id).model_dump() if db.get_meeting_for_lead(lead_id) else None),
        "audit_trail": [a.model_dump() for a in db.list_audit(lead_id)],
    }


@app.get("/clients/{client_id}/leads")
def list_client_leads(client_id: str) -> Dict[str, Any]:
    leads = db.list_leads(client_id)
    out = []
    for lead in leads:
        out.append(_lead_summary(lead, db.latest_qualification(lead.id)))
    return {"client_id": client_id, "count": len(out), "leads": out}


@app.post("/leads/{lead_id}/override")
def override(lead_id: str, req: OverrideRequest) -> Dict[str, Any]:
    qual = db.latest_qualification(lead_id)
    if not qual:
        raise HTTPException(404, "no qualification to override")
    before = {"label": qual.label.value, "total_score": qual.total_score}
    if req.label is not None:
        qual.label = req.label
    if req.total_score is not None:
        qual.total_score = max(0, min(100, req.total_score))
    qual.scoring_method = "human_override"
    db.save_qualification(qual)
    db.add_audit(AuditEntry(
        lead_id=lead_id, client_id=qual.client_id, actor=f"user:{req.actor}", action="override_qualification",
        detail={"before": before, "after": {"label": qual.label.value, "total_score": qual.total_score}, "reason": req.reason},
    ))
    return {"lead_id": lead_id, "label": qual.label.value, "total_score": qual.total_score}


@app.post("/clients/{client_id}/rag/index")
def rag_index(client_id: str, req: RagIndexRequest) -> Dict[str, Any]:
    if not db.get_client(client_id):
        raise HTTPException(404, "unknown client")
    n = rag.index_documents(client_id, req.docs)
    return {"client_id": client_id, "chunks_indexed": n, "rag_enabled": config.RAG_ENABLED}


@app.get("/clients/{client_id}/dashboard")
def dashboard(client_id: str) -> Dict[str, Any]:
    leads = db.list_leads(client_id)
    total = len(leads)
    by_label = {"Hot": 0, "Warm": 0, "Cold": 0}
    by_status: Dict[str, int] = {}
    verified = 0
    complete = 0
    response_secs: List[float] = []
    booked = 0

    for lead in leads:
        by_status[lead.status.value] = by_status.get(lead.status.value, 0) + 1
        if lead.verification_status and lead.verification_status.value == "verified":
            verified += 1
        enr = lead.enriched_data or {}
        if lead.title and enr.get("industry") and enr.get("company_size") and enr.get("region"):
            complete += 1
        if lead.first_response_at:
            try:
                dt = datetime.fromisoformat(lead.first_response_at) - datetime.fromisoformat(lead.created_at)
                response_secs.append(dt.total_seconds())
            except Exception:
                pass
        if lead.status == LeadStatus.meeting_booked:
            booked += 1
        q = db.latest_qualification(lead.id)
        if q:
            by_label[q.label.value] = by_label.get(q.label.value, 0) + 1

    pct = lambda n: round(100 * n / total, 1) if total else 0.0
    avg_resp = round(sum(response_secs) / len(response_secs), 1) if response_secs else None
    return {
        "client_id": client_id,
        "total_leads": total,
        "qualification_distribution": by_label,
        "status_distribution": by_status,
        "meeting_booking_rate_pct": pct(booked),
        "lead_to_verified_rate_pct": pct(verified),       # LTVL
        "data_completeness_pct": pct(complete),            # target 95%+
        "avg_first_response_seconds": avg_resp,
    }
