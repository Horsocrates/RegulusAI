const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// === Types ===

export type RunStatus = "created" | "running" | "paused" | "completed" | "failed" | "stopped";

export interface CostInfo {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  spent_cost: number;
  estimated_remaining: number;
  estimated_total: number;
  currency: string;
}

export interface LabRun {
  id: number;
  name: string;
  dataset: string;
  provider: string;
  total_questions: number;
  num_steps: number;
  concurrency: number;
  status: RunStatus;
  current_step: number;
  completed_questions: number;
  valid_count: number;
  correct_count: number;
  total_time: number;
  progress_percent: number;
  input_tokens: number;
  output_tokens: number;
  source_run_id: number | null;
  cost: CostInfo | null;
  mode: string;              // "v1" | "v2"
  reasoning_model: string;   // "deepseek", "claude-thinking", "openai-reasoning"
  created_at: string;
  updated_at: string;
}

export interface LabRunStats {
  run_id: number;
  status: RunStatus;
  total_questions: number;
  completed: number;
  passed: number;
  failed: number;
  fixed: number;
  accuracy: number;
  avg_time_seconds: number;
  total_time_seconds: number;
  cost_usd: number;
  tokens: { input: number; output: number };
  eta_seconds: number;
  progress_pct: number;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  total_questions: number;
  categories: string[];
  type: string;
}

export interface CreateRunRequest {
  name: string;
  dataset: string;
  total_questions: number;
  num_steps: number;
  concurrency: number;
  provider?: string;
  category?: string | null;
  source_run_id?: number | null;
  model_version?: string;
  mode?: string;               // "v1" | "v2"
  reasoning_model?: string;    // For v2: "deepseek", "claude-thinking", "openai-reasoning"
}

export const REASONING_MODELS = [
  { value: "deepseek",          label: "DeepSeek-R1",              trace: "Full CoT" },
  { value: "claude-thinking",   label: "Claude Extended Thinking", trace: "Summary" },
  { value: "openai-reasoning",  label: "OpenAI (Stub)",            trace: "None" },
] as const;

// === API Functions ===

export async function getLabRuns(): Promise<LabRun[]> {
  const res = await fetch(`${API_URL}/api/lab/runs`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getLabRun(id: number): Promise<LabRun> {
  const res = await fetch(`${API_URL}/api/lab/runs/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createLabRun(req: CreateRunRequest): Promise<LabRun> {
  const res = await fetch(`${API_URL}/api/lab/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail;
    if (Array.isArray(detail)) {
      throw new Error(detail.map((d: { msg: string }) => d.msg).join(", "));
    }
    throw new Error(detail || `Failed to create run: ${res.status}`);
  }
  return res.json();
}

export async function deleteLabRun(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/runs/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function stopLabRun(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/runs/${id}/stop`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function continueLabRun(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/runs/${id}/continue`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function getRunStats(id: number): Promise<LabRunStats> {
  const res = await fetch(`${API_URL}/api/lab/runs/${id}/stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getDatasets(): Promise<{ datasets: Dataset[] }> {
  const res = await fetch(`${API_URL}/api/lab/datasets`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function retryFailed(runId: number, opts: {
  concurrency?: number;
  num_steps?: number;
  model_version?: string;
} = {}): Promise<LabRun> {
  const res = await fetch(`${API_URL}/api/lab/runs/${runId}/retry-failed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === V2 Types ===

export interface DashboardStats {
  total_runs: number;
  completed_runs: number;
  running_runs: number;
  total_questions_answered: number;
  overall_accuracy: number;
  total_correct: number;
  total_wrong: number;
  total_cost: number;
  total_time_seconds: number;
}

export interface V2RunStats {
  total_questions: number;
  completed_questions: number;
  correct_count: number;
  wrong_count: number;
  partial_count: number;
  error_count: number;
  total_time_ms: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost: number;
  avg_time_per_question_ms: number;
  avg_tokens_per_question: number;
  avg_cost_per_question: number;
  accuracy: number;
  by_domain: Record<string, DomainStats>;
  by_team: Record<string, TeamStats>;
}

export interface DomainStats {
  domain: string;
  total: number;
  correct: number;
  wrong: number;
  partial: number;
  error: number;
  accuracy: number;
  avg_time_ms: number;
}

export interface TeamStats {
  team_index: number;
  total: number;
  correct: number;
  wrong: number;
  accuracy: number;
  avg_time_ms: number;
}

export interface AnalysisReport {
  run_id: string;
  generated_at: string;
  summary: {
    accuracy: number;
    total_questions: number;
    correct: number;
    wrong: number;
    partial: number;
    error: number;
    total_cost: number;
    total_time_seconds: number;
    avg_time_per_question: number;
  };
  domain_analysis: {
    domain: string;
    accuracy: number;
    total: number;
    correct: number;
    wrong: number;
    common_errors: string[];
  }[];
  team_analysis: {
    team_index: number;
    total: number;
    correct: number;
    accuracy: number;
    performance_trend: string;
  }[];
  failure_patterns: {
    pattern_type: string;
    description: string;
    affected_questions: string[];
    frequency: number;
    suggested_fix: string | null;
  }[];
  recommendations: string[];
}

export interface BenchmarkSummary {
  id: string;
  name: string;
  description: string;
  source: string;
  total_examples: number;
  domains_count: number;
  version: string;
}

export interface BenchmarkDetail extends BenchmarkSummary {
  domains: string[];
}

// === V2 API Functions ===

export async function getDashboard(): Promise<DashboardStats> {
  const res = await fetch(`${API_URL}/api/lab/v2/dashboard`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getV2RunStats(runId: string): Promise<V2RunStats> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getV2DomainStats(runId: string): Promise<DomainStats[]> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/stats/domains`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getV2TeamStats(runId: string): Promise<TeamStats[]> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/stats/teams`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAnalysisReport(runId: string): Promise<AnalysisReport> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/report`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function exportRunResults(runId: string, format: "json" | "csv" = "json"): Promise<Blob> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/export?format=${format}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.blob();
}

export async function getBenchmarks(): Promise<BenchmarkSummary[]> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getBenchmarkDetail(benchmarkId: string): Promise<BenchmarkDetail> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === V2 Test Config & Run Creation ===

export interface CreateTestConfigRequest {
  name: string;
  benchmark: string;
  domains?: string[];
  domain_limits?: Record<string, number>;
  question_count?: number;
  shuffle?: boolean;
  questions_per_team?: number;
  steps_count?: number;
  team_id?: string;
  judge_config?: { strict_mode?: boolean };
}

export interface TestConfigResponse {
  id: string;
  name: string;
  description: string;
  created_at: string;
  benchmark: string;
  domains: string[];
  domain_limits: Record<string, number>;
  question_count: number | null;
  shuffle: boolean;
  questions_per_team: number;
  steps_count: number;
  team_id: string;
  judge_config: Record<string, unknown>;
}

export interface TestRunResponse {
  id: string;
  config_id: string;
  status: string;
  total_questions: number;
  current_question_index: number;
  current_team_index: number;
  started_at: string | null;
  completed_at: string | null;
  progress_percent: number;
}

export async function createTestConfig(req: CreateTestConfigRequest): Promise<TestConfigResponse> {
  const res = await fetch(`${API_URL}/api/lab/tests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Failed to create test config: ${res.status}`);
  }
  return res.json();
}

export async function startTestRun(configId: string): Promise<TestRunResponse> {
  const res = await fetch(`${API_URL}/api/lab/tests/${configId}/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Failed to start run: ${res.status}`);
  }
  return res.json();
}

export async function executeTestRun(runId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/execute`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Failed to execute run: ${res.status}`);
  }
}

// === Test Config CRUD ===

export async function listTestConfigs(): Promise<TestConfigResponse[]> {
  const res = await fetch(`${API_URL}/api/lab/tests`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getTestConfig(id: string): Promise<TestConfigResponse> {
  const res = await fetch(`${API_URL}/api/lab/tests/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateTestConfig(id: string, req: Partial<CreateTestConfigRequest>): Promise<TestConfigResponse> {
  const res = await fetch(`${API_URL}/api/lab/tests/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Failed to update config: ${res.status}`);
  }
  return res.json();
}

export async function deleteTestConfig(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/tests/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === V2 Run Management ===

export async function listV2Runs(): Promise<TestRunResponse[]> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getV2Run(runId: string): Promise<TestRunResponse> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function pauseV2Run(runId: string): Promise<TestRunResponse> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/pause`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function resumeV2Run(runId: string): Promise<TestRunResponse> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/resume`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function stopV2Run(runId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/v2/runs/${runId}/stop`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === Paginated Results ===

export interface PaginatedResults {
  results: QuestionResultResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface QuestionResultResponse {
  id: string;
  run_id: string;
  question_index: number;
  question_id: string;
  domain: string;
  input_text: string;
  team_index: number;
  status: string;
  final_answer: string | null;
  judgment_verdict: string | null;
  judgment_confidence: number | null;
  judgment_explanation: string | null;
  total_time_ms: number;
  total_tokens_in: number;
  total_tokens_out: number;
  estimated_cost: number;
  has_analysis?: boolean;
  agent_outputs?: Record<string, unknown>;
}

export interface AnalysisResponse {
  id: string;
  question_result_id: string;
  status: "pending" | "running" | "completed" | "error";
  failure_category: string | null;
  root_cause: string | null;
  summary: string | null;
  recommendations: string[];
  model_used: string;
  cost: number;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface DomainNode {
  domain: string;
  total: number;
  correct: number;
  wrong: number;
  accuracy: number;
}

export interface ParticipantNode {
  participant: string;
  name: string;
  run_ids: string[];
  total: number;
  correct: number;
  wrong: number;
  accuracy: number;
  domains: DomainNode[];
}

export interface ResultsStats {
  total: number;
  correct: number;
  wrong: number;
  partial: number;
  error: number;
  pending: number;
  domains: string[];
  run_ids: string[];
}

export interface AnalysisStats {
  total: number;
  completed: number;
  by_category: Record<string, number>;
}

export async function listAllResults(opts: {
  verdict?: string;
  domain?: string;
  run_id?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<PaginatedResults> {
  const params = new URLSearchParams();
  if (opts.verdict) params.set("verdict", opts.verdict);
  if (opts.domain) params.set("domain", opts.domain);
  if (opts.run_id) params.set("run_id", opts.run_id);
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  const res = await fetch(`${API_URL}/api/lab/v2/results?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getResultsTree(): Promise<ParticipantNode[]> {
  const res = await fetch(`${API_URL}/api/lab/v2/results/tree`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getResultsStats(opts: {
  verdict?: string;
  domain?: string;
  run_id?: string;
} = {}): Promise<ResultsStats> {
  const params = new URLSearchParams();
  if (opts.verdict) params.set("verdict", opts.verdict);
  if (opts.domain) params.set("domain", opts.domain);
  if (opts.run_id) params.set("run_id", opts.run_id);
  const res = await fetch(`${API_URL}/api/lab/v2/results/stats?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function analyzeResult(resultId: string): Promise<AnalysisResponse> {
  const res = await fetch(`${API_URL}/api/lab/v2/results/${resultId}/analyze`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getResultAnalysis(resultId: string): Promise<AnalysisResponse> {
  const res = await fetch(`${API_URL}/api/lab/v2/results/${resultId}/analysis`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAnalysisStats(): Promise<AnalysisStats> {
  const res = await fetch(`${API_URL}/api/lab/v2/results/analysis-stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Benchmark Domains & Sample ===

export interface BenchmarkDomain {
  name: string;
  example_count: number;
}

export interface BenchmarkQuestion {
  id: string;
  input: string;
  target: string;
  domain: string;
}

export async function getBenchmarkDomains(benchmarkId: string): Promise<BenchmarkDomain[]> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/domains`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getBenchmarkSample(benchmarkId: string, n: number = 5): Promise<BenchmarkQuestion[]> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/sample?n=${n}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Benchmark Index ===

export interface BenchmarkIndexStatus {
  benchmark_id: string;
  status: "not_indexed" | "pending" | "indexing" | "ready" | "error";
  total_questions: number;
  domains: string[];
  indexed_at: string | null;
  error_message: string | null;
  questions_attempted: number;
  overall_accuracy: number;
}

export interface IndexedQuestion {
  question_id: string;
  domain: string;
  input_preview: string;
  target_short: string;
  status: "new" | "passed" | "failed";
  total_attempts: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
  last_result: string | null;
}

export interface DomainStatsDetail {
  domain: string;
  total: number;
  attempted: number;
  correct: number;
  wrong: number;
  accuracy: number;
  new_count: number;
  failed_count: number;
}

export interface QuestionDetail {
  id: string;
  question_id: string;
  domain: string;
  input: string;
  target: string;
  target_hash: string;
  difficulty: string | null;
  tags: string[];
  status: "new" | "passed" | "failed";
  total_attempts: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
  last_attempt_at: string | null;
  last_result: string | null;
  attempts: QuestionAttempt[];
}

export interface QuestionAttempt {
  id: string;
  run_id: string;
  team_id: string;
  model_answer: string;
  judgment: string;
  confidence: number;
  paradigm_used: string | null;
  time_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  attempted_at: string;
  analysis: string | null;
  failure_category: string | null;
}

export async function getBenchmarkIndexStatus(benchmarkId: string): Promise<BenchmarkIndexStatus> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/index`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function indexBenchmark(benchmarkId: string, force: boolean = false): Promise<BenchmarkIndexStatus> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/index?force=${force}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getIndexedQuestions(benchmarkId: string, opts: {
  domain?: string;
  status?: "new" | "passed" | "failed" | "all";
  min_attempts?: number;
  max_accuracy?: number;
  limit?: number;
  offset?: number;
} = {}): Promise<IndexedQuestion[]> {
  const params = new URLSearchParams();
  if (opts.domain) params.set("domain", opts.domain);
  if (opts.status) params.set("status", opts.status);
  if (opts.min_attempts != null) params.set("min_attempts", String(opts.min_attempts));
  if (opts.max_accuracy != null) params.set("max_accuracy", String(opts.max_accuracy));
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/questions?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getBenchmarkDomainStats(benchmarkId: string): Promise<DomainStatsDetail[]> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/domains/stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getQuestionDetail(benchmarkId: string, questionId: string): Promise<QuestionDetail> {
  const res = await fetch(`${API_URL}/api/lab/benchmarks/${benchmarkId}/questions/${questionId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Team API ===

export interface TeamResponse {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  team_lead_config: AgentConfig;
  agent_configs: Record<string, AgentConfig>;
}

export interface AgentConfig {
  model: string;
  instructions: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
}

export interface CreateTeamRequest {
  name: string;
  description?: string;
  is_default?: boolean;
  team_lead_config?: AgentConfig;
  agents?: Record<string, AgentConfig>;
}

export interface UpdateTeamRequest {
  name?: string;
  description?: string;
  is_default?: boolean;
  team_lead_config?: AgentConfig;
  agents?: Record<string, AgentConfig>;
}

export async function listTeams(): Promise<TeamResponse[]> {
  const res = await fetch(`${API_URL}/api/lab/teams`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getTeam(id: string): Promise<TeamResponse> {
  const res = await fetch(`${API_URL}/api/lab/teams/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createTeam(data: CreateTeamRequest): Promise<TeamResponse> {
  const res = await fetch(`${API_URL}/api/lab/teams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: data.name,
      description: data.description || "",
      is_default: data.is_default || false,
      team_lead_config: data.team_lead_config || {
        model: "gpt-4o-mini", temperature: 0.3, max_tokens: 4096, instructions: "", enabled: true,
      },
      agents: data.agents || {},
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to create team: ${res.status}`);
  }
  return res.json();
}

export async function updateTeam(id: string, data: UpdateTeamRequest): Promise<TeamResponse> {
  const res = await fetch(`${API_URL}/api/lab/teams/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to update team: ${res.status}`);
  }
  return res.json();
}

export async function deleteTeam(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/teams/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function setDefaultTeam(id: string): Promise<TeamResponse> {
  const res = await fetch(`${API_URL}/api/lab/teams/${id}/default`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function cloneTeam(id: string, name: string): Promise<TeamResponse> {
  const res = await fetch(`${API_URL}/api/lab/teams/${id}/clone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Status Helpers ===

export const STATUS_CONFIG: Record<RunStatus, { label: string; dotClass: string; textClass: string }> = {
  created:   { label: "Created",   dotClass: "bg-gray-400",                textClass: "text-gray-400"  },
  running:   { label: "Running",   dotClass: "bg-blue-400 animate-pulse",  textClass: "text-blue-400"  },
  paused:    { label: "Paused",    dotClass: "bg-yellow-400",              textClass: "text-yellow-400" },
  completed: { label: "Done",      dotClass: "bg-green-400",               textClass: "text-green-400" },
  failed:    { label: "Failed",    dotClass: "bg-red-400",                 textClass: "text-red-400"   },
  stopped:   { label: "Stopped",   dotClass: "bg-gray-500",                textClass: "text-gray-500"  },
};

// === Reports ===

export interface ReportSummary {
  filename: string;
  run_id: number;
  name: string;
  dataset: string;
  created_at: string;
  exported_at: string;
  correct_rate: number;
}

export async function listReports(): Promise<ReportSummary[]> {
  const res = await fetch(`${API_URL}/api/lab/reports`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getReportContent(filename: string): Promise<{ content: string }> {
  const res = await fetch(`${API_URL}/api/lab/reports/${filename}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Instructions API ===

export interface InstructionFile {
  role: string;
  name: string;
  content: string;
  updated_at: string;
}

export async function listInstructions(role?: string): Promise<InstructionFile[]> {
  const url = role
    ? `${API_URL}/api/lab/instructions/${role}`
    : `${API_URL}/api/lab/instructions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getInstruction(role: string, name: string): Promise<InstructionFile> {
  const res = await fetch(`${API_URL}/api/lab/instructions/${role}/${name}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function saveInstruction(role: string, name: string, content: string): Promise<InstructionFile> {
  const res = await fetch(`${API_URL}/api/lab/instructions/${role}/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function deleteInstruction(role: string, name: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/instructions/${role}/${name}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === Paradigm Instructions API ===

export interface ParadigmInfo {
  id: string;
  name: string;
  description: string;
}

export interface InstructionSetResponse {
  id: string;
  paradigm: string;
  version: string;
  name: string;
  description: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  instructions: Record<string, string>;
}

export interface CreateInstructionSetRequest {
  name: string;
  version: string;
  description?: string;
  is_default?: boolean;
  instructions: Record<string, string>;
}

export interface UpdateInstructionSetRequest {
  name?: string;
  version?: string;
  description?: string;
  is_default?: boolean;
  instructions?: Record<string, string>;
}

export interface TeamParadigmConfig {
  team_id: string;
  paradigm_sets: Record<string, string>;
}

export async function listParadigms(): Promise<ParadigmInfo[]> {
  const res = await fetch(`${API_URL}/api/lab/paradigms`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function listInstructionSets(paradigm: string): Promise<InstructionSetResponse[]> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getInstructionSet(paradigm: string, setId: string): Promise<InstructionSetResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets/${setId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createInstructionSet(paradigm: string, req: CreateInstructionSetRequest): Promise<InstructionSetResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to create instruction set: ${res.status}`);
  }
  return res.json();
}

export async function updateInstructionSet(paradigm: string, setId: string, req: UpdateInstructionSetRequest): Promise<InstructionSetResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets/${setId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to update instruction set: ${res.status}`);
  }
  return res.json();
}

export async function deleteInstructionSet(paradigm: string, setId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets/${setId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function cloneInstructionSet(paradigm: string, setId: string, version: string, name: string): Promise<InstructionSetResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets/${setId}/clone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version, name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to clone instruction set: ${res.status}`);
  }
  return res.json();
}

export async function setDefaultInstructionSet(paradigm: string, setId: string): Promise<InstructionSetResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/sets/${setId}/default`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getTeamParadigmConfig(teamId: string): Promise<TeamParadigmConfig> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/teams/${teamId}/config`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateTeamParadigmConfig(teamId: string, paradigmSets: Record<string, string>): Promise<TeamParadigmConfig> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/teams/${teamId}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(paradigmSets),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Paradigm Role Instructions (file-based) ===

export async function getParadigmRoleInstructions(paradigm: string): Promise<Record<string, string>> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/role-instructions`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateParadigmRoleInstructions(
  paradigm: string,
  configs: Record<string, string>,
): Promise<Record<string, string>> {
  const res = await fetch(`${API_URL}/api/lab/paradigms/${paradigm}/role-instructions`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(configs),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// === Paradigm Config API ===

export interface ParadigmConfigResponse {
  id: string;
  name: string;
  label: string;
  color: string;
  description: string;
  signals: string[];
  active_roles: string[];
  active_subprocesses: string[];
  role_models: Record<string, string>;
  role_instructions: Record<string, string>;
  instruction_set_id: string;
  created_at: string;
  updated_at: string;
}

export interface ParadigmConfigUpdate {
  name?: string;
  label?: string;
  color?: string;
  description?: string;
  signals?: string[];
  active_roles?: string[];
  active_subprocesses?: string[];
  role_models?: Record<string, string>;
  role_instructions?: Record<string, string>;
  instruction_set_id?: string;
}

export async function listParadigmConfigs(): Promise<ParadigmConfigResponse[]> {
  const res = await fetch(`${API_URL}/api/lab/paradigm-config`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getParadigmConfig(id: string): Promise<ParadigmConfigResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigm-config/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateParadigmConfig(id: string, data: ParadigmConfigUpdate): Promise<ParadigmConfigResponse> {
  const res = await fetch(`${API_URL}/api/lab/paradigm-config/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to update paradigm config: ${res.status}`);
  }
  return res.json();
}

export async function seedParadigmConfigs(): Promise<{ seeded: number }> {
  const res = await fetch(`${API_URL}/api/lab/paradigm-config/seed`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function deleteParadigmConfig(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/paradigm-config/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === Instruction Sets API ===

export interface InstructionSetSummary {
  id: string;
  name: string;
  path: string;
  files: string[];
  file_count: number;
  modified: string;
}

export interface InstructionSetDetail {
  id: string;
  name: string;
  files: Record<string, string>;
  inherited_files: string[];
  own_files: string[];
}

export interface CreateInstructionSetDirRequest {
  id: string;
  name?: string;
  clone_from?: string;
  files?: Record<string, string>;
}

export async function listInstructionSetDirs(): Promise<InstructionSetSummary[]> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getInstructionSetDetail(id: string): Promise<InstructionSetDetail> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createInstructionSetDir(data: CreateInstructionSetDirRequest): Promise<InstructionSetSummary> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || `Failed to create instruction set: ${res.status}`);
  }
  return res.json();
}

export async function updateInstructionFile(setId: string, filename: string, content: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets/${setId}/files/${filename}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function deleteInstructionFile(setId: string, filename: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets/${setId}/files/${filename}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function deleteInstructionSetDir(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/instruction-sets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === Model Settings API ===

export interface ModelLimitsInfo {
  name: string;
  maxContext: number;
  maxOutput: number;
  thinking: boolean;
  interleaved: boolean;
  inputCost: number;
  outputCost: number;
}

export interface ModelSettingsData {
  id: string;
  paradigm_id: string;
  role_id: string;
  model_id: string;
  context_window: number;
  max_tokens: number;
  thinking_enabled: boolean;
  thinking_budget: number;
  interleaved_thinking: boolean;
  temperature: number;
  created_at: string;
  updated_at: string;
}

export interface ResolvedSettings {
  context_window: number;
  max_tokens: number;
  thinking_enabled: boolean;
  thinking_budget: number;
  interleaved_thinking: boolean;
  temperature: number;
  resolved_from: string;
}

export interface ModelSettingsUpsert {
  paradigm_id?: string;
  role_id?: string;
  model_id: string;
  context_window?: number;
  max_tokens?: number;
  thinking_enabled?: boolean;
  thinking_budget?: number;
  interleaved_thinking?: boolean;
  temperature?: number;
}

export async function getModelLimits(): Promise<Record<string, ModelLimitsInfo>> {
  const res = await fetch(`${API_URL}/api/lab/model-settings/limits`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getModelDefaults(): Promise<Record<string, Record<string, unknown>>> {
  const res = await fetch(`${API_URL}/api/lab/model-settings/defaults`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function listModelSettings(opts: {
  paradigm_id?: string;
  model_id?: string;
} = {}): Promise<ModelSettingsData[]> {
  const params = new URLSearchParams();
  if (opts.paradigm_id) params.set("paradigm_id", opts.paradigm_id);
  if (opts.model_id) params.set("model_id", opts.model_id);
  const res = await fetch(`${API_URL}/api/lab/model-settings?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function resolveModelSettings(
  paradigmId: string,
  roleId: string,
  modelId: string,
): Promise<ResolvedSettings> {
  const params = new URLSearchParams({
    paradigm_id: paradigmId,
    role_id: roleId,
    model_id: modelId,
  });
  const res = await fetch(`${API_URL}/api/lab/model-settings/resolve?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function upsertModelSettings(data: ModelSettingsUpsert): Promise<ModelSettingsData> {
  const res = await fetch(`${API_URL}/api/lab/model-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Failed to save model settings: ${res.status}`);
  }
  return res.json();
}

export async function deleteModelSettings(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/lab/model-settings/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// === Helpers ===

export function formatCost(cost: number): string {
  if (cost < 0.01) return "<$0.01";
  return `$${cost.toFixed(2)}`;
}

export function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}
