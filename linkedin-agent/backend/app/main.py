"""
FastAPI backend for LinkedIn Agent.

Exposes the same five subagents + orchestrator/router + pipeline tracker
that linkedin_agent/ implements, as a REST API for the web frontend. This
is a thin HTTP layer -- all actual agent logic, guardrails, and state
management lives in linkedin_agent/; this module only does request
validation, dispatch, and error translation.

Nothing here ever calls a LinkedIn API -- per the locked V1 scope, this
system drafts/researches only. See linkedin_agent/README for details.
"""
import csv
import io
import logging
import os

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .logging_config import configure_logging
from . import schemas

from linkedin_agent import config, pipeline, orchestrator, handoff, state, router, execution_log
from linkedin_agent.client import AgentClient
from linkedin_agent.agents import content_agent, outreach_agent

configure_logging()
logger = logging.getLogger("linkedin_agent.api")

app = FastAPI(
    title="LinkedIn Agent API",
    description="Copilot API for LinkedIn profile, content, job search, resume, and outreach agents.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> AgentClient:
    try:
        return AgentClient()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.exception_handler(anthropic.APIError)
async def anthropic_error_handler(request, exc: anthropic.APIError):
    logger.error("anthropic API error: %s", exc)
    return _json_error(502, f"The LLM provider returned an error: {exc}")


@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc: Exception):
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return _json_error(500, "Internal server error. Check server logs for details.")


def _json_error(status_code: int, detail: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config.DEFAULT_MODEL, "api_key_configured": bool(config.ANTHROPIC_API_KEY)}


@app.get("/api/agents")
def list_agents():
    return {
        name: {
            "description": spec["description"],
            "required": spec["required"],
            "optional": spec["optional"],
        }
        for name, spec in router.AGENT_SPECS.items()
    }


# ---------------------------------------------------------------- orchestrator

@app.post("/api/orchestrate")
def orchestrate(req: schemas.OrchestrateRequest):
    client = get_client()
    try:
        result = router.route_and_run(client, req.task, overrides=req.overrides)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---------------------------------------------------------------- direct agent endpoints

@app.post("/api/agents/profile", response_model=schemas.AgentResult)
def run_profile(req: schemas.ProfileRequest):
    client = get_client()
    try:
        result = router.execute_agent(client, "profile", req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/agents/content", response_model=schemas.AgentResult)
def run_content(req: schemas.ContentRequest):
    client = get_client()
    try:
        result = router.execute_agent(client, "content", req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/agents/content/log-post")
def log_post(req: schemas.LogPostRequest):
    performance = {
        "likes": req.likes, "comments": req.comments, "shares": req.shares,
        "profile_views_after": req.profile_views, "connection_requests_after": req.connections,
    }
    content_agent.log_post_performance(req.idea, performance)
    return {"ok": True}


@app.post("/api/agents/jobs", response_model=schemas.AgentResult)
def run_jobs(req: schemas.JobsRequest):
    client = get_client()
    try:
        result = router.execute_agent(client, "jobs", req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/agents/resume", response_model=schemas.AgentResult)
def run_resume(req: schemas.ResumeRequest):
    client = get_client()
    try:
        result = router.execute_agent(client, "resume", req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/agents/outreach", response_model=schemas.AgentResult)
def run_outreach(req: schemas.OutreachRequest):
    client = get_client()
    try:
        result = router.execute_agent(client, "outreach", req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/agents/outreach/status")
def update_outreach_status(req: schemas.OutreachStatusRequest):
    ok = outreach_agent.update_status(req.company, req.target_person, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="No matching outreach entry found.")
    return {"ok": True}


# ---------------------------------------------------------------- status / execution log

@app.get("/api/status")
def get_status():
    return orchestrator.status_dict()


@app.get("/api/executions")
def get_executions(limit: int = 50):
    return execution_log.recent(limit=limit)


# ---------------------------------------------------------------- pipeline

@app.get("/api/pipeline")
def get_pipeline():
    items = pipeline.load()
    return {
        "items": [{**it, "display_stage": pipeline.display_stage(it), "is_stale": pipeline.is_stale(it)} for it in items],
        "stats": pipeline.summary_stats(items),
        "diagnostics": pipeline.diagnostics(items) if items else None,
    }


@app.post("/api/pipeline/track")
def track_pipeline(req: schemas.PipelineTrackRequest):
    try:
        old_stage, entry = pipeline.update_stage(req.id, req.stage, note=req.note)
    except ValueError as e:
        raise HTTPException(status_code=404 if "No pipeline entry" in str(e) else 400, detail=str(e))
    return {"old_stage": old_stage, "entry": entry}


@app.post("/api/pipeline/add")
def add_pipeline_entry(req: schemas.PipelineAddRequest):
    entry = pipeline.add_application(
        company=req.company, role=req.role, location=req.location,
        channel=req.channel, resume_version=req.resume_version or "manual",
        jd_snapshot=req.jd_snapshot or "", used_referral=req.referral, source="manual",
    )
    return entry


@app.get("/api/pipeline/export")
def export_pipeline():
    items = pipeline.load()
    fields = ["id", "company", "role", "location", "channel", "used_referral",
              "stage", "applied_date", "last_update", "fit_score", "source"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for it in items:
        writer.writerow(it)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pipeline_export.csv"},
    )


# ---------------------------------------------------------------- handoffs

@app.get("/api/handoffs")
def get_handoffs():
    log = state.load(handoff.HANDOFF_FILE, [])
    return [{**h, "index": i} for i, h in enumerate(log)]


@app.post("/api/handoffs/{index}/resolve")
def resolve_handoff(index: int):
    log = state.load(handoff.HANDOFF_FILE, [])
    if not (0 <= index < len(log)):
        raise HTTPException(status_code=404, detail=f"No handoff at index {index}")
    handoff.resolve_handoff(index)
    return {"ok": True}


# ---------------------------------------------------------------- saved reports

@app.get("/api/reports")
def list_reports():
    if not os.path.isdir(config.OUTPUT_DIR):
        return []
    files = sorted(
        (f for f in os.listdir(config.OUTPUT_DIR) if f.endswith(".md")),
        reverse=True,
    )
    return files


@app.get("/api/reports/{filename}")
def get_report(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(config.OUTPUT_DIR, safe_name)
    if not os.path.isfile(path) or not safe_name.endswith(".md"):
        raise HTTPException(status_code=404, detail="Report not found.")
    with open(path, "r") as f:
        content = f.read()
    return {"filename": safe_name, "content": content}
