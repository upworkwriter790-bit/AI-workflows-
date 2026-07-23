export interface AgentSpec {
  description: string;
  required: string[];
  optional: string[];
}

export type AgentSpecs = Record<string, AgentSpec>;

export interface AgentResult {
  report: string;
  sources: { title: string | null; url: string }[];
  path: string | null;
  handoff: string | null;
  warnings: string[];
  pipeline_entry: Record<string, unknown> | null;
}

export interface OrchestrateNeedsInput {
  status: "needs_input";
  agent: string;
  description: string;
  extracted_params: Record<string, unknown>;
  missing: string[];
  reasoning: string;
}

export interface OrchestrateCompleted {
  status: "completed";
  agent: string;
  reasoning: string;
  result: AgentResult;
}

export type OrchestrateResponse = OrchestrateNeedsInput | OrchestrateCompleted;

export interface ExecutionEntry {
  id: number;
  agent: string;
  source: "orchestrator" | "direct";
  input_summary: string;
  status: "running" | "success" | "error";
  started_at: string;
  finished_at: string | null;
  duration_s: number | null;
  error: string | null;
}

export interface PipelineItem {
  id: string;
  company: string;
  role: string;
  location: string;
  channel: string;
  used_referral: boolean;
  stage: string;
  display_stage: string;
  is_stale: boolean;
  applied_date: string;
  last_update: string;
  fit_score: number | null;
  source: string;
}

export interface PipelineResponse {
  items: PipelineItem[];
  stats: Record<string, number>;
  diagnostics: {
    referral_count: number;
    cold_count: number;
    referral_ghost_rate_pct: number | null;
    cold_ghost_rate_pct: number | null;
    rejection_clusters: Record<string, number>;
  } | null;
}

export interface HandoffEntry {
  index: number;
  from_agent: string;
  note: string;
  created_at: string;
  resolved: boolean;
  resolved_at?: string;
}

export interface StatusResponse {
  profile: { target_role?: string; updated_at?: string } | null;
  pipeline: PipelineResponse & { stats: Record<string, number> };
  outreach: {
    company: string;
    target_person: string;
    role: string;
    status: string;
    date: string;
  }[];
  handoffs: HandoffEntry[];
}
