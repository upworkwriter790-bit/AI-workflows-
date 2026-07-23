"""
Central configuration for LinkedIn Agent.
All values are overridable via environment variables so this can be
deployed the same way in dev, staging, or as a packaged CLI tool / API.
"""
import os

# --- LLM provider selection ---
# Which backend client.py talks to. Lets you switch providers with one env
# var if one account is out of credits/unreachable, without touching code.
#   anthropic  -- native Anthropic Messages API (default; full web_search tool support)
#   openrouter -- OpenAI-compatible API at openrouter.ai, routes to many models
#   openai     -- native OpenAI Responses API
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()

# --- Per-provider API keys ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# --- Per-provider default models (used unless LINKEDIN_AGENT_MODEL /
# LINKEDIN_AGENT_ROUTER_MODEL override them) ---
_DEFAULT_MODEL_BY_PROVIDER = {
    "anthropic": "claude-sonnet-5",
    "openrouter": "anthropic/claude-3.5-sonnet",
    "openai": "gpt-4o-mini",
}
_ROUTER_MODEL_BY_PROVIDER = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openrouter": "openai/gpt-4o-mini",
    "openai": "gpt-4o-mini",
}

# Main model used by all five agents.
DEFAULT_MODEL = os.environ.get(
    "LINKEDIN_AGENT_MODEL", _DEFAULT_MODEL_BY_PROVIDER.get(LLM_PROVIDER, "gpt-4o-mini")
)

# Cheaper/faster model used by the orchestrator's intent router for
# classifying free-text requests into an agent + params.
ROUTER_MODEL = os.environ.get(
    "LINKEDIN_AGENT_ROUTER_MODEL", _ROUTER_MODEL_BY_PROVIDER.get(LLM_PROVIDER, "gpt-4o-mini")
)

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


def configured_api_key() -> str | None:
    return {
        "anthropic": ANTHROPIC_API_KEY,
        "openrouter": OPENROUTER_API_KEY,
        "openai": OPENAI_API_KEY,
    }.get(LLM_PROVIDER)


def require_api_key():
    if LLM_PROVIDER not in _DEFAULT_MODEL_BY_PROVIDER:
        raise RuntimeError(
            f"LLM_PROVIDER={LLM_PROVIDER!r} is not recognized. Use one of: "
            f"{', '.join(_DEFAULT_MODEL_BY_PROVIDER)}."
        )
    env_var = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY"}[LLM_PROVIDER]
    if not configured_api_key():
        raise RuntimeError(
            f"LLM_PROVIDER is set to {LLM_PROVIDER!r} but {env_var} is not set. "
            f"Export it in your shell or put it in a .env file (see .env.example) "
            f"before running any agent command."
        )
