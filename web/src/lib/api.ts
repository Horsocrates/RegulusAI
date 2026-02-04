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
