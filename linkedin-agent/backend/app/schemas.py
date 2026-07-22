"""Pydantic request/response models for the LinkedIn Agent API."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Free-text description of what you want done.")
    overrides: Dict[str, Any] = Field(default_factory=dict, description="Explicit field values, merged over anything the router extracts from `task`.")


class ProfileRequest(BaseModel):
    profile_text: str = Field(..., min_length=1)
    target_role: str = Field(..., min_length=1)
    reference_profiles: Optional[str] = None


class ContentRequest(BaseModel):
    target_companies: Optional[str] = None
    prior_post_performance: Optional[str] = None


class LogPostRequest(BaseModel):
    idea: str = Field(..., min_length=1)
    likes: int = 0
    comments: int = 0
    shares: int = 0
    profile_views: int = 0
    connections: int = 0


class JobsRequest(BaseModel):
    target_role: Optional[str] = None
    geography: str = "remote"
    experience_level: str = "not specified"
    target_companies: Optional[str] = None
    active_only: bool = False


class ResumeRequest(BaseModel):
    master_resume_text: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1)
    channel: str = Field("cold", pattern="^(cold|referral)$")
    used_referral: bool = False
    log_to_pipeline: bool = True


class OutreachRequest(BaseModel):
    company: str = Field(..., min_length=1)
    target_person: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    resume_summary: Optional[str] = None
    relationship_warmth: str = Field("cold", pattern="^(cold|warmed-up|referral-available)$")
    referral_available: bool = False


class OutreachStatusRequest(BaseModel):
    company: str = Field(..., min_length=1)
    target_person: str = Field(..., min_length=1)
    status: str = Field(..., pattern="^(sent|responded_positive|responded_negative|no_response|closed)$")


class PipelineTrackRequest(BaseModel):
    id: str = Field(..., min_length=1)
    stage: str
    note: Optional[str] = None


class PipelineAddRequest(BaseModel):
    company: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    channel: str = Field("cold", pattern="^(cold|referral)$")
    referral: bool = False
    resume_version: Optional[str] = "manual"
    jd_snapshot: Optional[str] = ""


class HandoffResolveRequest(BaseModel):
    index: int


class AgentResult(BaseModel):
    report: str
    sources: List[Dict[str, Any]] = []
    path: Optional[str] = None
    handoff: Optional[str] = None
    warnings: List[str] = []
    pipeline_entry: Optional[Dict[str, Any]] = None
