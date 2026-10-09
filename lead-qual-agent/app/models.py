"""Core data models (the real contracts the agent operates on).

These mirror the PRD data design: Client, ICPConfig, BANTConfig, Lead,
ConversationMessage, QualificationResult, plus supporting Rep / Meeting /
AuditEntry records needed for routing, booking and the audit trail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Channel(str, Enum):
    web_form = "web_form"
    email = "email"
    whatsapp = "whatsapp"
    linkedin = "linkedin"
    system = "system"


class LeadStatus(str, Enum):
    new = "new"
    qualifying = "qualifying"
    qualified = "qualified"
    pending_approval = "pending_approval"
    responded = "responded"
    meeting_proposed = "meeting_proposed"
    meeting_booked = "meeting_booked"
    nurture = "nurture"
    disqualified = "disqualified"
    needs_manual_routing = "needs_manual_routing"
    duplicate = "duplicate"


class Label(str, Enum):
    hot = "Hot"
    warm = "Warm"
    cold = "Cold"


class NextStep(str, Enum):
    book_meeting = "book_meeting"
    nurture = "nurture"
    disqualify = "disqualify"


class VerificationStatus(str, Enum):
    verified = "verified"
    catch_all_risk = "catch_all_risk"
    bounce_risk = "bounce_risk"
    scrubbed = "scrubbed"


class MessageRole(str, Enum):
    lead = "lead"
    agent = "agent"
    system = "system"


# --------------------------------------------------------------------------- #
# Config entities
# --------------------------------------------------------------------------- #
class Rep(BaseModel):
    id: str
    name: str
    email: str
    regions: List[str] = Field(default_factory=list)   # e.g. ["IN", "SG"]
    segments: List[str] = Field(default_factory=list)   # e.g. ["MM", "Enterprise"]
    calendar_link: Optional[str] = None
    active: bool = True


class Client(BaseModel):
    id: str = Field(default_factory=lambda: _id("client"))
    name: str
    industry: Optional[str] = None
    timezone: str = "UTC"
    crm_provider: str = "mock"          # mock | hubspot | pipedrive | salesforce
    routing_strategy: str = "round_robin"  # round_robin | territory | segment
    require_human_approval: bool = False
    default_calendar_link: Optional[str] = None
    reps: List[Rep] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class ICPConfig(BaseModel):
    id: str = Field(default_factory=lambda: _id("icp"))
    client_id: str
    target_industries: List[str] = Field(default_factory=list)
    exclude_industries: List[str] = Field(default_factory=list)
    company_size_min: int = 0
    company_size_max: int = 1_000_000
    target_regions: List[str] = Field(default_factory=list)
    target_titles: List[str] = Field(default_factory=list)
    ideal_use_cases: List[str] = Field(default_factory=list)


class BANTConfig(BaseModel):
    """Per-client weighted BANT model. Tunable without code changes."""
    id: str = Field(default_factory=lambda: _id("bant"))
    client_id: str
    weights: Dict[str, float] = Field(
        default_factory=lambda: {"budget": 0.15, "authority": 0.25, "need": 0.35, "timeline": 0.25}
    )
    score_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {"hot_min": 0.70, "warm_min": 0.40}
    )
    rules: Dict[str, bool] = Field(
        default_factory=lambda: {
            "auto_disqualify_if_need_0": True,
            "require_authority_ge_1": True,
        }
    )
    # Blend of ICP fit vs BANT when computing total_score (0..1, must sum to 1).
    fit_weight: float = 0.4
    bant_weight: float = 0.6


# --------------------------------------------------------------------------- #
# Lead / conversation entities
# --------------------------------------------------------------------------- #
class Lead(BaseModel):
    id: str = Field(default_factory=lambda: _id("lead"))
    client_id: str
    source: Channel = Channel.web_form
    name: str = ""
    email: str = ""
    company: str = ""
    title: str = ""
    phone: Optional[str] = None
    website: Optional[str] = None
    initial_message: str = ""
    enriched_data: Dict[str, Any] = Field(default_factory=dict)

    # Provenance / QC (Pillar 3 pattern)
    source_tool: Optional[str] = None
    verification_status: Optional[VerificationStatus] = None

    status: LeadStatus = LeadStatus.new
    owner_id: Optional[str] = None
    draft_response: Optional[str] = None

    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    first_response_at: Optional[str] = None


class ConversationMessage(BaseModel):
    id: str = Field(default_factory=lambda: _id("msg"))
    lead_id: str
    role: MessageRole
    channel: Channel
    content: str
    timestamp: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Qualification output
# --------------------------------------------------------------------------- #
class BANTDimension(BaseModel):
    score: int = 0                       # 0..3
    reasons: List[str] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)


class QualificationResult(BaseModel):
    id: str = Field(default_factory=lambda: _id("qual"))
    lead_id: str
    client_id: str

    budget: BANTDimension = Field(default_factory=BANTDimension)
    authority: BANTDimension = Field(default_factory=BANTDimension)
    need: BANTDimension = Field(default_factory=BANTDimension)
    timeline: BANTDimension = Field(default_factory=BANTDimension)

    fit_score: int = 0                   # 0..100  (ICP match, computed in code)
    intent_score: int = 0                # 0..100  (weighted BANT)
    total_score: int = 0                 # 0..100  (blend)
    label: Label = Label.cold
    next_step: NextStep = NextStep.nurture
    reasoning: str = ""

    scoring_method: str = "rule_based"   # rule_based | llm | llm+rules ; future: ml
    model_version: str = "bant-v1"
    created_at: str = Field(default_factory=_now)

    def bant_scores(self) -> Dict[str, int]:
        return {
            "budget": self.budget.score,
            "authority": self.authority.score,
            "need": self.need.score,
            "timeline": self.timeline.score,
        }


# --------------------------------------------------------------------------- #
# Supporting records
# --------------------------------------------------------------------------- #
class Meeting(BaseModel):
    id: str = Field(default_factory=lambda: _id("mtg"))
    lead_id: str
    client_id: str
    owner_id: Optional[str] = None
    calendar_link: str = ""
    scheduled_for: Optional[str] = None
    status: str = "proposed"             # proposed | booked
    created_at: str = Field(default_factory=_now)


class AuditEntry(BaseModel):
    id: str = Field(default_factory=lambda: _id("audit"))
    lead_id: Optional[str] = None
    client_id: Optional[str] = None
    actor: str = "agent"                 # agent | system | user:<email>
    action: str = ""
    detail: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_now)
