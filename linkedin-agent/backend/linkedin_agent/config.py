"""
Central configuration for LinkedIn Agent.
All values are overridable via environment variables so this can be
deployed the same way in dev, staging, or as a packaged CLI tool / API.
"""
import os

# --- Anthropic API ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Default to Sonnet 5 for the best cost/quality balance across all five
# subagents. Override per-deploy with LINKEDIN_AGENT_MODEL.
DEFAULT_MODEL = os.environ.get("LINKEDIN_AGENT_MODEL", "claude-sonnet-5")

# Cheaper/faster model used by the orchestrator's intent router for
# classifying free-text requests into an agent + params. Falls back to
# DEFAULT_MODEL if not set.
ROUTER_MODEL = os.environ.get("LINKEDIN_AGENT_ROUTER_MODEL", "claude-haiku-4-5-20251001")

# --- Storage ---
# All user data (profile, pipeline tracker, job cache, content log,
# outreach log, handoff notes) lives here as plain JSON files. No DB
# dependency in V1 -- keeps the copilot fully local / easy to inspect.
DATA_DIR = os.environ.get("LINKEDIN_AGENT_DATA_DIR", os.path.join(os.getcwd(), "data"))
OUTPUT_DIR = os.environ.get("LINKEDIN_AGENT_OUTPUT_DIR", os.path.join(os.getcwd(), "outputs"))

# --- Pipeline tracking rules (from PRD acceptance criteria) ---
STALE_DAYS = int(os.environ.get("LINKEDIN_AGENT_STALE_DAYS", "21"))  # 3 weeks

# --- API server ---
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("LINKEDIN_AGENT_CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

# --- Guardrails ---
# The PRD's #1 rollback trigger is fabrication (invented listings, salaries,
# metrics). We can't fully guarantee an LLM won't hallucinate, but we can
# make the failure loud instead of silent: every job-discovery and resume
# report is scanned for basic red flags before being shown to the user.
FABRICATION_WARNING_BANNER = (
    "\n\n---\n"
    "REVIEW REQUIRED: This output was flagged by an automated fabrication "
    "check (see warnings above). Verify every specific number, deadline, "
    "and listing against the live source before acting on it.\n"
)


def require_api_key():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it in your shell or put it "
            "in a .env file (see .env.example) before running any agent command."
        )
