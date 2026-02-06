const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface Step {
  domain: string;
  level: number;
  content: string;
  status: string;
  weight: number;
  gate: number;
  is_primary: boolean;
}

export interface VerifyResponse {
  query: string;
  valid: boolean;
  primary_max: Step | null;
  corrections: number;
  violations: string[];
  steps: Step[];
  time_seconds: number;
}

export async function verifyQuery(query: string, provider = "claude"): Promise<VerifyResponse> {
  const res = await fetch(`${API_URL}/api/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, provider }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_URL}/api/health`);
  return res.json();
}

export interface BattleResponse {
  query: string;
  raw_answer: string;
  raw_time: number;
  guarded_answer: string | null;
  guarded_valid: boolean;
  guarded_corrections: number;
  guarded_violations: string[];
  guarded_time: number;
  comparison: "MATCH" | "CORRECTED" | "BLOCKED";
}

export async function battleQuery(query: string, provider = "claude"): Promise<BattleResponse> {
  const res = await fetch(`${API_URL}/api/battle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, provider }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface DualResponse {
  query: string;
  claude_answer: string | null;
  claude_valid: boolean;
  claude_time: number;
  openai_answer: string | null;
  openai_valid: boolean;
  openai_time: number;
  agreement: boolean;
}

export async function dualQuery(query: string): Promise<DualResponse> {
  const res = await fetch(`${API_URL}/api/dual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface BenchmarkItem {
  question: string;
  expected: string;
  answer: string | null;
  synthesized?: boolean;
  valid: boolean;
  corrections: number;
  time_seconds: number;
}

export interface BenchmarkResponse {
  total: number;
  valid_count: number;
  valid_rate: number;
  avg_corrections: number;
  avg_time: number;
  items: BenchmarkItem[];
}

export async function runBenchmark(n: number = 10, provider = "claude"): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_URL}/api/benchmark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ n, provider }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Streaming benchmark types
export interface BenchmarkProgress {
  type: "progress";
  index: number;
  completed: number;
  total: number;
  valid_so_far: number;
  item: BenchmarkItem;
}

export interface BenchmarkDone {
  type: "done";
  summary: {
    total: number;
    valid_count: number;
    valid_rate: number;
    avg_corrections: number;
    avg_time: number;
  };
}

export interface BenchmarkError {
  type: "error";
  message: string;
}

export type BenchmarkEvent = BenchmarkProgress | BenchmarkDone | BenchmarkError;

export function streamBenchmark(
  n: number = 10,
  concurrency: number = 5,
  provider: string = "claude",
  onProgress: (event: BenchmarkEvent) => void,
  onError: (error: Error) => void,
): () => void {
  const url = `${API_URL}/api/benchmark/stream?n=${n}&concurrency=${concurrency}&provider=${provider}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as BenchmarkEvent;
      onProgress(data);
      if (data.type === "done" || data.type === "error") {
        eventSource.close();
      }
    } catch (err) {
      onError(new Error(`Failed to parse SSE data: ${e.data}`));
    }
  };

  eventSource.onerror = () => {
    onError(new Error("SSE connection error"));
    eventSource.close();
  };

  // Return cleanup function
  return () => eventSource.close();
}
