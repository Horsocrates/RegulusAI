"use client";

import { useState, useEffect, useRef } from "react";
import { FlaskConical, ArrowLeft, Play, Square, Download, Loader2, CheckCircle, XCircle, Clock, PauseCircle, ChevronDown, ChevronRight, Settings, Save, DollarSign } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

const API_URL = "http://localhost:8000";

interface LabStep {
  id: number;
  step_number: number;
  status: string;
  questions_start: number;
  questions_end: number;
  valid_count: number;
  correct_count: number;
  total_time: number;
  started_at: string | null;
  completed_at: string | null;
}

interface CostInfo {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  spent_cost: number;
  estimated_remaining: number;
  estimated_total: number;
  currency: string;
}

interface LabRun {
  id: number;
  name: string;
  dataset: string;
  provider: string;
  total_questions: number;
  num_steps: number;
  concurrency: number;
  status: string;
  current_step: number;
  completed_questions: number;
  valid_count: number;
  correct_count: number;
  total_time: number;
  progress_percent: number;
  input_tokens: number;
  output_tokens: number;
  cost: CostInfo | null;
  created_at: string;
  updated_at: string;
  steps: LabStep[];
}

interface ReasoningStep {
  domain: string;
  content: string;
}

interface LabResult {
  id: number;
  question: string;
  expected: string;
  answer: string | null;
  valid: boolean;
  correct: boolean | null;
  informative: boolean | null;
  judge_reason: string | null;
  corrections: number;
  time_seconds: number;
  reasoning_steps?: ReasoningStep[];
}

interface StreamProgress {
  type: string;
  step_number: number;
  question_index: number;
  total_in_step: number;
  agent_id: number;
  result?: LabResult;
  error?: string;
}

interface AgentState {
  id: number;
  question: string;
  status: "idle" | "reasoning" | "judging" | "done";
  reasoning_steps: ReasoningStep[];
  result: LabResult | null;
}

function formatCost(cost: number): string {
  if (cost < 0.01) return "<$0.01";
  return `$${cost.toFixed(2)}`;
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return String(tokens);
  if (tokens < 1_000_000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${(tokens / 1_000_000).toFixed(2)}M`;
}

function ProgressCostBar({ run }: { run: LabRun }) {
  const correctRate = run.completed_questions > 0
    ? (run.correct_count / run.completed_questions * 100).toFixed(1)
    : "0.0";

  return (
    <div className="bg-white border rounded-lg p-3 mb-4">
      <div className="flex items-center gap-4">
        {/* Progress */}
        <div className="flex-1">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-gray-500">Progress</span>
            <span className="font-medium">{run.completed_questions}/{run.total_questions} ({run.progress_percent.toFixed(0)}%)</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-purple-600 h-2 rounded-full transition-all"
              style={{ width: `${run.progress_percent}%` }}
            />
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-3 text-sm border-l pl-4">
          <div className="text-center">
            <div className="font-bold text-green-600">{run.valid_count}</div>
            <div className="text-xs text-gray-500">valid</div>
          </div>
          <div className="text-center">
            <div className="font-bold text-blue-600">{correctRate}%</div>
            <div className="text-xs text-gray-500">correct</div>
          </div>
          <div className="text-center">
            <div className="font-bold">{run.total_time.toFixed(0)}s</div>
            <div className="text-xs text-gray-500">time</div>
          </div>
        </div>

        {/* Cost */}
        {run.cost && (
          <div className="flex items-center gap-2 text-sm border-l pl-4">
            <DollarSign className="w-4 h-4 text-green-600" />
            <div>
              <span className="font-medium text-green-700">{formatCost(run.cost.spent_cost)}</span>
              <span className="text-gray-400 mx-1">/</span>
              <span className="text-gray-500">{formatCost(run.cost.estimated_total)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ProcessWindow({
  agents,
  activeAgent,
  setActiveAgent,
  stepStats,
  totalStats,
  statsTab,
  setStatsTab,
  isRunning,
  steps,
  stepResults,
  expandedStep,
  setExpandedStep,
}: {
  agents: AgentState[];
  activeAgent: number;
  setActiveAgent: (id: number) => void;
  stepStats: { completed: number; correct: number; valid: number; time: number };
  totalStats: { completed: number; correct: number; valid: number };
  statsTab: "step" | "total" | "steps";
  setStatsTab: (tab: "step" | "total" | "steps") => void;
  isRunning: boolean;
  steps: LabStep[];
  stepResults: Record<number, LabResult[]>;
  expandedStep: number | null;
  setExpandedStep: (step: number | null) => void;
}) {
  const reasoningRef = useRef<HTMLDivElement>(null);
  const currentAgent = agents.find(a => a.id === activeAgent) || agents[0] || { id: 0, question: "", status: "idle" as const, reasoning_steps: [], result: null };

  useEffect(() => {
    if (reasoningRef.current) {
      reasoningRef.current.scrollTop = reasoningRef.current.scrollHeight;
    }
  }, [currentAgent?.reasoning_steps]);

  const domainColors: Record<string, string> = {
    D1: "bg-blue-900 text-blue-300",
    D2: "bg-purple-900 text-purple-300",
    D3: "bg-green-900 text-green-300",
    D4: "bg-yellow-900 text-yellow-300",
    D5: "bg-orange-900 text-orange-300",
    D6: "bg-pink-900 text-pink-300",
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 mb-4 overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
        {isRunning ? (
          <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
        ) : (
          <FlaskConical className="w-4 h-4 text-purple-400" />
        )}
        <span className="text-sm font-medium text-white">Process Monitor</span>
        <span className="text-xs text-gray-400 ml-auto">
          {isRunning ? `${agents.length} agents active` : "Idle"}
        </span>
      </div>

      {/* Agent Tabs - only show when running or have agents with results */}
      {(isRunning || agents.some(a => a.result)) && (
        <div className="flex items-center border-b border-gray-700 bg-gray-800/50">
          <div className="flex overflow-x-auto">
            {agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => setActiveAgent(agent.id)}
                className={`px-3 py-2 text-sm font-medium whitespace-nowrap ${
                  activeAgent === agent.id
                    ? "bg-gray-900 text-white border-b-2 border-purple-500"
                    : "text-gray-400 hover:text-white hover:bg-gray-700"
                }`}
              >
                Agent {agent.id + 1}
                {agent.status === "idle" && <Clock className="inline w-3 h-3 ml-1 text-gray-500" />}
                {agent.status === "reasoning" && <Loader2 className="inline w-3 h-3 ml-1 animate-spin" />}
                {agent.status === "done" && agent.result?.correct && <CheckCircle className="inline w-3 h-3 ml-1 text-green-500" />}
                {agent.status === "done" && agent.result && !agent.result.correct && <XCircle className="inline w-3 h-3 ml-1 text-red-500" />}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex">
        {/* Reasoning Panel */}
        <div className="flex-1 border-r border-gray-700">
          {currentAgent?.question && (
            <div className="px-3 py-2 bg-gray-800 text-xs text-gray-400 border-b border-gray-700 truncate">
              Q: {currentAgent.question}
            </div>
          )}
          <div ref={reasoningRef} className="p-3 h-72 overflow-y-auto font-mono text-sm">
            {!isRunning && !agents.some(a => a.result) && (
              <div className="text-gray-500 text-center py-8">
                <FlaskConical className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                <div>Click Start to begin processing</div>
                <div className="text-xs text-gray-600 mt-1">Agent reasoning will appear here</div>
              </div>
            )}
            {isRunning && currentAgent?.reasoning_steps.length === 0 && currentAgent?.status === "idle" && (
              <div className="text-gray-500">
                <div className="flex items-center gap-2 mb-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Waiting for work...</span>
                </div>
              </div>
            )}
            {currentAgent?.reasoning_steps.map((step, i) => (
              <div key={i} className="mb-2">
                <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold mr-2 ${domainColors[step.domain] || "bg-gray-700 text-gray-300"}`}>
                  {step.domain}
                </span>
                <span className="text-gray-300">{step.content}</span>
              </div>
            ))}
            {currentAgent?.status === "judging" && (
              <div className="text-orange-400 flex items-center gap-2 mt-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Judge evaluating...
              </div>
            )}
          </div>
        </div>

        {/* Stats Panel */}
        <div className="w-72 bg-gray-800 flex flex-col">
          {/* Stats Tabs */}
          <div className="flex border-b border-gray-700">
            <button
              onClick={() => setStatsTab("step")}
              className={`flex-1 px-2 py-1.5 text-xs font-medium ${
                statsTab === "step" ? "bg-gray-900 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              Step
            </button>
            <button
              onClick={() => setStatsTab("total")}
              className={`flex-1 px-2 py-1.5 text-xs font-medium ${
                statsTab === "total" ? "bg-gray-900 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              Total
            </button>
            <button
              onClick={() => setStatsTab("steps")}
              className={`flex-1 px-2 py-1.5 text-xs font-medium ${
                statsTab === "steps" ? "bg-gray-900 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              Steps
            </button>
          </div>

          {/* Current Result */}
          {statsTab !== "steps" && currentAgent?.result && (
            <div className="p-3 border-b border-gray-700">
              <div className="text-xs text-gray-400 mb-1">Last Result</div>
              <div className={`flex items-center gap-2 ${currentAgent.result.correct ? "text-green-400" : "text-red-400"}`}>
                {currentAgent.result.correct ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                <span className="font-medium">{currentAgent.result.correct ? "Correct" : "Incorrect"}</span>
              </div>
              <div className="text-xs text-gray-500 mt-1 truncate" title={currentAgent.result.expected}>
                Expected: {currentAgent.result.expected}
              </div>
              <div className="text-xs text-gray-400 mt-1 line-clamp-2" title={currentAgent.result.answer || ""}>
                Answer: {currentAgent.result.answer || "N/A"}
              </div>
            </div>
          )}

          {/* Stats Content */}
          <div className="p-3 flex-1 overflow-y-auto">
            {statsTab === "step" && (
              <div className="space-y-1 text-sm">
                <div className="text-xs text-gray-400 mb-2">Current Step</div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Completed</span>
                  <span className="text-white">{stepStats.completed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Valid</span>
                  <span className="text-green-400">{stepStats.valid}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Correct</span>
                  <span className="text-blue-400">{stepStats.correct}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Rate</span>
                  <span className="text-purple-400">
                    {stepStats.completed > 0 ? (stepStats.correct / stepStats.completed * 100).toFixed(1) : 0}%
                  </span>
                </div>
              </div>
            )}
            {statsTab === "total" && (
              <div className="space-y-1 text-sm">
                <div className="text-xs text-gray-400 mb-2">Total Progress</div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Completed</span>
                  <span className="text-white">{totalStats.completed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Valid</span>
                  <span className="text-green-400">{totalStats.valid}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Correct</span>
                  <span className="text-blue-400">{totalStats.correct}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Rate</span>
                  <span className="text-purple-400">
                    {totalStats.completed > 0 ? (totalStats.correct / totalStats.completed * 100).toFixed(1) : 0}%
                  </span>
                </div>
              </div>
            )}
            {statsTab === "steps" && (
              <div className="space-y-2 text-sm max-h-48 overflow-y-auto">
                {steps.map((step) => {
                  const results = stepResults[step.step_number] || [];
                  const qCount = step.questions_end - step.questions_start;
                  return (
                    <div
                      key={step.id}
                      onClick={() => setExpandedStep(expandedStep === step.step_number ? null : step.step_number)}
                      className={`p-2 rounded cursor-pointer ${
                        step.status === "completed" ? "bg-green-900/30" :
                        step.status === "running" ? "bg-blue-900/30" :
                        "bg-gray-700/30"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <StatusIcon status={step.status} />
                        <span className="text-white">Step {step.step_number}</span>
                        <span className="text-xs text-gray-400 ml-auto">{qCount}q</span>
                      </div>
                      {step.status === "completed" && (
                        <div className="text-xs text-gray-400 mt-1">
                          {step.correct_count}/{results.length || qCount} correct
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    case "running":
      return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
    case "failed":
      return <XCircle className="w-5 h-5 text-red-500" />;
    case "paused":
      return <PauseCircle className="w-5 h-5 text-yellow-500" />;
    default:
      return <Clock className="w-5 h-5 text-gray-400" />;
  }
}

function ConfigPanel({
  run,
  onUpdated,
}: {
  run: LabRun;
  onUpdated: () => void;
}) {
  const pendingSteps = run.steps.filter((s) => s.status === "pending");
  const remainingQuestions = pendingSteps.reduce(
    (sum, s) => sum + (s.questions_end - s.questions_start),
    0
  );

  const [concurrency, setConcurrency] = useState(run.concurrency || 5);
  const [remainingSteps, setRemainingSteps] = useState(String(pendingSteps.length));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const parsedSteps = parseInt(remainingSteps) || 1;
  const actualSteps = Math.min(Math.max(1, parsedSteps), remainingQuestions);
  const questionsPerStep = remainingQuestions > 0 ? Math.ceil(remainingQuestions / actualSteps) : 0;

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch(`${API_URL}/api/lab/runs/${run.id}/config`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          concurrency,
          remaining_steps: actualSteps,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to update");
      }

      setMessage("Configuration updated!");
      onUpdated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (remainingQuestions === 0) {
    return null;
  }

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Settings className="w-5 h-5 text-yellow-600" />
        <span className="font-medium text-yellow-800">Adjust Configuration</span>
        <span className="text-sm text-yellow-600 ml-auto">
          {remainingQuestions} questions remaining
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Parallel Agents
          </label>
          <select
            value={concurrency}
            onChange={(e) => setConcurrency(Number(e.target.value))}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          >
            <option value={1}>1 (sequential)</option>
            <option value={3}>3</option>
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={15}>15</option>
            <option value={20}>20</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Remaining Steps
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              min={1}
              max={remainingQuestions}
              value={remainingSteps}
              onChange={(e) => setRemainingSteps(e.target.value)}
              className="flex-1 px-3 py-2 border rounded-lg text-sm"
            />
            <button
              type="button"
              onClick={() => setRemainingSteps(String(Math.ceil(remainingQuestions / concurrency)))}
              className="px-2 py-1 text-xs bg-yellow-200 text-yellow-800 rounded hover:bg-yellow-300"
              title="Set steps = remaining / concurrency"
            >
              Auto
            </button>
          </div>
        </div>
      </div>

      <div className="text-sm text-yellow-700 mb-3">
        {actualSteps} steps × ~{questionsPerStep} questions each, {Math.min(concurrency, questionsPerStep)} parallel
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 flex items-center gap-2 text-sm"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Apply Changes
        </button>
        {message && (
          <span className={`text-sm ${message.includes("Error") ? "text-red-600" : "text-green-600"}`}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}

function StepCard({
  step,
  isActive,
  results,
  onExpand,
  expanded,
}: {
  step: LabStep;
  isActive: boolean;
  results: LabResult[];
  onExpand: () => void;
  expanded: boolean;
}) {
  const questionsCount = step.questions_end - step.questions_start;
  const correctRate = results.length > 0
    ? (results.filter(r => r.correct).length / results.length * 100).toFixed(1)
    : "0.0";

  return (
    <div className={`border rounded-lg overflow-hidden ${isActive ? "border-blue-500 ring-2 ring-blue-200" : ""}`}>
      <div
        onClick={onExpand}
        className={`p-4 cursor-pointer hover:bg-gray-50 ${step.status === "completed" ? "bg-green-50/50" : ""}`}
      >
        <div className="flex items-center gap-3">
          <StatusIcon status={step.status} />
          <div className="flex-1">
            <div className="font-medium">Step {step.step_number}</div>
            <div className="text-sm text-gray-500">
              Questions {step.questions_start + 1} - {step.questions_end} ({questionsCount} total)
            </div>
          </div>
          <div className="text-right text-sm">
            <div className="font-medium">{step.valid_count}/{results.length || questionsCount} valid</div>
            {step.status === "completed" && (
              <div className="text-gray-500">{correctRate}% correct</div>
            )}
          </div>
          {expanded ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
        </div>
      </div>

      {expanded && results.length > 0 && (
        <div className="border-t bg-gray-50 p-4 max-h-96 overflow-y-auto">
          <div className="space-y-3">
            {results.map((r, i) => (
              <div
                key={r.id}
                className={`bg-white p-3 rounded border ${
                  r.correct ? "border-green-200" : r.valid ? "border-yellow-200" : "border-red-200"
                }`}
              >
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-xs font-mono text-gray-400">#{i + 1}</span>
                  {r.correct ? (
                    <CheckCircle className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                  ) : r.valid ? (
                    <XCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  )}
                  <p className="text-sm font-medium text-gray-800 flex-1">{r.question}</p>
                </div>
                <div className="text-xs text-gray-500 ml-6">
                  <div><strong>Expected:</strong> {r.expected}</div>
                  <div><strong>Answer:</strong> {r.answer || "No answer"}</div>
                  {r.judge_reason && <div><strong>Judge:</strong> {r.judge_reason}</div>}
                  <div className="mt-1 text-gray-400">
                    {r.time_seconds.toFixed(1)}s | {r.corrections} corrections
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = Number(params.id);

  const [run, setRun] = useState<LabRun | null>(null);
  const [stepResults, setStepResults] = useState<Record<number, LabResult[]>>({});
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [currentProgress, setCurrentProgress] = useState<StreamProgress | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Process window state
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [activeAgent, setActiveAgent] = useState(0);
  const [statsTab, setStatsTab] = useState<"step" | "total" | "steps">("step");
  const [stepStats, setStepStats] = useState({ completed: 0, correct: 0, valid: 0, time: 0 });

  const fetchRun = async () => {
    try {
      const res = await fetch(`${API_URL}/api/lab/runs/${runId}`);
      if (res.ok) {
        const data = await res.json();
        setRun(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStepResults = async (stepNumber: number) => {
    if (stepResults[stepNumber]) return;

    try {
      const res = await fetch(`${API_URL}/api/lab/runs/${runId}/steps/${stepNumber}/results`);
      if (res.ok) {
        const data = await res.json();
        setStepResults((prev) => ({ ...prev, [stepNumber]: data }));
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchRun();
  }, [runId]);

  useEffect(() => {
    if (expandedStep !== null) {
      fetchStepResults(expandedStep);
    }
  }, [expandedStep]);

  const handleContinue = () => {
    console.log("handleContinue called, run:", run?.id, "running:", running);
    if (!run) {
      console.log("No run, returning");
      return;
    }

    const nextStep = run.steps.find((s) => s.status === "pending");
    console.log("Next pending step:", nextStep?.step_number, "all steps:", run.steps.map(s => ({n: s.step_number, s: s.status})));
    if (!nextStep) {
      console.log("No pending step found, returning");
      return;
    }

    setRunning(true);
    setExpandedStep(nextStep.step_number);
    setCurrentProgress(null);
    setStepStats({ completed: 0, correct: 0, valid: 0, time: 0 });

    // Initialize agents based on concurrency
    const numAgents = run.concurrency || 5;
    const initialAgents: AgentState[] = Array.from({ length: numAgents }, (_, i) => ({
      id: i,
      question: "",
      status: "idle",
      reasoning_steps: [],
      result: null,
    }));
    setAgents(initialAgents);
    setActiveAgent(0);

    const url = `${API_URL}/api/lab/runs/${runId}/stream?step_number=${nextStep.step_number}`;
    console.log("SSE connecting to:", url);
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    const liveResults: LabResult[] = [];

    eventSource.onmessage = (e) => {
      try {
        const data: StreamProgress = JSON.parse(e.data);
        console.log("SSE message:", data.type, data);
        setCurrentProgress(data);

        // Handle start event - update agents to show they're working
        if (data.type === "start") {
          console.log(`Step ${data.step_number} started with ${data.total_in_step} questions`);
        }

        if (data.type === "progress" && data.result) {
          liveResults.push(data.result);
          setStepResults((prev) => ({
            ...prev,
            [data.step_number]: [...liveResults],
          }));

          // Update agent state
          const agentId = data.agent_id;
          setAgents(prev => prev.map(a =>
            a.id === agentId
              ? {
                  ...a,
                  status: "done" as const,
                  result: data.result!,
                  reasoning_steps: data.result?.reasoning_steps || [],
                  question: data.result?.question || "",
                }
              : a
          ));

          // Update step stats
          setStepStats(prev => ({
            completed: prev.completed + 1,
            correct: prev.correct + (data.result?.correct ? 1 : 0),
            valid: prev.valid + (data.result?.valid ? 1 : 0),
            time: prev.time + (data.result?.time_seconds || 0),
          }));
        }

        if (data.type === "complete" || data.type === "error") {
          setRunning(false);
          eventSource.close();
          fetchRun(); // Refresh full state
        }
      } catch (err) {
        console.error("Parse error:", err);
      }
    };

    eventSource.onopen = () => {
      console.log("SSE connected");
    };

    eventSource.onerror = (e) => {
      console.error("SSE error:", e);
      setRunning(false);
      eventSource.close();
      fetchRun();
    };
  };

  const handleStop = async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      await fetch(`${API_URL}/api/lab/runs/${runId}/stop`, { method: "POST" });
    } catch (err) {
      console.error(err);
    }

    setRunning(false);
    fetchRun();
  };

  const handleExport = async () => {
    try {
      const res = await fetch(`${API_URL}/api/lab/runs/${runId}/export`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        alert(`Exported to:\n${data.files.json}\n${data.files.markdown}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
      </main>
    );
  }

  if (!run) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-2xl font-bold text-red-600">Run not found</h1>
          <Link href="/lab" className="text-blue-600 hover:underline mt-4 inline-block">
            Back to Lab
          </Link>
        </div>
      </main>
    );
  }

  const pendingSteps = run.steps.filter((s) => s.status === "pending");
  const canContinue = pendingSteps.length > 0 && !running;
  const totalStats = {
    completed: run.completed_questions,
    correct: run.correct_count,
    valid: run.valid_count,
  };

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/lab" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FlaskConical className="w-8 h-8 text-purple-600" />
          <div className="flex-1">
            <h1 className="text-xl font-bold">{run.name}</h1>
            <p className="text-sm text-gray-500">
              {run.dataset} / {run.provider} / {run.num_steps} steps
            </p>
          </div>
          <button
            onClick={handleExport}
            disabled={run.completed_questions === 0}
            className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          {running ? (
            <button
              onClick={handleStop}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
            >
              <Square className="w-4 h-4" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleContinue}
              disabled={!canContinue}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              {run.status === "created" ? "Start" : "Continue"}
            </button>
          )}
        </div>

        {/* Progress + Cost Bar */}
        <ProgressCostBar run={run} />

        {/* Config Panel - show when paused or created */}
        {!running && (run.status === "paused" || run.status === "created") && (
          <ConfigPanel run={run} onUpdated={fetchRun} />
        )}

        {/* Process Window - always visible */}
        <ProcessWindow
          agents={agents.length > 0 ? agents : [{ id: 0, question: "", status: "idle", reasoning_steps: [], result: null }]}
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
          stepStats={stepStats}
          totalStats={totalStats}
          statsTab={statsTab}
          setStatsTab={setStatsTab}
          isRunning={running}
          steps={run.steps}
          stepResults={stepResults}
          expandedStep={expandedStep}
          setExpandedStep={setExpandedStep}
        />
      </div>
    </main>
  );
}
