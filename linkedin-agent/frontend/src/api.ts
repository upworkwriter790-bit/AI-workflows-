import type {
  AgentSpecs,
  AgentResult,
  OrchestrateResponse,
  ExecutionEntry,
  PipelineResponse,
  StatusResponse,
  HandoffEntry,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export const api = {
  health: () => request<{ status: string; provider: string; model: string; api_key_configured: boolean }>("/api/health"),
  listAgents: () => request<AgentSpecs>("/api/agents"),

  orchestrate: (task: string, overrides: Record<string, unknown> = {}) =>
    post<OrchestrateResponse>("/api/orchestrate", { task, overrides }),

  runProfile: (body: { profile_text: string; target_role: string; reference_profiles?: string }) =>
    post<AgentResult>("/api/agents/profile", body),

  runContent: (body: { target_companies?: string; prior_post_performance?: string }) =>
    post<AgentResult>("/api/agents/content", body),

  logPost: (body: { idea: string; likes: number; comments: number; shares: number; profile_views: number; connections: number }) =>
    post<{ ok: boolean }>("/api/agents/content/log-post", body),

  runJobs: (body: {
    target_role?: string;
    geography: string;
    experience_level: string;
    target_companies?: string;
    active_only: boolean;
  }) => post<AgentResult>("/api/agents/jobs", body),

  runResume: (body: {
    master_resume_text: string;
    company: string;
    role: string;
    location: string;
    job_description: string;
    channel: string;
    used_referral: boolean;
    log_to_pipeline: boolean;
  }) => post<AgentResult>("/api/agents/resume", body),

  runOutreach: (body: {
    company: string;
    target_person: string;
    role: string;
    resume_summary?: string;
    relationship_warmth: string;
    referral_available: boolean;
  }) => post<AgentResult>("/api/agents/outreach", body),

  updateOutreachStatus: (body: { company: string; target_person: string; status: string }) =>
    post<{ ok: boolean }>("/api/agents/outreach/status", body),

  getStatus: () => request<StatusResponse>("/api/status"),
  getExecutions: () => request<ExecutionEntry[]>("/api/executions"),
  getPipeline: () => request<PipelineResponse>("/api/pipeline"),

  trackPipeline: (body: { id: string; stage: string; note?: string }) =>
    post<{ old_stage: string; entry: unknown }>("/api/pipeline/track", body),

  addPipeline: (body: {
    company: string;
    role: string;
    location: string;
    channel: string;
    referral: boolean;
  }) => post<unknown>("/api/pipeline/add", body),

  getHandoffs: () => request<HandoffEntry[]>("/api/handoffs"),
  resolveHandoff: (index: number) => post<{ ok: boolean }>(`/api/handoffs/${index}/resolve`, {}),

  exportPipelineUrl: () => `${BASE}/api/pipeline/export`,
};

export { ApiError };
