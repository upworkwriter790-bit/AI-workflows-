# LinkedIn Agent

A working multi-agent LinkedIn career-growth copilot: five specialist
agents (Profile, Content/Network, Job Discovery, Resume Tailoring,
Outreach), a central orchestrator that routes free-text requests to the
right agent, a FastAPI backend, a React/Vite web frontend, and the
original standalone CLI -- all sharing the same agent logic.

It's a **copilot, not an autopilot**: every agent researches and drafts;
nothing here ever posts, connects, sends, or applies on LinkedIn on its
own. That's a locked V1 decision, not a limitation to work around later.

## Architecture

```
linkedin-agent/
  backend/
    linkedin_agent/                # shared agent package (used by both API and CLI)
      config.py                    # env-driven settings
      client.py                    # Anthropic Messages API wrapper + web_search tool
      state.py                     # atomic JSON read/write, corrupt-file recovery
      handoff.py                   # cross-agent "HANDOFF:" ledger
      pipeline.py                  # application lifecycle state machine + diagnostics
      guardrails.py                # post-hoc fabrication checks
      prompts.py                   # the 5 subagent system prompts
      orchestrator.py              # unified status view across all 5 agents' state
      router.py                    # CENTRAL ORCHESTRATOR: routes a free-text task to the right agent
      execution_log.py             # run history (agent, status, duration) for the UI
      agents/
        profile_agent.py           # Subagent 1
        content_agent.py           # Subagent 2
        job_agent.py               # Subagent 3
        resume_agent.py            # Subagent 4
        outreach_agent.py          # Subagent 5
    app/
      main.py                      # FastAPI app: REST endpoints over linkedin_agent/
      schemas.py                   # request/response models
      logging_config.py
    cli.py                         # original standalone CLI entrypoint
    tests/                         # pytest suite (mocked LLM calls, no API key required)
    data/                          # created at runtime: profile.json, pipeline.json, etc.
    outputs/                       # every agent run also saves a timestamped .md report here
  frontend/
    src/
      api.ts                       # typed fetch client for the FastAPI backend
      components/                  # Orchestrator box, one form per agent, status dashboard, execution log
      App.tsx
```

### Why a router on top of the orchestrator

`orchestrator.py` deliberately does **not** auto-chain agents end-to-end --
the product's core rule is that a human executes every real LinkedIn
action (post, connect, apply, send) between agent runs. `router.py` is the
piece that still gives you a single front door: type a free-text request,
and one small LLM call (`config.ROUTER_MODEL`, defaults to Haiku) decides
which of the five agents should handle it and extracts whatever
parameters it can confidently find in your text -- matching the same
"never fabricate" guardrail philosophy used everywhere else in this repo,
it reports missing required fields instead of inventing them. The
frontend's "Ask the copilot" tab and the CLI's `orchestrate` subcommand
both use this.

### Data flow between agents

- `profile` writes `data/profile.json` (target role, audit, keywords).
  Every downstream agent reads it for context.
- Every agent's system prompt ends with a mandatory `HANDOFF:` line,
  parsed by `handoff.py` into `data/handoff_log.json`. Both `GET
  /api/handoffs` and the CLI's `status` command surface every unresolved
  handoff.
- `resume` writes directly into `pipeline.py`'s tracker (company, role,
  channel, JD snapshot, fit score).
- `pipeline.py` derives **Ghosted** status automatically from
  `last_update` age (default 21 days).
- `orchestrator.status_dict()` / `status_report()` compute referral vs.
  cold ghost rate and flag it as a signal when cold applications are
  dying off much faster than referred ones.

### Multi-provider LLM support

`client.py` doesn't hard-code Anthropic -- it's a facade over three
interchangeable backends, selected with one env var (`LLM_PROVIDER`), so a
single account being out of credits or unreachable is a config change, not
a code change:

| `LLM_PROVIDER` | Key env var | API used | Web search |
|---|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | Anthropic Messages API | native `web_search_20250305` tool |
| `openrouter` | `OPENROUTER_API_KEY` | OpenRouter (OpenAI-compatible) | `:online` model suffix (OpenRouter's web plugin) |
| `openai` | `OPENAI_API_KEY` | OpenAI Responses API | built-in `web_search_preview` tool |

Every agent and the router call the exact same `AgentClient.call(...)`
regardless of provider -- `client.py` normalizes each provider's citation
format into the same `[{"title", "url"}]` shape guardrails.py expects. If
a provider's response doesn't include parseable citations, sources come
back empty (logged, not guessed) so `guardrails.py`'s "no sources" warning
fires honestly instead of a fabricated source slipping through.

To switch, set `LLM_PROVIDER` and the matching key in `.env`:
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
```
Model defaults switch automatically with the provider (see
`config._DEFAULT_MODEL_BY_PROVIDER` / `_ROUTER_MODEL_BY_PROVIDER`); override
either with `LINKEDIN_AGENT_MODEL` / `LINKEDIN_AGENT_ROUTER_MODEL` if you
want a specific model on any provider.

## Requirements

- Python 3.10+
- Node.js 18+ (for the frontend)
- An API key for at least one provider: Anthropic (`ANTHROPIC_API_KEY`,
  default), OpenRouter (`OPENROUTER_API_KEY`), or OpenAI (`OPENAI_API_KEY`)

## Setup

### 1. Backend

```bash
cd linkedin-agent/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)   # or use python-dotenv / your shell's env loading
```

Run the API server:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive OpenAPI docs.

Run the test suite (fully offline -- the LLM client is mocked so no API
key or network access is required for tests):

```bash
pytest tests/ -v
```

### 2. Frontend

```bash
cd linkedin-agent/frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000` automatically (see `vite.config.ts`), so no CORS
setup is needed locally. For a production build, set
`VITE_API_BASE_URL` (see `frontend/.env.example`) to your deployed
backend's URL, then:

```bash
npm run build   # outputs frontend/dist -- serve with any static host
```

### 3. CLI (optional, works standalone)

```bash
cd linkedin-agent/backend
source venv/bin/activate
python cli.py profile --file my_profile.txt --role "SDE Internship, backend"
python cli.py orchestrate "find me remote backend intern roles at Stripe"
python cli.py status
```

Run `python cli.py --help` for every subcommand.

## Using the app

1. **Ask the copilot** tab -- describe what you want in plain English. The
   router picks an agent and tells you if it needs more information (it
   will never invent a resume, company, or profile you didn't give it).
2. Or use the dedicated tab per agent (**Profile**, **Content & Network**,
   **Job Discovery**, **Resume Tailoring**, **Outreach**) for full control
   over every field.
3. **Status & Pipeline** -- unified dashboard: profile summary, the
   application pipeline table (with one-click stage updates and CSV
   export), outreach log, and open cross-agent handoffs.
4. The **Agent execution** panel on the right shows a live history of
   every agent run this session (agent, status, duration), polling
   `GET /api/executions` every few seconds.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + whether an API key is configured |
| GET | `/api/agents` | Agent specs (description, required/optional fields) |
| POST | `/api/orchestrate` | Central router: `{task, overrides}` -> classify + dispatch |
| POST | `/api/agents/profile` | Run the Profile agent |
| POST | `/api/agents/content` | Run the Content/Network agent |
| POST | `/api/agents/content/log-post` | Log real post performance for the feedback loop |
| POST | `/api/agents/jobs` | Run the Job Discovery agent |
| POST | `/api/agents/resume` | Run the Resume Tailoring agent |
| POST | `/api/agents/outreach` | Run the Outreach agent |
| POST | `/api/agents/outreach/status` | Update a logged outreach attempt's status |
| GET | `/api/status` | Unified cross-agent status (JSON) |
| GET | `/api/executions` | Recent agent run history |
| GET/POST | `/api/pipeline`, `/api/pipeline/track`, `/api/pipeline/add` | Pipeline tracker |
| GET | `/api/pipeline/export` | CSV export |
| GET/POST | `/api/handoffs`, `/api/handoffs/{index}/resolve` | Cross-agent handoff ledger |
| GET | `/api/reports`, `/api/reports/{filename}` | Saved markdown reports |

## What this deliberately does NOT do

- No LinkedIn OAuth, scraping, or automated posting/connecting/applying --
  copilot-only until an official LinkedIn integration is secured.
- No persistent multi-user backend/auth -- this is a single-tenant app;
  every user shares the same `data/` directory. Add auth + per-user data
  isolation before exposing this beyond a single trusted user.
- No RAG/vector store -- context per call is short-lived (one profile, one
  JD, one target person at a time).

## Known limitations

- The fabrication guardrails (`guardrails.py`) are heuristic pattern
  matching, not a verifier model -- treat every guardrail "pass" as "no
  obvious red flag," not "verified."
- Web search coverage depends on what Anthropic's server-side search tool
  surfaces; a listing behind a login wall or a very new posting may not
  appear yet.
- The router's intent classification is a best-effort LLM call -- if it
  picks the wrong agent for an ambiguous request, use the dedicated
  per-agent tab/subcommand directly instead.
- `data/` is plain JSON on local disk, not a database -- fine for a single
  user, not for concurrent multi-user production use.
