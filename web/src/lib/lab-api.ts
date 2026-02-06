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
}

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

// === Status Helpers ===

export const STATUS_CONFIG: Record<RunStatus, { label: string; dotClass: string; textClass: string }> = {
  created:   { label: "Created",   dotClass: "bg-gray-400",                textClass: "text-gray-400"  },
  running:   { label: "Running",   dotClass: "bg-blue-400 animate-pulse",  textClass: "text-blue-400"  },
  paused:    { label: "Paused",    dotClass: "bg-yellow-400",              textClass: "text-yellow-400" },
  completed: { label: "Done",      dotClass: "bg-green-400",               textClass: "text-green-400" },
  failed:    { label: "Failed",    dotClass: "bg-red-400",                 textClass: "text-red-400"   },
  stopped:   { label: "Stopped",   dotClass: "bg-gray-500",                textClass: "text-gray-500"  },
};

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
