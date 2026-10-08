"""LangGraph workflow for the Lead Response & Qualification Agent.

Flow:
  load_lead_and_config -> dedup_and_verify -> retrieve_rag_context ->
  parse_and_enrich -> qualify_lead -> decide_next_step -> draft_response ->
  [approval gate] -> send_and_log -> [schedule gate] -> schedule_meeting -> END

Human-in-the-loop: when the client requires approval, the graph stops after
drafting (status = pending_approval). Delivery resumes via deliver() from the
/approve endpoint, reusing the same send/schedule node code (no LLM re-run).
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app import bant, crm, db, enrich, messaging, rag, routing, scheduler
from app.models import (
    AuditEntry,
    BANTConfig,
    Channel,
    Client,
    ICPConfig,
    Label,
    Lead,
    LeadStatus,
    NextStep,
    QualificationResult,
    VerificationStatus,
)


class AgentState(TypedDict, total=False):
    lead_id: str
    client_id: str
    lead: Lead
    client: Client
    icp: ICPConfig
    bant_config: BANTConfig
    rag_context: str
    qualification: Optional[QualificationResult]
    draft: Optional[str]
    needs_human_approval: bool
    approved: bool
    duplicate_of: Optional[str]
    errors: List[str]


def _audit(lead_id, client_id, action, detail=None, actor="agent"):
    db.add_audit(AuditEntry(lead_id=lead_id, client_id=client_id, actor=actor, action=action, detail=detail or {}))


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def load_lead_and_config(state: AgentState) -> AgentState:
    lead = db.get_lead(state["lead_id"])
    if not lead:
        state["errors"] = state.get("errors", []) + [f"lead {state['lead_id']} not found"]
        return state
    client = db.get_client(lead.client_id)
    icp = db.get_icp_for_client(lead.client_id) or ICPConfig(client_id=lead.client_id)
    bant_cfg = db.get_bant_for_client(lead.client_id) or BANTConfig(client_id=lead.client_id)

    lead.status = LeadStatus.qualifying
    db.save_lead(lead)

    state.update(
        lead=lead,
        client=client,
        client_id=lead.client_id,
        icp=icp,
        bant_config=bant_cfg,
        needs_human_approval=bool(client and client.require_human_approval),
        errors=state.get("errors", []),
    )
    _audit(lead.id, lead.client_id, "load_lead_and_config")
    return state


def dedup_and_verify(state: AgentState) -> AgentState:
    """QC gauntlet: verify contactability + dedup before spending LLM effort."""
    lead = state["lead"]
    if not lead.email and lead.phone:
        # Phone-native channel (e.g. WhatsApp): reachable without an email address.
        lead.verification_status = VerificationStatus.verified
    else:
        lead.verification_status = enrich.verify_email(lead.email)

    dup = crm.find_duplicate(lead)
    if dup:
        # Fold the new message into the original thread; do not re-qualify or auto-reply.
        state["duplicate_of"] = dup.id
        for m in db.list_messages(lead.id):
            m.lead_id = dup.id
            db.save_message(m)
        lead.status = LeadStatus.duplicate
        _audit(lead.id, lead.client_id, "duplicate_detected", {"duplicate_of": dup.id})
        _audit(dup.id, dup.client_id, "duplicate_message_merged", {"from_lead": lead.id})

    db.save_lead(lead)
    _audit(lead.id, lead.client_id, "verify_email", {"status": lead.verification_status.value})
    state["lead"] = lead
    return state


def retrieve_rag_context(state: AgentState) -> AgentState:
    client = state["client"]
    name = client.name if client else state["client_id"]
    query = f"ICP, ideal customer profile, qualification criteria and sales playbook for {name}"
    state["rag_context"] = rag.retrieve(state["client_id"], query, k=5)
    return state


def parse_and_enrich(state: AgentState) -> AgentState:
    lead = state["lead"]
    lead.enriched_data = enrich.enrich_lead(lead)
    db.save_lead(lead)
    state["lead"] = lead
    _audit(lead.id, lead.client_id, "parse_and_enrich", {"enriched": lead.enriched_data})
    return state


def qualify_lead(state: AgentState) -> AgentState:
    lead, icp, cfg = state["lead"], state["icp"], state["bant_config"]
    qual = bant.qualify(lead, icp, cfg, state.get("rag_context", ""))
    db.save_qualification(qual)

    lead.status = LeadStatus.qualified
    db.save_lead(lead)

    state["qualification"] = qual
    _audit(
        lead.id, lead.client_id, "qualify_lead",
        {
            "label": qual.label.value, "total_score": qual.total_score,
            "fit_score": qual.fit_score, "intent_score": qual.intent_score,
            "bant": qual.bant_scores(), "method": qual.scoring_method,
        },
    )
    return state


def decide_next_step(state: AgentState) -> AgentState:
    lead, client = state["lead"], state["client"]
    qual = state["qualification"]

    # Route only leads worth a human; owner may still be assigned for nurture.
    owner_id = routing.assign_owner(client, lead) if client else None
    lead.owner_id = owner_id
    if qual.next_step == NextStep.book_meeting and owner_id is None:
        lead.status = LeadStatus.needs_manual_routing
        _audit(lead.id, lead.client_id, "routing_ambiguous", {"reason": "no matching rep"})
    db.save_lead(lead)
    state["lead"] = lead
    _audit(lead.id, lead.client_id, "decide_next_step", {"owner_id": owner_id, "next_step": qual.next_step.value})
    return state


def draft_response_node(state: AgentState) -> AgentState:
    lead, qual = state["lead"], state["qualification"]
    draft = bant.draft_response(lead, qual, state.get("rag_context", ""))
    lead.draft_response = draft
    db.save_lead(lead)
    state["draft"] = draft
    _audit(lead.id, lead.client_id, "draft_response", {"needs_human_approval": state.get("needs_human_approval", False)})
    return state


def await_approval(state: AgentState) -> AgentState:
    lead = state["lead"]
    lead.status = LeadStatus.pending_approval
    db.save_lead(lead)
    _audit(lead.id, lead.client_id, "pending_human_approval")
    return state


def send_and_log(state: AgentState) -> AgentState:
    lead, qual = state["lead"], state["qualification"]
    draft = state.get("draft") or lead.draft_response or ""
    if not draft:
        state["errors"] = state.get("errors", []) + ["no draft to send"]
        return state

    meeting_link = None
    if qual and qual.next_step == NextStep.book_meeting:
        meeting = scheduler.propose_meeting(state["client"], lead)
        meeting_link = meeting.calendar_link
    message = draft.replace("[MEETING_LINK]", meeting_link or (state["client"].default_calendar_link if state.get("client") else "") or "")

    channel = Channel.email if lead.source in (Channel.email, Channel.web_form, Channel.linkedin) else Channel.whatsapp
    messaging.send_message(lead, channel, message)

    from datetime import datetime, timezone
    if not lead.first_response_at:
        lead.first_response_at = datetime.now(timezone.utc).isoformat()
    lead.status = LeadStatus.meeting_booked if (qual and qual.next_step == NextStep.book_meeting) else (
        LeadStatus.disqualified if (qual and qual.next_step == NextStep.disqualify) else LeadStatus.responded
    )
    db.save_lead(lead)
    crm.upsert_lead(lead, qual)
    state["lead"] = lead
    _audit(lead.id, lead.client_id, "send_and_log", {"channel": channel.value, "status": lead.status.value})
    return state


def schedule_meeting(state: AgentState) -> AgentState:
    lead = state["lead"]
    meeting = db.get_meeting_for_lead(lead.id)
    _audit(lead.id, lead.client_id, "meeting_proposed", {"link": meeting.calendar_link if meeting else None})
    return state


# --------------------------------------------------------------------------- #
# Conditional routers
# --------------------------------------------------------------------------- #
def _after_dedup(state: AgentState) -> str:
    return END if state.get("duplicate_of") else "retrieve_rag_context"


def _after_draft(state: AgentState) -> str:
    if state.get("needs_human_approval") and not state.get("approved"):
        return "await_approval"
    return "send_and_log"


def _after_send(state: AgentState) -> str:
    qual = state.get("qualification")
    if qual and qual.next_step == NextStep.book_meeting and state["lead"].status == LeadStatus.meeting_booked:
        return "schedule_meeting"
    return END


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_lead_and_config", load_lead_and_config)
    g.add_node("dedup_and_verify", dedup_and_verify)
    g.add_node("retrieve_rag_context", retrieve_rag_context)
    g.add_node("parse_and_enrich", parse_and_enrich)
    g.add_node("qualify_lead", qualify_lead)
    g.add_node("decide_next_step", decide_next_step)
    g.add_node("draft_response", draft_response_node)
    g.add_node("await_approval", await_approval)
    g.add_node("send_and_log", send_and_log)
    g.add_node("schedule_meeting", schedule_meeting)

    g.set_entry_point("load_lead_and_config")
    g.add_edge("load_lead_and_config", "dedup_and_verify")
    g.add_conditional_edges("dedup_and_verify", _after_dedup, {"retrieve_rag_context": "retrieve_rag_context", END: END})
    g.add_edge("retrieve_rag_context", "parse_and_enrich")
    g.add_edge("parse_and_enrich", "qualify_lead")
    g.add_edge("qualify_lead", "decide_next_step")
    g.add_edge("decide_next_step", "draft_response")
    g.add_conditional_edges("draft_response", _after_draft, {"await_approval": "await_approval", "send_and_log": "send_and_log"})
    g.add_edge("await_approval", END)
    g.add_conditional_edges("send_and_log", _after_send, {"schedule_meeting": "schedule_meeting", END: END})
    g.add_edge("schedule_meeting", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def process_lead(lead_id: str) -> AgentState:
    """Run the full graph for a lead."""
    init: AgentState = {"lead_id": lead_id, "approved": False, "errors": []}
    return get_graph().invoke(init)


def deliver(lead_id: str, override_message: Optional[str] = None, actor: str = "agent") -> AgentState:
    """Resume delivery after human approval (reuses send/schedule nodes)."""
    lead = db.get_lead(lead_id)
    if not lead:
        return {"errors": [f"lead {lead_id} not found"]}
    if override_message is not None:
        lead.draft_response = override_message
        db.save_lead(lead)
    qual = db.latest_qualification(lead_id)
    client = db.get_client(lead.client_id)
    state: AgentState = {
        "lead_id": lead_id, "lead": lead, "client": client, "client_id": lead.client_id,
        "qualification": qual, "draft": lead.draft_response, "approved": True, "errors": [],
    }
    _audit(lead_id, lead.client_id, "human_approved", {"edited": override_message is not None}, actor=actor)
    state = send_and_log(state)
    if _after_send(state) == "schedule_meeting":
        state = schedule_meeting(state)
    return state
